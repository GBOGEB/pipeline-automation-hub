"""W35 typed DAG, SIPOC lanes, group-lasso and Mermaid outward adapters.

Source-only graph layouts; no live orchestration, QPS private payloads,
new authority, synthetic timestamps or coverage credit. The exact same
node/edge identities are used by SVG, HTML and Mermaid.
"""
from __future__ import annotations

import html
import json
import re
import textwrap
from collections import Counter
from pathlib import Path

GROUP_SCHEMA = 'missioncontrol.superstitch.groups.v1'
METRIC_REFS = frozenset({'census', 'authenticated', 'statements', 'branches', 'alias_topology'})
GROUP_KINDS = frozenset({'OWNER_LANE', 'CROSS_DAG'})
NODE_ID = re.compile(r'^[a-z0-9][a-z0-9-]{1,62}$')


def validate_groups(bundle: dict, model: dict) -> dict:
    if (bundle.get('schema') != GROUP_SCHEMA or bundle.get('mode') != 'READ_ONLY_PROJECTION'
            or bundle.get('admission') != 'HOLD' or bundle.get('runtime_dispatch') is not False
            or bundle.get('authority_transfer') is not False
            or bundle.get('merge_approval') is not None
            or bundle.get('classification') != 'PUBLIC_ROLE_METADATA_ONLY'):
        raise ValueError('GROUP_AUTHORITY_OR_SCHEMA_PROMOTION')
    valid_nodes = {n['id']: n for n in model['nodes']}
    valid_metrics = model['observations']
    if not valid_metrics['historical_six_repo_breadth']['observed'] == 6:
        raise ValueError('INVENTED_HISTORICAL_CENSUS')
    if not valid_metrics['authenticated_codex_qps_pairs']['observed'] == 0:
        raise ValueError('INVENTED_OWNER_ACCEPTANCE')
    all_groups = bundle.get('groups')
    if not isinstance(all_groups, list) or not 6 <= len(all_groups) <= 20:
        raise ValueError('GROUP_COUNT_UNBOUNDED')
    seen = set()
    sipoc_rows = set()
    group_sipoc_ids = []
    for group in all_groups:
        ident = group.get('id')
        if not isinstance(ident, str) or not NODE_ID.fullmatch(ident) or ident in seen:
            raise ValueError('DUPLICATED_OR_INVALID_GROUP_ID')
        seen.add(ident)
        members = group.get('nodes')
        if (group.get('kind') not in GROUP_KINDS or not isinstance(members, list)
                or len(members) < 2 or len(members) != len(set(members))
                or not set(members).issubset(valid_nodes)):
            raise ValueError('NON_SOURCE_BOUND_LASSO_MEMBERS')
        metrics = group.get('metric_refs')
        if not isinstance(metrics, list) or len(metrics) != len(set(metrics)) or not set(metrics).issubset(METRIC_REFS):
            raise ValueError('INVALID_CROSS_SCOPE_BURNDOWN_METRIC')
        if group['kind'] == 'OWNER_LANE' and len({valid_nodes[n]['lane'] for n in members}) != 1:
            raise ValueError('OWNER_LANE_CROSSES_DOMAIN_BOUNDARY')
        row = group.get('sipoc_row')
        if row is not None:
            if not isinstance(row, int) or not 0 <= row < len(model['sipoc']) or row in sipoc_rows:
                raise ValueError('DUPLICATE_OR_OUT_OF_SCOPE_SIPOC_ROW')
            sipoc_rows.add(row)
            group_sipoc_ids.append(ident)
        if group['id'] == 'federation-touch' and metrics != ['authenticated']:
            raise ValueError('AUTHENTICATED_FEDERATION_DENOMINATOR_REQUIRED')
        if group['id'] == 'math-methods' and metrics != ['statements', 'branches']:
            raise ValueError('MATH_SCOPE_DENOMINATOR_REQUIRED')
        if group['id'] == 'mc-control' and metrics != ['census']:
            raise ValueError('SIX_REPO_BREADTH_SCOPE_REQUIRED')
    if len(sipoc_rows) != len(model['sipoc']):
        raise ValueError('INCOMPLETE_SIPOC_LANE_BINDINGS')
    if not any(g['kind'] == 'CROSS_DAG' for g in all_groups):
        raise ValueError('NO_MULTI_DAG_LASSO_GROUPS')
    if not {n['id'] for n in model['nodes'] if n['status'] == 'ALIAS'}.issubset(
        set(next(g['nodes'] for g in all_groups if g['id'] == 'alias-mycelium'))):
        raise ValueError('DUPLICATED_CANONICAL_PLACEMENTS_MISSING')
    return bundle


