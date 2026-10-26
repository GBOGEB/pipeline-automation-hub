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

REDTRACE_REQUIRED={'redtrace.html','redtrace-slides.html','redtrace-slides.pdf','redtrace-manifest.json'}
REDTRACE_SOURCES={'data/RED_TRACE_FEDERATION_N8.json','data/GAP_ANALYSIS_N8.json'}
REDTRACE_PDF_MAX=2_000_000

def stage_redtrace(project_root, output_root, portal_hashes):
    """Fail-closed optional N+8 red-trace child: ledger page, 16:9 slides, interactive PDF.

    HTML/manifest bytes are deterministic and digest-bound to the committed sources; the PDF
    (Chromium print, not byte-deterministic) is bound by magic, size bound and the slide
    count recorded in the manifest outline, and is published byte-for-byte as committed."""
    project_root,output_root=Path(project_root),Path(output_root)
    site=project_root/'site'
    names={x for x in REDTRACE_REQUIRED if (site/x).exists()}
    if not names:
        return 0
    if names!=REDTRACE_REQUIRED:
        raise ValueError('JADE_N8_PARTIAL_SITE')
    m=json.loads((site/'redtrace-manifest.json').read_text('utf-8'))
    if not (m.get('schema')=='jade.temple.redtrace_manifest.v1'
            and m.get('merge_authorized') is False
            and m.get('pdf',{}).get('file')=='redtrace-slides.pdf'
            and set(m.get('public_files_sha256',{}))=={'redtrace.html','redtrace-slides.html'}
            and set(m.get('sources_sha256',{}))==REDTRACE_SOURCES
            and isinstance(m.get('slide_outline'),list) and m['slide_outline']):
        raise ValueError('JADE_N8_UNSAFE_MANIFEST')
    for rel,want in m['sources_sha256'].items():
        if not SHA256.fullmatch(want) or sha256(project_root/rel)!=want:
            raise ValueError('JADE_N8_SOURCE_DIGEST_DRIFT: '+rel)
    for name,want in m['public_files_sha256'].items():
        src=site/name
        if not SHA256.fullmatch(want) or src.is_symlink() or not src.is_file() or sha256(src)!=want:
            raise ValueError('JADE_N8_STATIC_DIGEST_DRIFT: '+name)
    pdf=site/'redtrace-slides.pdf'
    raw=pdf.read_bytes() if pdf.is_file() and not pdf.is_symlink() else b''
    if not (raw[:5]==b'%PDF-' and 0<len(raw)<=REDTRACE_PDF_MAX
            and raw.count(b'/Type /Page')-raw.count(b'/Type /Pages')>=len(m['slide_outline'])):
        raise ValueError('JADE_N8_BAD_PDF')
    for name in sorted(REDTRACE_REQUIRED):
        dst=output_root/'jade'/name;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(site/name,dst)
        portal_hashes[dst.relative_to(output_root).as_posix()]=sha256(dst)
    return len(REDTRACE_REQUIRED)

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
        portal_hashes[dst.relative_to(output_root).as_posix()]=sha256(dst)
    return len(BURNDOWN_REQUIRED)

EIGHT_REQUIRED={
    'eightpoint.html','eightpoint.css','eightpoint.js',
    'eightpoint-data.js','eightpoint.json','eightpoint.csv','eightpoint-manifest.json',
}
EIGHT_SOURCES={
    'data/EIGHT_POINT_AUDIT_NPLUS3.json','data/HEAD_RECENSUS_NPLUS3.json',
    'data/CAPABILITY_LEDGER_NPLUS3.json','data/COHORT_CROSSWALK_NPLUS1.json',
    'data/READBACK_NPLUS2.json','tools/eight_point_contract.py',
    'site/eightpoint_template.html',
}

