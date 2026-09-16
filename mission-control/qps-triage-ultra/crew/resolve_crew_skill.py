#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

ALLOWED = {"math", "plots", "math-plots"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--skills-root", type=Path, required=True)
    p.add_argument("--skill", choices=sorted(ALLOWED), required=True)
    p.add_argument("--task-id", required=True)
    p.add_argument("--source-repo", required=True)
    p.add_argument("--source-ref", required=True)
    p.add_argument("--skills-ref", default="UNSPECIFIED")
    p.add_argument("--resolution-mode", default="missioncontrol_resolver")
    p.add_argument("--out", type=Path)
    ns = p.parse_args()

    skill_dir = ns.skills_root / "skills" / ns.skill
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise SystemExit(f"missing skill entrypoint: {skill_md}")
    raw = skill_md.read_bytes()
    text = raw.decode("utf-8")
    if f"name: {ns.skill}" not in text:
        raise SystemExit("skill frontmatter name mismatch")
    if not (skill_dir / "agents" / "openai.yaml").is_file():
        raise SystemExit("missing agents/openai.yaml")

    receipt = {
        "schema": "missioncontrol.crew.skill_resolution_receipt.v1",
        "skill": ns.skill,
        "task_id": ns.task_id,
        "source_repo": ns.source_repo,
        "source_ref": ns.source_ref,
        "skills_repo": "GBOGEB/skills",
        "skills_ref": ns.skills_ref,
        "resolution_mode": ns.resolution_mode,
        "resolved_skill_path": f"skills/{ns.skill}/SKILL.md",
        "entrypoint_sha256": hashlib.sha256(raw).hexdigest(),
        "authority_transfer": False,
        "status": "PASS_SKILL_BUNDLE_RESOLUTION"
    }
    payload = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if ns.out:
        ns.out.parent.mkdir(parents=True, exist_ok=True)
        ns.out.write_text(payload, encoding="utf-8")
    print(payload, end="")


if __name__ == "__main__":
    main()