def me(s: object) -> str:
    """Escape external sourced content before interpolation in Mermaid syntax."""
    return (str(s).replace('\\', '\\\\').replace('"', "'").replace('\n', ' ')
            .replace('[', '(').replace(']', ')').replace('|', '/').replace('<', '‹').replace('>', '›'))


def mid(s: str) -> str:
    return 'n_' + re.sub(r'[^a-zA-Z0-9_]', '_', s)


def mermaid(model: dict, edges=None, nodes=None, title='W35 Superstitch · proposed') -> str:
    vertices = nodes if nodes is not None else model['nodes']
    keep = {n['id'] for n in vertices}
    segments = [f'%% {me(title)}', '%% DECLARED/ROLE_ONLY/DESIGN_ONLY means planned or source-described, NOT native execution.',
                '%% Internal workflow is acyclic; explicit NEXT-PULSE RETRIGGER is outside the same-wave DAG.', 'flowchart LR']
    for lane in model['lanes']:
        local = [n for n in vertices if n['lane'] == lane['id']]
        if not local:
            continue
        segments.append(f'  subgraph lane_{mid(lane["id"])}["{me(lane["title"])}"]')
        for n in local:
            label = me(n['label'])
            if n['status'] == 'ALIAS':
                label += ' (shared canonical alias)'
            segments.append(f'    {mid(n["id"])}["{label}"]')
        segments.append('  end')
    for e in (edges if edges is not None else model['edges']):
        if e['from'] not in keep or e['to'] not in keep:
            continue
        left = mid(e['from']); right = mid(e['to'])
        typ = e['kind']; binding = e['binding']
        if typ in ('RETRIGGER', 'TOUCH') or binding in ('DECLARED', 'DESIGN_ONLY'):
            segments.append(f'  {left} -. "{me(typ)} / {me(binding)}" .-> {right}')
        else:
            segments.append(f'  {left} -->|"{me(typ)} / {me(binding)}"| {right}')
    segments.extend([
        '  classDef unknown fill:#292042,stroke:#c39cfa,color:#eff0ff',
        '  classDef hold fill:#392234,stroke:#ef89a6,color:#fff',
        '  classDef alias fill:#241d3e,stroke:#c39cfa,stroke-dasharray:4 4,color:#fff',
    ])
    for n in vertices:
        cls = 'alias' if n['status'] == 'ALIAS' else 'hold' if n['status'] in ('HOLD', 'OWNER_ONLY', 'NATIVE_REQUIRED') else 'unknown'
        segments.append(f'  class {mid(n["id"])} {cls}')
    return '\n'.join(segments) + '\n'


def mermaid_group(model: dict, group: dict) -> str:
    ids = set(group['nodes'])
    vertices = [n for n in model['nodes'] if n['id'] in ids]
    internal_edges = [e for e in model['edges'] if e['from'] in ids and e['to'] in ids]
    return mermaid(model, internal_edges, vertices, f'W35 Lasso group: {group["label"]}')


def mermaid_trigger(model: dict) -> str:
    chosen = [e for e in model['edges'] if e['kind'] in ('TRIGGER', 'RETRIGGER', 'FEDERATION', 'DEPENDENCY')]
    ids = {e[x] for e in chosen for x in ('from','to')}
    return mermaid(model, chosen, [n for n in model['nodes'] if n['id'] in ids],
                   'Trigger/dependency lens · source routes not native event bus')


def mermaid_sipoc(model: dict, groups: list[dict]) -> str:
    byrow = {g['sipoc_row']: g for g in groups if g.get('sipoc_row') is not None}
    x = ['%% Typed SIPOC pipeline projection, not live execution', 'flowchart LR']
    for i, row in enumerate(model['sipoc']):
        g = byrow[i]
        x.append(f'  subgraph S{i}["{me(g["label"])} · SOURCE"]')
        for j, stage in enumerate(('supplier', 'input', 'process', 'output', 'customer')):
            x.append(f'    p{i}_{j}["{me(row[stage])}"]')
        x.append('  end')
        for j in range(4):
            x.append(f'  p{i}_{j} -. "SIPOC mapping / DECLARED" .-> p{i}_{j+1}')
    return '\n'.join(x) + '\n'


