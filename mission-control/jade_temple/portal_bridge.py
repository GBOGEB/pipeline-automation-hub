"""Stage JADE as a hashed child of the EXISTING Mission Control Pages publisher.

This module only packages source-validated static files. It does not deploy,
dispatch, merge, change rulesets, or qualify hosted HTTP/Pages acceptance.
"""
import hashlib, json, re, shutil
from pathlib import Path

STATIC_REQUIRED={
    'index.html','green.html','jade.css','jade.js','jade_data.js',
    'snapshot.json','top21_bd_queue.csv','site-manifest.json',
}
BURNDOWN_REQUIRED={
    'burndown.html','burndown.css','burndown.js',
    'burndown-data.js','burndown.json','burndown.csv','burndown-manifest.json',
}
BURNDOWN_SOURCES={
    'data/READBACK_NPLUS2.json','data/EVIDENCE_EVENTS_NPLUS2.json',
    'data/STOP_MODEL_NPLUS2.json','data/REPO_READINESS_NPLUS1.json',
}

def stage_burndown(project_root, output_root, portal_hashes):
    """Fail-closed optional N+2 child, no new publisher or admission claim."""
    project_root,output_root=Path(project_root),Path(output_root)
    site=project_root/'site'
    names={x for x in BURNDOWN_REQUIRED if (site/x).exists()}
    if not names:
        return 0  # old N+1 fixture/archived source remains replayable
    if names!=BURNDOWN_REQUIRED:
        raise ValueError('JADE_N2_PARTIAL_SITE')
    m=json.loads((site/'burndown-manifest.json').read_text('utf-8'))
    if not (m.get('schema')=='jade.temple.burndown_manifest.v2'
        and m.get('publisher')=='EXISTING_METHOD_ATLAS_PAGES_ONLY'
        and m.get('merge_admission')=='HOLD'
        and m.get('security_waiver') is False
        and m.get('authority_transfer') is False
        and m.get('hosted_sha') is None
        and m.get('static_population')==6
        and set(m.get('public_files_sha256',{}))==BURNDOWN_REQUIRED-{'burndown-manifest.json'}
        and set(m.get('source_files_sha256',{}))==BURNDOWN_SOURCES):
        raise ValueError('JADE_N2_UNSAFE_MANIFEST')
    for rel,want in m['source_files_sha256'].items():
        if not SHA256.fullmatch(want) or sha256(project_root/rel)!=want:
            raise ValueError('JADE_N2_SOURCE_DIGEST_DRIFT: '+rel)
    d=json.loads((site/'burndown.json').read_text('utf-8'))
    if not (d.get('schema')=='jade.temple.burndown_projection.v2'
            and d.get('merge_admission')=='HOLD'
            and d.get('authority_transfer') is False
            and d.get('security_waiver') is False
            and len(d.get('rows',[]))==21
            and d.get('controller',{}).get('merge_admission')=='HOLD'
            and d.get('metrics',{}).get('owner_causal_roots_qualified')==0
            and d.get('metrics',{}).get('hosted_jade_qualified') is None):
        raise ValueError('JADE_N2_UNSAFE_PROJECTION')
    for name,want in m['public_files_sha256'].items():
        src=site/name
        if not SHA256.fullmatch(want) or src.is_symlink() or not src.is_file() or sha256(src)!=want:
            raise ValueError('JADE_N2_STATIC_DIGEST_DRIFT: '+name)
    for name in sorted(BURNDOWN_REQUIRED):
        src=site/name
        if src.is_symlink() or not src.is_file():
            raise ValueError('JADE_N2_MISSING_ASSET: '+name)
        dst=output_root/'jade'/name
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dst)
        portal_hashes[str(dst.relative_to(output_root))]=sha256(dst)
    return len(BURNDOWN_REQUIRED)

SHA40=re.compile(r'^[0-9a-f]{40}$')
SHA256=re.compile(r'^[0-9a-f]{64}$')
def sha256(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def stage_jade(project_root, output_root, portal_hashes, source_sha):
    project_root,output_root=Path(project_root),Path(output_root)
    site=project_root/'site'
    if not SHA40.fullmatch(source_sha):raise ValueError('SOURCE_SHA_INVALID')
    receipt=json.loads((site/'site-manifest.json').read_text('utf-8'))
    if not (receipt.get('schema')=='jade.temple.static_manifest.v1'
            and receipt.get('publisher')=='EXISTING_METHOD_ATLAS_PAGES_ONLY'
            and receipt.get('merge_admission')=='HOLD'
            and receipt.get('security_waiver') is False
            and receipt.get('authority_transfer') is False
            and receipt.get('no_second_publisher') is True
            and receipt.get('hosted_parity_receipt') is None
            and receipt.get('served_http_sha') is None):
        raise ValueError('JADE_UNSAFE_PUBLICATION_CLAIM')
    names=set(receipt.get('public_files_sha256',{}))
    if names != STATIC_REQUIRED-{'site-manifest.json'}:raise ValueError('JADE_UNEXPECTED_STATIC_POPULATION')
    for rel,want in receipt['source_files_sha256'].items():
        if rel not in {'data/REPO_READINESS_NPLUS1.json','data/COHORT_CROSSWALK_NPLUS1.json','data/GLOBAL_METRICS_NPLUS1.json'} or not SHA256.fullmatch(want):
            raise ValueError('JADE_UNSAFE_INPUT_SOURCE')
        if sha256(project_root/rel)!=want:raise ValueError('JADE_SOURCE_DIGEST_DRIFT')
    snapshot=json.loads((site/'snapshot.json').read_text('utf-8'))
    if not (snapshot.get('schema')=='jade.temple.presentation.v1'
            and snapshot.get('admission')=='HOLD'
            and snapshot.get('authority_transfer') is False
            and snapshot.get('security_waiver') is False
            and len(snapshot.get('rows',[]))==21
            and snapshot.get('crosswalk',{}).get('intersection_count')==13):
        raise ValueError('JADE_BAD_PUBLICATION_SNAPSHOT')
    for name,want in receipt['public_files_sha256'].items():
        src=site/name
        if not SHA256.fullmatch(want) or not src.is_file() or src.is_symlink() or sha256(src)!=want:
            raise ValueError('JADE_STATIC_SHA256_MISMATCH: '+name)
    for name in STATIC_REQUIRED:
        src=site/name
        if not src.is_file() or src.is_symlink():raise ValueError('JADE_STATIC_MISSING: '+name)
        dst=output_root/'jade'/name;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dst)
        portal_hashes[str(dst.relative_to(output_root))]=sha256(dst)
    n2_assets=stage_burndown(project_root,output_root,portal_hashes)
    proof={'schema':'jade.temple.pages_bridge.v1','presentation_head':source_sha,
        'publisher':'EXISTING_METHOD_ATLAS_PAGES_ONLY','merge_admission':'HOLD',
        'authority_transfer':False,'security_waiver':False,
        'hosted_http_verified':False,'native_release_admission':None,
        'site_manifest_sha256':sha256(site/'site-manifest.json'),
        'cohort_overlap':[13,21],'repository_count':21,
        'files_in_pages':len(STATIC_REQUIRED)+n2_assets,'burndown_assets_in_pages':n2_assets}
    dst=output_root/'jade'/'publisher-receipt.json'
    dst.write_text(json.dumps(proof,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    portal_hashes[str(dst.relative_to(output_root))]=sha256(dst)
    return proof
