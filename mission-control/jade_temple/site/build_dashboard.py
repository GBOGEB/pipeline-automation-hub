#!/usr/bin/env python3
"""Offline deterministic JADE read-only dashboard built solely from the dated snapshot."""
from pathlib import Path
import json, sys, re, hashlib, importlib.util
ROOT=Path(__file__).resolve().parents[1]
_pb=importlib.util.spec_from_file_location('jade_private_boundary',ROOT/'tools/private_boundary.py');PB=importlib.util.module_from_spec(_pb);_pb.loader.exec_module(PB)
DATA=ROOT/'data'/'TOP21_PORTFOLIO.json'
TEMPLATE=ROOT/'site'/'template.html'
OUTPUT=ROOT/'site'/'index.html'
def generate():
    d=json.loads(DATA.read_text('utf-8'))
    assert d['schema']=='jade_temple.top21.observation.v0'
    assert d['merge_admission']=='HOLD' and d['authority_transfer'] is False
    assert len(d['repositories'])==21
    assert len({x['repo'] for x in d['repositories']})==21
    assert all((re.fullmatch(r'[0-9a-f]{40}',x['commit_sha_observed']) or x['commit_sha_observed']==PB.MARK) for x in d['repositories'])
    assert sum(x['n11_historical']['files'] for x in d['repositories'])==26836
    assert sum(x['n11_historical']['root_files'] for x in d['repositories'])==880
    assert sum(x['n11_historical']['root_review_candidates'] for x in d['repositories'])==706
    assert all(x['site']['proof_status']=='UNKNOWN' and x['release']['readiness_level']=='UNASSESSED' for x in d['repositories'])
    inline=json.dumps(d,ensure_ascii=True,separators=(',',':'),sort_keys=True).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    template=TEMPLATE.read_text('utf-8')
    if template.count('/*__JADE_DATA__*/')!=1:raise ValueError('invalid template sentinel')
    html=template.replace('/*__JADE_DATA__*/',inline)
    return html.encode('utf-8')
if __name__=='__main__':
    data=generate()
    if '--check' in sys.argv:
        if not OUTPUT.exists() or OUTPUT.read_bytes()!=data:raise SystemExit('FAIL: HTML is not current/deterministic')
        print('PASS deterministic',hashlib.sha256(data).hexdigest())
    else:
        OUTPUT.write_bytes(data)
        print('built',OUTPUT,'sha256',hashlib.sha256(data).hexdigest())