def short_lines(s: str, limit: int = 24) -> list[str]:
    text = ' '.join(str(s).split())
    return textwrap.wrap(text, width=limit, break_long_words=True, break_on_hyphens=False)[:3] or ['—']


def sipoc_svg(model: dict, groups: list[dict]) -> str:
    groups_by_row = {g['sipoc_row']:g for g in groups if g.get('sipoc_row') is not None}
    titles = ('SUPPLIER', 'INPUT', 'PROCESS', 'OUTPUT', 'CUSTOMER')
    row_h = 90
    width = 1380
    height = 70 + len(model['sipoc']) * row_h + 35
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-label="Five source-bound SIPOC process lanes; click row for synchronized group lasso">',
             '<defs><marker id="sipoc-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0 L7 3.5 L0 7" stroke="#bca5fd" fill="none"/></marker></defs>',
             '<rect width="100%" height="100%" fill="#0d1428"/>',
             '<text x="18" y="20" fill="#cbb0ff" font-size="15" font-weight="700">SIPOC · typed source and process lanes</text>',
             '<text x="18" y="38" fill="#9eb1d7" font-size="11">CLICK A ROW · owner-bound mapping, NOT verified native stage execution</text>']
    for i,title in enumerate(titles):
        parts.append(f'<text x="{25+i*274}" y="57" fill="#aeadcf" font-size="12" font-weight="700">{title}</text>')
    for i,row in enumerate(model['sipoc']):
        y=68+i*row_h
        group=groups_by_row[i]
        gid=group['id']
        parts.append(f'<g data-group="{html.escape(gid, quote=True)}" class="sipoc-group" role="button" tabindex="0" aria-label="Inspect SIPOC group {html.escape(group["label"],quote=True)}">')
        parts.append(f'<title>{html.escape(group["label"])} · evidence UNKNOWN where not independently qualified</title>')
        for j,stage in enumerate(('supplier', 'input', 'process', 'output', 'customer')):
            x=18+j*274
            parts.append(f'<rect x="{x}" y="{y}" width="242" height="76" rx="10" fill="#221a43" stroke="#956bd9" stroke-opacity="0.9"/>')
            for line_no, ln in enumerate(short_lines(row[stage])):
                parts.append(f'<text x="{x+12}" y="{y+25+line_no*17}" fill="#e8ddff" font-size="12">{html.escape(ln)}</text>')
            if j < 4:
                parts.append(f'<path d="M{x+245} {y+38} H{x+272}" stroke="#c7a5ff" stroke-width="2" marker-end="url(#sipoc-arrow)"/>')
        parts.append('</g>')
    parts.append('</svg>')
    return '\n'.join(parts)+'\n'


def trigger_svg(model: dict, draw_svg) -> str:
    # Reuse the same governed node positions and edges, not a simulated event log.
    chosen = [e for e in model['edges'] if e['kind'] in ('TRIGGER','RETRIGGER','FEDERATION','DEPENDENCY')]
    ids = {e[x] for e in chosen for x in ('from','to')}
    subset = {**model,
              'nodes': [n for n in model['nodes'] if n['id'] in ids],
              'edges': chosen}
    return draw_svg(subset).replace('aria-label="Expanded six-lane',
                                    'aria-label="Trigger and dependency source-only six-lane')


def summarize_group_edges(model: dict, group: dict) -> dict:
    members = set(group['nodes'])
    internal = [e for e in model['edges'] if e['from'] in members and e['to'] in members]
    touches = [e for e in model['edges'] if e['kind']=='TOUCH' and
               (e['from'] in members or e['to'] in members)]
    aliases = sum(n['status']=='ALIAS' and n['id'] in members for n in model['nodes'])
    return {'group_id':group['id'],'node_placements':len(members),
            'internal_typed_edges':len(internal),'touch_edges':len(touches),
            'alias_placements':aliases,'native_completed_jobs':None}