def stage_eight_point(project_root, output_root, portal_hashes):
    """Fail-closed optional N+3 child; no second publisher, no merge authority."""
    project_root,output_root=Path(project_root),Path(output_root)
    site=project_root/'site'
    present={p for p in EIGHT_REQUIRED if (site/p).exists()}
    if not present:return 0  # N+2 predecessor remains replayable
    if present!=EIGHT_REQUIRED:raise ValueError('JADE_EIGHT_PARTIAL_SITE')
    m=json.loads((site/'eightpoint-manifest.json').read_text('utf-8'))
    if not (m.get('schema')=='jade.temple.eightpoint_manifest.v3'
            and m.get('publisher')=='EXISTING_METHOD_ATLAS_PAGES_ONLY'
            and m.get('merge_admission')=='HOLD'
            and m.get('security_waiver') is False
            and m.get('authority_transfer') is False
            and m.get('hosted_eightpoint_sha') is None
            and m.get('static_population')==6
            and m.get('controlled_ids')==['J%02d'%i for i in range(1,9)]
            and m.get('repo_count')==21
            and set(m.get('public_files_sha256',{}))==EIGHT_REQUIRED-{'eightpoint-manifest.json'}
            and set(m.get('source_files_sha256',{}))==EIGHT_SOURCES):
        raise ValueError('JADE_EIGHT_UNSAFE_MANIFEST')
    for rel,want in m['source_files_sha256'].items():
        if not SHA256.fullmatch(want) or sha256(project_root/rel)!=want:
            raise ValueError('JADE_EIGHT_SOURCE_DIGEST_DRIFT: '+rel)
    projection=json.loads((site/'eightpoint.json').read_text('utf-8'))
    if not (projection.get('schema')=='jade.temple.eightpoint_projection.v3'
            and projection.get('merge_admission')=='HOLD'
            and projection.get('authority_transfer') is False
            and projection.get('security_waiver') is False
            and projection.get('hosted_nplus3_verified') is None
            and projection.get('formal_point_release') is None
            and len(projection.get('sections',[]))==8
            and len(projection.get('rows',[]))==21
            and projection.get('metrics',{}).get('action_open')==21
            and projection.get('metrics',{}).get('action_owner_closed')==0):
        raise ValueError('JADE_EIGHT_UNSAFE_PROJECTION')
    for rel,want in m['public_files_sha256'].items():
        src=site/rel
        if not SHA256.fullmatch(want) or src.is_symlink() or not src.is_file() or sha256(src)!=want:
            raise ValueError('JADE_EIGHT_STATIC_DIGEST_DRIFT: '+rel)
    for name in sorted(EIGHT_REQUIRED):
        src=site/name
        if src.is_symlink() or not src.is_file():raise ValueError('JADE_EIGHT_MISSING_ASSET: '+name)
        dst=output_root/'jade'/name
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,dst)
        portal_hashes[dst.relative_to(output_root).as_posix()]=sha256(dst)
    return len(EIGHT_REQUIRED)

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
        portal_hashes[dst.relative_to(output_root).as_posix()]=sha256(dst)
    n2_assets=stage_burndown(project_root,output_root,portal_hashes)
    n3_assets=stage_eight_point(project_root,output_root,portal_hashes)
    n8_assets=stage_redtrace(project_root,output_root,portal_hashes)
    proof={'schema':'jade.temple.pages_bridge.v1','presentation_head':source_sha,
        'publisher':'EXISTING_METHOD_ATLAS_PAGES_ONLY','merge_admission':'HOLD',
        'authority_transfer':False,'security_waiver':False,
        'hosted_http_verified':False,'native_release_admission':None,
        'site_manifest_sha256':sha256(site/'site-manifest.json'),
        'cohort_overlap':[13,21],'repository_count':21,
        'files_in_pages':len(STATIC_REQUIRED)+n2_assets+n3_assets+n8_assets,
        'burndown_assets_in_pages':n2_assets,'eightpoint_assets_in_pages':n3_assets,
        'redtrace_assets_in_pages':n8_assets}
    dst=output_root/'jade'/'publisher-receipt.json'
    dst.write_text(json.dumps(proof,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    portal_hashes[dst.relative_to(output_root).as_posix()]=sha256(dst)
    return proof
