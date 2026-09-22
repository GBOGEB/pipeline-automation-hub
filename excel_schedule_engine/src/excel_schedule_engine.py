#!/usr/bin/env python3
"""Excel schedule-table extraction engine.

Extracts every defined Excel table and, optionally, each non-empty worksheet used
range into separate CSV and XLSX exports. Generates a machine manifest and a
human-readable schedule index for the MAIN pipeline.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass, asdict
from datetime import date, datetime
from pathlib import Path
from typing import List, Sequence, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.formula.translate import Translator, TranslatorError
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.cell import range_boundaries
from openpyxl.worksheet.table import Table, TableStyleInfo


SCHEDULE_HEADER_GROUPS = {
    "activity": {"activity", "task", "work package", "work_package", "wbs", "milestone"},
    "start": {"start", "start date", "start_date", "planned start", "baseline start"},
    "finish": {"finish", "end", "finish date", "end date", "planned finish", "baseline finish"},
    "duration": {"duration", "days", "working days", "lead time"},
    "owner": {"owner", "responsible", "assignee", "lead"},
    "status": {"status", "state", "phase"},
    "dependency": {"dependency", "dependencies", "predecessor", "successor"},
    "progress": {"progress", "% complete", "percent complete", "completion"},
    "float": {"float", "slack", "total float"},
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    value = re.sub(r"_+", "_", value).strip("_.")
    return value or "table"


def logical_export_id(sheet: str, source_kind: str, source_name: str, source_ref: str) -> str:
    identity = "\x1f".join([sheet, source_kind, source_name, source_ref])
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
    return f"{safe_name(f'{sheet}__{source_name}')}__{digest}"


def jsonable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def text_header(value) -> str:
    return "" if value is None else str(value).strip()


def schedule_signature(headers: Sequence[object]) -> Tuple[int, List[str]]:
    normalized = {text_header(h).casefold() for h in headers if text_header(h)}
    reasons: List[str] = []
    for group, aliases in SCHEDULE_HEADER_GROUPS.items():
        if normalized.intersection({a.casefold() for a in aliases}):
            reasons.append(group)
    return len(reasons), reasons


def rows_from_ref(ws, ref: str) -> List[List[object]]:
    min_col, min_row, max_col, max_row = range_boundaries(ref)
    return [
        [ws.cell(row=r, column=c).value for c in range(min_col, max_col + 1)]
        for r in range(min_row, max_row + 1)
    ]


def used_range_rows(ws) -> Tuple[List[List[object]], str]:
    ref = ws.calculate_dimension()
    if ref == "A1:A1" and ws["A1"].value is None:
        return [], ref
    return rows_from_ref(ws, ref), ref


def has_payload(rows: Sequence[Sequence[object]]) -> bool:
    return any(any(v not in (None, "") for v in row) for row in rows)


def trim_empty_edges(rows: List[List[object]]) -> List[List[object]]:
    while rows and not any(v not in (None, "") for v in rows[-1]):
        rows.pop()
    if not rows:
        return rows
    max_nonempty = 0
    for row in rows:
        for i, value in enumerate(row, start=1):
            if value not in (None, ""):
                max_nonempty = max(max_nonempty, i)
    return [row[:max_nonempty] for row in rows]


@dataclass
class ExportRecord:
    id: str
    source_workbook: str
    source_sheet: str
    source_kind: str
    source_name: str
    source_ref: str
    rows_including_header: int
    data_rows: int
    columns: int
    headers: List[str]
    schedule_score: int
    schedule_reasons: List[str]
    schedule_candidate: bool
    csv_path: str
    xlsx_path: str
    csv_sha256: str
    xlsx_sha256: str


class ExcelScheduleEngine:
    def __init__(
        self,
        source: Path,
        output_root: Path,
        include_sheet_ranges: bool = True,
        cell_mode: str = "formula",
        schedule_as_of: date | None = None,
        schedule_due_soon_days: int = 14,
    ):
        self.source = source
        self.output_root = output_root
        self.include_sheet_ranges = include_sheet_ranges
        self.cell_mode = cell_mode
        self.schedule_as_of = schedule_as_of
        self.schedule_due_soon_days = schedule_due_soon_days
        self.csv_dir = output_root / "Outputs" / "excel" / "tables_csv"
        self.xlsx_dir = output_root / "Outputs" / "excel" / "tables_xlsx"
        self.manifest_path = output_root / "Outputs" / "excel" / "table_manifest.json"
        self.report_dir = output_root / "Reports"
        self.schedule_index_md = self.report_dir / "schedule_index.md"
        self.schedule_index_csv = self.report_dir / "schedule_index.csv"
        self._export_ids = set()

    def _prepare_dirs(self) -> None:
        self.csv_dir.mkdir(parents=True, exist_ok=True)
        self.xlsx_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _load(self):
        data_only = self.cell_mode == "cached"
        keep_vba = self.source.suffix.lower() == ".xlsm"
        return load_workbook(
            self.source,
            data_only=data_only,
            keep_vba=keep_vba,
            read_only=False,
        )

    def _write_csv(self, path: Path, rows: Sequence[Sequence[object]]) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerows([[jsonable(v) for v in row] for row in rows])

    def _translate_formula(
        self,
        value,
        source_row: int,
        source_col: int,
        dest_row: int,
        dest_col: int,
    ):
        if self.cell_mode != "formula" or not isinstance(value, str) or not value.startswith("="):
            return value
        source_coord = f"{get_column_letter(source_col)}{source_row}"
        dest_coord = f"{get_column_letter(dest_col)}{dest_row}"
        try:
            return Translator(value, origin=source_coord).translate_formula(dest_coord)
        except TranslatorError:
            return value

    def _write_xlsx(
        self,
        path: Path,
        rows: Sequence[Sequence[object]],
        title: str,
        source_kind: str,
        source_ref: str,
    ) -> None:
        wb = Workbook()
        ws = wb.active
        ws.title = "Data"
        source_min_col, source_min_row, _, _ = range_boundaries(source_ref)

        for dest_row, row in enumerate(rows, start=1):
            for dest_col, value in enumerate(row, start=1):
                source_row = source_min_row + dest_row - 1
                source_col = source_min_col + dest_col - 1
                ws.cell(row=dest_row, column=dest_col).value = self._translate_formula(
                    value,
                    source_row,
                    source_col,
                    dest_row,
                    dest_col,
                )

        if rows:
            for cell in ws[1]:
                cell.font = Font(bold=True)
                cell.fill = PatternFill("solid", fgColor="D9EAF7")
                cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.freeze_panes = "A2"
            for col in ws.columns:
                letter = col[0].column_letter
                width = min(
                    max(
                        10,
                        max(
                            len(str(c.value)) if c.value is not None else 0
                            for c in col
                        )
                        + 2,
                    ),
                    60,
                )
                ws.column_dimensions[letter].width = width

            if source_kind == "excel_table":
                last_col = get_column_letter(max(len(r) for r in rows))
                table = Table(displayName=title, ref=f"A1:{last_col}{len(rows)}")
                table.tableStyleInfo = TableStyleInfo(
                    name="TableStyleMedium2",
                    showFirstColumn=False,
                    showLastColumn=False,
                    showRowStripes=True,
                    showColumnStripes=False,
                )
                ws.add_table(table)

        meta = wb.create_sheet("_META")
        meta.sheet_state = "hidden"
        meta["A1"] = "source_workbook"
        meta["B1"] = str(self.source)
        meta["A2"] = "logical_table"
        meta["B2"] = title
        meta["A3"] = "cell_mode"
        meta["B3"] = self.cell_mode
        meta["A4"] = "source_ref"
        meta["B4"] = source_ref
        wb.save(path)

    def _export(
        self,
        ws,
        source_kind: str,
        source_name: str,
        source_ref: str,
        rows: List[List[object]],
    ) -> ExportRecord:
        rows = trim_empty_edges(rows)
        if not rows or not has_payload(rows):
            raise ValueError("cannot export an empty table")

        headers = [text_header(v) for v in rows[0]]
        score, reasons = schedule_signature(headers)
        base = logical_export_id(ws.title, source_kind, source_name, source_ref)
        if base in self._export_ids:
            raise RuntimeError(f"logical export id collision: {base}")
        self._export_ids.add(base)
        csv_path = self.csv_dir / f"{base}.csv"
        xlsx_path = self.xlsx_dir / f"{base}.xlsx"

        self._write_csv(csv_path, rows)
        self._write_xlsx(xlsx_path, rows, source_name, source_kind, source_ref)

        return ExportRecord(
            id=base,
            source_workbook=str(self.source),
            source_sheet=ws.title,
            source_kind=source_kind,
            source_name=source_name,
            source_ref=source_ref,
            rows_including_header=len(rows),
            data_rows=max(0, len(rows) - 1),
            columns=max((len(r) for r in rows), default=0),
            headers=headers,
            schedule_score=score,
            schedule_reasons=reasons,
            schedule_candidate=score >= 2,
            csv_path=str(csv_path.relative_to(self.output_root)),
            xlsx_path=str(xlsx_path.relative_to(self.output_root)),
            csv_sha256=sha256_file(csv_path),
            xlsx_sha256=sha256_file(xlsx_path),
        )

    def run(self) -> List[ExportRecord]:
        if not self.source.exists():
            raise FileNotFoundError(self.source)
        if self.source.suffix.lower() not in {".xlsx", ".xlsm"}:
            raise ValueError("supported source formats are .xlsx and .xlsm")

        self._prepare_dirs()
        wb = self._load()
        records: List[ExportRecord] = []
        errors = []

        try:
            for ws in wb.worksheets:
                for table in ws.tables.values():
                    rows = rows_from_ref(ws, table.ref)
                    try:
                        records.append(
                            self._export(
                                ws,
                                "excel_table",
                                table.name,
                                table.ref,
                                rows,
                            )
                        )
                    except Exception as exc:
                        errors.append(
                            {
                                "sheet": ws.title,
                                "table": table.name,
                                "error": str(exc),
                            }
                        )

                if self.include_sheet_ranges and not ws.tables:
                    rows, ref = used_range_rows(ws)
                    if rows and has_payload(rows):
                        try:
                            records.append(
                                self._export(
                                    ws,
                                    "sheet_used_range",
                                    "USED_RANGE",
                                    ref,
                                    rows,
                                )
                            )
                        except Exception as exc:
                            errors.append(
                                {
                                    "sheet": ws.title,
                                    "table": "USED_RANGE",
                                    "error": str(exc),
                                }
                            )
        finally:
            wb.close()

        self._write_manifest(records, errors)
        self._write_schedule_index(records)

        if errors:
            raise RuntimeError(
                f"{len(errors)} table export(s) failed; see {self.manifest_path}"
            )

        from schedule_projection import ScheduleProjectionEngine

        ScheduleProjectionEngine(
            output_root=self.output_root,
            table_manifest_path=self.manifest_path,
            as_of=self.schedule_as_of,
            due_soon_days=self.schedule_due_soon_days,
        ).run()
        return records

    def _write_manifest(
        self,
        records: Sequence[ExportRecord],
        errors: Sequence[dict],
    ) -> None:
        source_sha = sha256_file(self.source)
        payload = {
            "schema": "gbogeb.excel_schedule_engine.table_manifest.v1",
            "generated_at": datetime.now().astimezone().isoformat(),
            "source": {
                "path": str(self.source),
                "sha256": source_sha,
                "cell_mode": self.cell_mode,
            },
            "authority": {
                "source_workbook_is_input_authority": True,
                "exports_are_derived_renditions": True,
                "authority_transfer": False,
            },
            "summary": {
                "tables_exported": len(records),
                "schedule_candidates": sum(
                    1 for r in records if r.schedule_candidate
                ),
                "errors": len(errors),
            },
            "tables": [asdict(r) for r in records],
            "errors": list(errors),
        }
        self.manifest_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _write_schedule_index(
        self,
        records: Sequence[ExportRecord],
    ) -> None:
        with self.schedule_index_csv.open(
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "id",
                    "sheet",
                    "kind",
                    "rows",
                    "columns",
                    "schedule_candidate",
                    "schedule_score",
                    "schedule_reasons",
                    "csv",
                    "xlsx",
                ]
            )
            for r in records:
                writer.writerow(
                    [
                        r.id,
                        r.source_sheet,
                        r.source_kind,
                        r.data_rows,
                        r.columns,
                        r.schedule_candidate,
                        r.schedule_score,
                        ";".join(r.schedule_reasons),
                        r.csv_path,
                        r.xlsx_path,
                    ]
                )

        lines = [
            "# Excel Schedule/Data Table Index",
            "",
            f"Source: `{self.source}`",
            "",
            (
                "Every logical table is exported separately as CSV and XLSX. "
                "Schedule classification is heuristic and does not change source authority."
            ),
            "",
            (
                "| ID | Sheet | Kind | Rows | Cols | Schedule | Score | "
                "Signals | CSV | XLSX |"
            ),
            "|---|---|---|---:|---:|---|---:|---|---|---|",
        ]
        for r in records:
            lines.append(
                f"| `{r.id}` | {r.source_sheet} | {r.source_kind} | "
                f"{r.data_rows} | {r.columns} | "
                f"{'YES' if r.schedule_candidate else 'NO'} | "
                f"{r.schedule_score} | "
                f"{', '.join(r.schedule_reasons) or '-'} | "
                f"`{r.csv_path}` | `{r.xlsx_path}` |"
            )
        self.schedule_index_md.write_text(
            "\n".join(lines) + "\n",
            encoding="utf-8",
        )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Extract all Excel tables into separate CSV/XLSX files "
            "and build schedule indexes."
        )
    )
    p.add_argument("source", type=Path, help="Input .xlsx/.xlsm workbook")
    p.add_argument(
        "--output-root",
        type=Path,
        default=Path("."),
        help="Pipeline root containing Outputs/ and Reports/",
    )
    p.add_argument(
        "--tables-only",
        action="store_true",
        help=(
            "Do not export non-empty worksheet used ranges "
            "when no Excel table exists"
        ),
    )
    p.add_argument(
        "--cell-mode",
        choices=["formula", "cached"],
        default="formula",
        help="Read formulas or cached calculated values",
    )
    p.add_argument(
        "--schedule-as-of",
        type=date.fromisoformat,
        default=None,
        help="Deterministic schedule dashboard as-of date (YYYY-MM-DD)",
    )
    p.add_argument(
        "--schedule-due-soon-days",
        type=int,
        default=14,
        help="Yellow due-soon horizon in calendar days",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    engine = ExcelScheduleEngine(
        source=args.source,
        output_root=args.output_root,
        include_sheet_ranges=not args.tables_only,
        cell_mode=args.cell_mode,
        schedule_as_of=args.schedule_as_of,
        schedule_due_soon_days=args.schedule_due_soon_days,
    )
    records = engine.run()
    print(
        json.dumps(
            {
                "tables_exported": len(records),
                "schedule_candidates": sum(
                    r.schedule_candidate for r in records
                ),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
