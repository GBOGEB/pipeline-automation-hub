"""Build local, inert P0009 handover without network or authority transfer."""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build(out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    evidence = json.loads((HERE / "POSTMERGE_AUDIT.json").read_text(encoding="utf-8"))
    cols = ["number", "head_sha", "merge_commit_sha", "merged_at",
            "fpc_failure_at", "fpc_failure_run", "approved_review_count",
            "historical_outcome"]
    with (out / "PR_MERGE_MATRIX.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(evidence["rows"])
    data = json.dumps(evidence, separators=(",", ":"), ensure_ascii=True).replace("<", "\\u003c")
    page = """<!doctype html><html lang="en"><meta charset="utf-8">
<title>GM-I-C P0009 | Exact-head audit</title>
<style>body{font:15px Aptos,system-ui,sans-serif;background:#180d22;color:#f8eafa;max-width:1200px;margin:auto;padding:24px}h1{color:#ebc7fc}button{padding:10px;background:#9435a4;color:white;border:0;border-radius:7px;margin-right:7px}table{border-collapse:collapse;width:100%%;margin-top:18px}td,th{padding:10px;text-align:left;border-bottom:1px solid #634475}th{background:#482653}.muted{color:#d9bce4}</style>
<h1>GM-I-C | P0009 post-merge admission evidence</h1>
<p class="muted">Offline snapshot. No direct GitHub API, reviewer or merge authority.</p>
<p id="count">10 selected PRs with pre-merge trusted RED status; 0 APPROVED reviews.</p>
<button id="reset">Reload bundled snapshot</button><button id="import">Import updated JSON</button><button id="export">Export displayed JSON</button>
<input type="file" id="file" hidden accept=".json,application/json">
<p id="stamp" class="muted">Source capture: 2026-11-12</p>
<table><thead><tr><th>PR</th><th>Exact head</th><th>Trusted RED observed at</th><th>Merge timestamp</th></tr></thead><tbody id="rows"></tbody></table>
<script type="application/json" id="audit">%s</script>
<script>
const frozen=JSON.parse(document.getElementById('audit').textContent);
let current=frozen;
function draw(x){
  const body=document.getElementById('rows');body.textContent='';
  for(const item of x.rows){const tr=document.createElement('tr');for(const value of ['#'+item.number,item.head_sha.slice(0,12),item.fpc_failure_at,item.merged_at]){const cell=document.createElement('td');cell.textContent=value;tr.appendChild(cell)}body.appendChild(tr)}
  document.getElementById('count').textContent=x.rows.length+' observed pre-merge FPC failures; '+x.approved_review_count+' recorded APPROVED reviews';
  document.getElementById('stamp').textContent=x.capture_date+' | Hub '+x.observed_master_sha.slice(0,12)+' | not live provider data';
}
document.getElementById('reset').onclick=()=>{current=frozen;draw(current)};
document.getElementById('import').onclick=()=>document.getElementById('file').click();
document.getElementById('file').onchange=async e=>{const f=e.target.files[0];if(!f)return;try{const parsed=JSON.parse(await f.text());if(parsed.schema!==frozen.schema||parsed.merge_admission_authorized!==false||parsed.authority_transfer!==false||!Array.isArray(parsed.rows))throw Error('not an inert P0009 snapshot');current=parsed;draw(current)}catch(e){alert('Rejected: '+e.message)}};
document.getElementById('export').onclick=()=>{const blob=new Blob([JSON.stringify(current,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const anchor=document.createElement('a');anchor.href=url;anchor.download='GMIC_P0009_VIEW.json';anchor.click();URL.revokeObjectURL(url)};
draw(current);
</script></html>""" % data
    (out / "index.html").write_text(page, encoding="utf-8")
    names = ["POSTMERGE_AUDIT.json", "DAG.json", "DAG.mmd",
             "README.md", "test_p0009.py", "build_p0009.py"]
    sources = {name: (HERE / name).read_bytes() for name in names}
    sources["PR_MERGE_MATRIX.csv"] = (out / "PR_MERGE_MATRIX.csv").read_bytes()
    sources["index.html"] = (out / "index.html").read_bytes()
    manifest = {
        "schema": "missioncontrol.gmic_p0009.release.v1",
        "sha256": {key: hashlib.sha256(value).hexdigest()
                   for key, value in sorted(sources.items())},
        "source_master_sha": evidence["observed_master_sha"],
        "merge_authorized": False,
        "authority_transfer": False,
    }
    sources["RELEASE_MANIFEST.json"] = (
        json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()
    archive = out / "GMIC_P0009_POSTMERGE_EVIDENCE.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for name, value in sorted(sources.items()):
            output.writestr(name, value)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (out / (archive.name + ".sha256")).write_text(
        f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    print(build(ap.parse_args().out))
