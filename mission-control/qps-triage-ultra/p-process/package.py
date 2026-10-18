#!/usr/bin/env python3
"""Package site/ into a deterministic zip: dist/p-process-site-<census>.zip (+ .sha256).

Verifies every file against site/manifest.json first, so a zip is never built from a half-refreshed site.
Usage: python package.py [--out DIR]
"""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
EPOCH = (2026, 1, 1, 0, 0, 0)  # fixed timestamps: same site -> byte-identical zip


def build(out_dir: Path) -> Path:
    man = json.loads((SITE / "manifest.json").read_text())
    for rel, h in man["files_sha256"].items():
        if hashlib.sha256((SITE / rel).read_bytes()).hexdigest() != h:
            raise SystemExit(f"site/{rel} does not match manifest: run refresh.py first")
    stamp = man["census_at"][:16].replace(":", "").replace("-", "").replace("T", "-")
    out_dir.mkdir(parents=True, exist_ok=True)
    z = out_dir / f"p-process-site-{stamp}Z.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in sorted([*man["files_sha256"], "manifest.json"]):
            info = zipfile.ZipInfo(f"p-process/{rel}", EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, (SITE / rel).read_bytes())
    digest = hashlib.sha256(z.read_bytes()).hexdigest()
    (z.parent / (z.name + ".sha256")).write_text(f"{digest}  {z.name}\n")
    print(json.dumps({"zip": str(z), "files": len(man["files_sha256"]) + 1, "sha256": digest}))
    return z


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"))
    build(Path(ap.parse_args().out))
