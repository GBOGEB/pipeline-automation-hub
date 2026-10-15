# Corporate document-control boundary

This project uses its own descriptive brand **MISSION CONTROL / CODE PURPLE**. It does not claim to be an official ALX or SCK CEN corporate publication, nor reissue engineering specifications under an invented document number.

| Family | Input authority | Output user receives | Control path |
|---|---|---|---|
| SSOT JSON/YAML | Governed Git repository and engineering owner | Machine-readable canonical input identity | PR review and exact SHA |
| Markdown README/runbook | Repo-maintained source | Operator instructions and traceable references | PR review |
| HTML / SVG | Generated from controlled JSON | Navigable review site, process graph, per-leaf evidence | Generated only; source hash + browser QA |
| XLSX | Controlled census data | Editable review workbook, formula+cached KPI cells, linked source rows | Review derivative; no corporate ID |
| DOCX | Controlled census data | Report template | Review derivative; no corporate ID |
| PPTX | Controlled census data | Leadership/engineering briefing deck | Review derivative; no corporate ID |
| PDF | Controlled census data | Fixed evidence book with clickable TOC and references | Review derivative; not full interactive UI |
| Original USER binaries | User-approved corporate document repository | Original XLSX/DOCX/PDF input, if any | **Preserve unchanged**; generator reads structured SSOT rather than editing corporate originals |

**Procedure:** the document owner resolves a real controlled document number, version, reviewer, signature and effective status in the official document management system. The generator may then reference those IDs as external fields in a governed source update; it cannot grant or fabricate them. The corporate-original binary (if available) stays unchanged; regenerated views carry explicit source digests and derived-data classification.

An Office/PDF download can be very useful without being a corporate-approved released document. Browser-side notes are exported as user review suggestions and should be reconciled into the source by a controlled PR or official doc-control workflow.