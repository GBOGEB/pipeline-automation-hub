"""Read-only additive GM-I-C postmerge projection. No scheduler or admission authority."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
HIST = ROOT / 'mission-control/v2/handoff/closeout/w11-gmic-r2-p0008/BD_B01_B46_READONLY.json'
WITNESS = HERE / 'POSTMERGE_WITNESS.json'
MANIFEST = HERE / 'RELEASE_MANIFEST.json'
SHA = re.compile(r'^[0-9a-f]{40}$')
HEX64 = re.compile(r'^[0-9a-f]{64}$')
# Git blob OID of the frozen P0008 B01-B46 projection. Historical evidence: never re-pin to later progress.
FROZEN_BLOB = '48106d26a1db49317a20b91105ccb2a76237abad'
PINNED_FIELDS = ('id', 'priority', 'state', 'minimum_dod_dov')


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()


def load_frozen_rows(path: Path = HIST) -> dict:
    """Return the pinned per-row map, refusing any projection whose bytes differ from the frozen blob."""
    raw = path.read_bytes()
    oid = git_blob_sha(raw)
    assert oid == FROZEN_BLOB, f'frozen B01-B46 projection drifted: {oid} != {FROZEN_BLOB}'
    items = json.loads(raw.decode('utf-8'))['items']
    rows = {x['id']: tuple(x[k] for k in PINNED_FIELDS) for x in items}
    assert len(rows) == len(items) == 46
    return rows


def verify_manifest(manifest: dict, base: Path = HERE) -> None:
    """Every manifest member must exist under base and match its sha256; no external or nested paths."""
    files = manifest['files_sha256']
    assert files, 'empty release manifest'
    for name, digest in files.items():
        assert name and '/' not in name and '\\' not in name and name not in ('.', '..'), f'bad member {name!r}'
        assert HEX64.fullmatch(digest), f'bad digest for {name}'
        target = base / name
        assert target.is_file(), f'release member missing: {name}'
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        assert actual == digest, f'checksum mismatch for {name}: {actual} != {digest}'


def project(baseline: dict, witness: dict, frozen: dict | None = None) -> dict:
    """Project new evidence, never promote B closure based on merged source alone."""
    if frozen is None:
        frozen = load_frozen_rows()
    items = baseline['items']
    assert [x['id'] for x in items] == [f'B{i:02d}' for i in range(1, 47)]
    for x in items:
        got = tuple(x.get(k) for k in PINNED_FIELDS)
        assert got == frozen.get(x['id']), f'historical row {x["id"]} differs from frozen projection'
    assert len(items) == 46
    assert baseline['counts']['done'] == 22
    assert baseline['counts']['open'] == 24
    assert sum(x['state'] == 'DONE' for x in items[:38]) == 20
    assert witness['schema'] == 'missioncontrol.gmic.postmerge-witness.v1'
    assert SHA.fullmatch(witness['source_head'])
    assert witness['historical_counts'] == {
        'total': 46, 'done': 22, 'open': 24, 'original_cohort_open': 18,
    }
    assert witness['controls']['authority_transfer'] is False
    assert witness['controls']['formal_credit_delta'] == 0
    assert witness['controls']['merge_admission_retroactively_verified'] is False
    assert witness['controls']['ic3_hosted_pass_verified'] is False
    assert witness['controls']['wire_owner_decision_verified'] is False
    known = {item['id'] for item in items}
    overlays = {item['id']: [] for item in items}
    prs = set()
    for pr in witness['commit_observations']:
        assert isinstance(pr['pr'], int) and pr['pr'] not in prs
        prs.add(pr['pr'])
        assert SHA.fullmatch(pr['head']) and SHA.fullmatch(pr['merge'])
        assert pr['approved_reviews_observed'] >= 0
        for bid in pr['b_items']:
            assert bid in known
            overlays[bid].append({
                'pr': pr['pr'], 'merge_sha': pr['merge'],
                'phase': 'MERGED_SOURCE_REVIEW_PROOF_MISSING'
                if pr['approved_reviews_observed'] == 0 else 'MERGED_REVIEW_EVIDENCE_RECHECK',
            })
    out = []
    for item in items:
        row = dict(item)
        row['historical_state'] = item['state']
        row['current_phase_observation'] = overlays[item['id']]
        row['status_authority'] = 'HISTORICAL_FROZEN_UNCHANGED'
        out.append(row)
    return {
        'schema': 'missioncontrol.gmic.p0009-postmerge-readonly.v1',
        'observation_date': witness['observed_date'],
        'observed_master': witness['source_head'],
        'baseline_source': witness['historical_projection'],
        'historic_counts': baseline['counts'],
        'current_parent_closure_count_verified': None,
        'historical_unchanged_46': out,
        'governance_audit': witness['commit_observations'],
        'controls': witness['controls'],
        'nonclaims': [
            'NO_LIVE_CLOSURE_COUNT_INFERRED_FROM_MERGED_PR',
            'NO_FPC_SUCCESS_INFERRED_FROM_OLD_HEAD',
            'NO_RETROACTIVE_INDEPENDENT_APPROVAL',
            'NO_HOSTED_WIF_OR_IC3_CREDIT',
            'NO_WIRE_CHOICE_ON_OWNER_BEHALF',
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--baseline', type=Path, default=HIST)
    p.add_argument('--witness', type=Path, default=WITNESS)
    p.add_argument('--manifest', type=Path, default=MANIFEST)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    verify_manifest(json.loads(args.manifest.read_text(encoding='utf-8')), args.manifest.parent)
    baseline = json.loads(args.baseline.read_text(encoding='utf-8'))
    witness = json.loads(args.witness.read_text(encoding='utf-8'))
    snapshot = project(baseline, witness)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'POSTMERGE_PROJECTION.json').write_text(json.dumps(snapshot, indent=2, sort_keys=True) + '\n', encoding='utf-8', newline='\n')
    with (args.out / 'POSTMERGE_B46.csv').open('w', encoding='utf-8', newline='\n') as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(['id', 'priority', 'historical_state', 'source_merge_prs', 'current_phase'])
        for row in snapshot['historical_unchanged_46']:
            witness_rows = row['current_phase_observation']
            writer.writerow([row['id'], row['priority'], row['historical_state'],
                             ';'.join(str(x['pr']) for x in witness_rows),
                             ';'.join(x['phase'] for x in witness_rows)])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
