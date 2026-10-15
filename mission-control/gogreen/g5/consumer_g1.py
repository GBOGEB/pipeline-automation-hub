"""Fail-closed consumer-side verification of an immutable G1 producer artifact.

Producer, consumer and QPS are independent authority levels. This module
does not run code from downloaded artifacts and cannot admit a PR or QPS.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

SCHEMA = "gogreen.g5.g1-consumer-replay.v1"
SHA = re.compile(r"[0-9a-f]{40}\Z")
HEX = re.compile(r"[0-9a-f]{64}\Z")
MEMBERS = {"rollup.json", "rollup.html", "manifest.json", "source_tests.log", "html_tests.log"}
MAX_ARCHIVE = 2_000_000
MAX_MEMBER = 1_000_000


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_archive(raw: bytes, *, expected_archive_sha256: str,
                     expected_source_sha: str, expected_run_id: int,
                     expected_job_id: int):
    if not isinstance(raw, bytes) or len(raw) > MAX_ARCHIVE:
        raise ValueError("ZIP byte budget exceeded")
    if not HEX.fullmatch(expected_archive_sha256) or _sha(raw) != expected_archive_sha256:
        raise ValueError("downloaded ZIP SHA256 mismatch")
    if not SHA.fullmatch(expected_source_sha):
        raise ValueError("invalid pinned producer SHA")
    if any(type(x) is not int or x < 1 for x in (expected_run_id, expected_job_id)):
        raise ValueError("missing immutable GitHub producer run/job ID")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            entries = z.infolist()
            if {x.filename for x in entries} != MEMBERS or len(entries) != len(MEMBERS):
                raise ValueError("ZIP members changed or unsafe")
            for entry in entries:
                if entry.filename.startswith("/") or ".." in entry.filename.split("/"):
                    raise ValueError("unsafe ZIP member path")
                if entry.file_size > MAX_MEMBER or entry.flag_bits & 1:
                    raise ValueError("ZIP member size/encryption forbidden")
                # Symlinks are never accepted as source artifacts.
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("ZIP symlink forbidden")
            if z.testzip() is not None:
                raise ValueError("ZIP CRC/integrity failure")
            members = {name: z.read(name) for name in MEMBERS}
    except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
        raise ValueError("invalid ZIP encoding") from exc
    manifest = json.loads(members["manifest.json"])
    body = json.loads(members["rollup.json"])
    if manifest.get("schema") != "gogreen.federation.rollup.manifest.v1":
        raise ValueError("unknown G1 producer manifest schema")
    if manifest.get("producer_source_sha") != expected_source_sha or manifest.get("native_run_id") != expected_run_id:
        raise ValueError("G1 artifact exact head/run provenance mismatch")
    if manifest.get("native_attempt") != 1:
        raise ValueError("unexpected source run attempt")
    if manifest.get("evidence_class") != "PRODUCER_NATIVE_NOT_CONSUMER_ACCEPTED":
        raise ValueError("source evidence class mismatch")
    if any(manifest.get(x) is not False for x in
           ("authority_transfer", "merge_authorized", "independent_downloaded_bytes_verified")):
        raise ValueError("producer claimed unauthorized approval")
    for name in ("rollup.json", "rollup.html"):
        if manifest.get("sha256", {}).get(name) != _sha(members[name]):
            raise ValueError("producer inner-member digest mismatch: " + name)
    stat = body.get("breadth_depth", {})
    if body.get("schema") != "gogreen.federation.rollup.v1":
        raise ValueError("G1 report source schema mismatch")
    if (stat.get("repositories"), stat.get("target_repo_surface_cells"),
        stat.get("source_discovered_cells"), stat.get("native_status_verified_cells"),
        stat.get("artifact_bytes_verified_cells"), stat.get("unknown_cells")) != (6, 66, 13, 0, 0, 53):
        raise ValueError("source cohort/depth/unknown denominator mismatch")
    if body.get("authority_transfer") is not False or body.get("merge_authorized") is not False:
        raise ValueError("source report claims owner authority")
    html_data = members["rollup.html"].decode("utf-8")
    if expected_source_sha not in html_data or "13/66" not in html_data or "DEFER" not in html_data:
        raise ValueError("HTML source/view parity mismatch")
    for name in ("source_tests.log", "html_tests.log"):
        if b"\nOK" not in members[name]:
            raise ValueError("native unittest log not successful")
    return {"schema": SCHEMA, "producer": {
                "repository": "GBOGEB/pipeline-automation-hub",
                "head_sha": expected_source_sha, "run_id": expected_run_id,
                "job_id": expected_job_id, "run_attempt": 1,
                "archive_sha256": expected_archive_sha256,
                "rollup_sha256": _sha(members["rollup.json"]),
                "html_sha256": _sha(members["rollup.html"])},
            "consumer": {"status": "VERIFIED_DOWNLOADED_BYTES",
                         "proof_kind": "SAME_REPO_CROSS_PR_PRODUCER_TO_CONSUMER"},
            "verified_producer_to_consumer_links": 1,
            "cross_repository_federation_links": 0,
            "qps_recipient_accepted_links": 0,
            "global_causal_root_closure": None,
            "worker_dispatches": 0,
            "authority_transfer": False, "merge_authorized": False,
            "qps_disposition": "DEFER"}


def emit(result, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
    digest = _sha(data)
    (directory / "g1_consumer_receipt.json").write_bytes(data)
    (directory / "g1_consumer_receipt.sha256").write_text(digest + "\n", encoding="ascii")
    (directory / "g1_consumer_receipt.md").write_text(
        "# G1 → G5 consumer-replay proof\n\n"
        "One pinned GitHub producer ZIP has been independently downloaded and "
        "byte-verified by the G5 consumer.\n\n"
        "Same-repository producer→consumer links: **1**. "
        "Cross-repository consumer hops: **0**. "
        "QPS ACCEPT: **0**. Admission: **HOLD**.\n\n"
        "SHA-256: " + digest + "\n", encoding="utf-8")
    prod = result["producer"]
    # All interpolated identifiers are validated immutable integers/hex strings.
    page = ("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark light"><title>CODE PURPLE — G1 to G5 consumer evidence</title>
<style>
:root{color-scheme:dark;--bg:#0c0c0c;--fg:#fafafa;--dim:#b6b6b6;--line:#414141}
*{box-sizing:border-box}body{background:var(--bg);color:var(--fg);margin:0;font:15px/1.5 system-ui,sans-serif}
main{max-width:1050px;margin:auto;padding:28px 20px;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.card{padding:16px;border:1px solid var(--line);border-radius:9px}.big{font-size:1.9rem;font-weight:800}
.dim{color:var(--dim);font-size:.87rem}h1{font-size:1.55rem}a{color:inherit;overflow-wrap:anywhere}
footer{border-top:1px solid var(--line);margin-top:26px;padding-top:18px;overflow-wrap:anywhere}
@media(prefers-color-scheme:light){:root{--bg:white;--fg:#171717;--dim:#555;--line:#ccc}}
</style></head><body><main><h1>G1 → G5 · independently replayed producer bytes</h1>
<p>One pinned, same-repository producer archive passed strict consumer-side byte and manifest checks.
This does not establish any cross-repository KEB/DOW/QPS ACCEPT.</p>
<div class="grid"><section class="card"><div class="dim">Same-repository consumer proof</div><div class="big">1</div>
</section><section class="card"><div class="dim">Cross-repository authenticated hops</div><div class="big">0</div>
</section><section class="card"><div class="dim">QPS accepted links</div><div class="big">0</div></section></div>
<h2>Provenance</h2>
<p>Producer SHA: <code>""" + prod["head_sha"] + """</code></p>
<p>Run: <a href="https://github.com/GBOGEB/pipeline-automation-hub/actions/runs/""" +
str(prod["run_id"]) + """">""" + str(prod["run_id"]) + """</a>; job """ + str(prod["job_id"]) + """</p>
<p>Downloaded ZIP SHA-256: <code>""" + prod["archive_sha256"] + """</code></p>
<p>JSON source SHA-256: <code>""" + prod["rollup_sha256"] + """</code></p>
<p>HTML source SHA-256: <code>""" + prod["html_sha256"] + """</code></p>
<footer>Admission: HOLD · QPS: DEFER · authority transfer: false · consumer proof SHA-256:
<code>""" + digest + """</code><p>Review derivative only — the SSOT stays at its owner.</p></footer>
</main></body></html>""")
    (directory / "g1_consumer_receipt.html").write_text(page, encoding="utf-8")
    return digest


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--zip", type=Path, required=True)
    p.add_argument("--archive-sha256", required=True)
    p.add_argument("--source-sha", required=True)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--job-id", type=int, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    data = validate_archive(a.zip.read_bytes(),
          expected_archive_sha256=a.archive_sha256, expected_source_sha=a.source_sha,
          expected_run_id=a.run_id, expected_job_id=a.job_id)
    digest = emit(data, a.out)
    print(json.dumps({"schema": SCHEMA, "consumer_proof": "PASS",
                      "sha256": digest, "merge_authorized": False}, sort_keys=True))


if __name__ == "__main__":
    main()
