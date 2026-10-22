"""Read-only G3P HTML/SVG dashboard, N-index replay and local ledger watcher.

The server reads existing validated ledgers on each request. It does NOT poll
GitHub, trigger workers, overwrite historic evidence, or authorize admission.
Supports SSE revision pushes and periodic browser polling; no third-party deps.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = 'missioncontrol.g3p.live_snapshot.v1'
_TEMPLATE = Path(__file__).with_name('g3p_live_template.html')


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'))


def load_snapshot(paths):
    """Read+validate full immutable ledger copies; do not cache stale validity."""
    from n3_wave_federation import compile_waves
    if not isinstance(paths, (list, tuple)) or len(paths) < 2:
        raise ValueError('two or more source ledgers are required')
    ledgers = []
    inputs = []
    for path in paths:
        source = Path(path)
        payload = source.read_bytes()
        obj = json.loads(payload.decode('utf-8'))
        ledgers.append(obj)
        inputs.append({'filename': source.name, 'raw_sha256': hashlib.sha256(payload).hexdigest()})
    data = compile_waves(ledgers)  # underlying controller rejects broken chains, duplicate identities, escalation
    if data['merge_admission'] != 'HOLD' or data['authority_transfer'] is not False:
        raise ValueError('refuse propagated admission authority')
    if any(node['merge_admission'] != 'HOLD' or node['source_authenticated'] is not False
           for node in data['nodes']):
        raise ValueError('unverified source or admission promoted')
    revision = hashlib.sha256(canonical({'inputs': inputs, 'lineage': data}).encode('utf-8')).hexdigest()
    # Wall clock below is feeder readback, NOT knowledge-time or test-execution evidence.
    return {**data, 'schema': SCHEMA, 'revision': revision, 'source_inputs': inputs,
            'capture_class': 'LEDGER_CHAIN_VALIDATED_NOT_GITHUB_NATIVE_PROOF',
            'feeder_observed_at_utc': datetime.now(timezone.utc).isoformat()}


def _escape_bootstrap(obj):
    """Never let an untrusted source label terminate a script tag."""
    return canonical(obj).replace('<', r'\u003c').replace('>', r'\u003e')\
        .replace('&', r'\u0026').replace('\u2028', r'\u2028').replace('\u2029', r'\u2029')


def render_html(data):
    """Fully static first paint and embedded payload for file:// replay."""
    if data.get('merge_admission') != 'HOLD' or data.get('authority_transfer') is not False:
        raise ValueError('cannot render escalated authority')
    if data.get('schema') not in (SCHEMA, 'missioncontrol.g3p.wave_lineage.v1'):
        raise ValueError('invalid wave graph')
    graph = data
    if data['schema'] != SCHEMA:
        # Legacy generator produced the static graph without a live source digest.
        rev = hashlib.sha256(canonical(data).encode()).hexdigest()
        graph = {**data, 'schema': SCHEMA, 'revision': rev,
                 'capture_class': 'BUNDLED_VALIDATED_CLAIM_NOT_NATIVE_PROOF',
                 'source_inputs': []}
    nodes, edges = graph['nodes'], graph['edges']
    if not nodes:
        raise ValueError('no pulse nodes')
    esc = lambda x: html.escape(str(x), quote=True)
    loc = {node['id']: 105 + 155 * i for i, node in enumerate(nodes)}
    initial_edges = []
    for edge in edges:
        style = ' stroke-dasharray="7 6"' if edge['evidence'] == 'DECLARED_GAP' else ''
        first = loc[edge['source']] + 31
        last = loc[edge['target']] - 32
        initial_edges.append(f'<line x1="{first}" y1="86" x2="{last}" y2="86" '
                             f'stroke="#556f91" stroke-width="2" marker-end="url(#arr)"{style}/>')
    initial_nodes = []
    for i, n in enumerate(nodes):
        x = 105 + 155 * i
        initial_nodes.append(f'<g><circle cx="{x}" cy="86" r="31" fill="#edf2f8" '
                             f'stroke="#426486" stroke-width="2"/><text x="{x}" y="92" text-anchor="middle">'
                             f'N+{int(n["ordinal"])}</text><title>{esc(n["id"])}</title></g>')
    rows = []
    for n in nodes:
        passed = 'UNKNOWN' if n['test_kind'] == 'NOT_RUN' else str(n['passed_test_claim'])
        rows.append(f'<tr><th scope="row">N+{int(n["ordinal"])}</th><td>{esc(n["wave"])}</td>'
                    f'<td><code>{esc(n["source_head_claim"][:12])}</code></td><td>{esc(n["test_kind"])}</td>'
                    f'<td>{passed}</td><td>UNVERIFIED</td><td class="hold">HOLD</td></tr>')
    tokens = {
        '@@INITIAL_EDGES@@': ''.join(initial_edges),
        '@@INITIAL_NODES@@': ''.join(initial_nodes),
        '@@INITIAL_ROWS@@': ''.join(rows),
        '@@INITIAL_SOURCE_DIGESTS@@': esc(', '.join(w['source_digest'] for w in graph['waves'])),
        '@@INITIAL_REVISION@@': esc(graph['revision']),
        '@@BOOTSTRAP@@': _escape_bootstrap(graph),
    }
    output = _TEMPLATE.read_text(encoding='utf-8')
    for key, value in tokens.items():
        if output.count(key) != 1:
            raise ValueError('template placeholder missing or duplicated: ' + key)
        output = output.replace(key, value)
    return output


def export(paths, out_dir):
    from n3_wave_federation import mermaid
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    payload = load_snapshot(paths)
    (out / 'g3p-lineage.html').write_text(render_html(payload) + '\n', encoding='utf-8')
    (out / 'g3p-lineage.json').write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    (out / 'g3p-lineage.mmd').write_text(mermaid({**payload,'schema':'missioncontrol.g3p.wave_lineage.v1'}), encoding='utf-8')
    files = ['g3p-lineage.html', 'g3p-lineage.json', 'g3p-lineage.mmd']
    hashes = {name: hashlib.sha256((out/name).read_bytes()).hexdigest() for name in files}
    manifest = {'schema':'missioncontrol.g3p.live_static_manifest.v1',
                'revision': payload['revision'], 'source_inputs': payload['source_inputs'],
                'outputs_sha256': hashes, 'merge_admission':'HOLD', 'authority_transfer':False}
    (out / 'g3p-manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


class LiveFeed:
    def __init__(self, paths):
        self.paths = tuple(Path(p) for p in paths)

    def snapshot(self):
        return load_snapshot(self.paths)


def create_server(paths, port=8765, host='127.0.0.1'):
    if host not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('external network binding disabled: use loopback only')
    feed = LiveFeed(paths)
    feed.snapshot()  # refuse to start with invalid source ledgers

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, format_string, *args):
            # Avoid printing untrusted request data into CI transcript by default.
            pass

        def send_payload(self, body, kind='application/json; charset=utf-8', code=200):
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in ('/', '/g3p-lineage.html'):
                try:
                    content = render_html(feed.snapshot()).encode('utf-8')
                    self.send_payload(content, 'text/html; charset=utf-8')
                except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
                    self.send_payload(json.dumps({'error':str(exc),'admission':'HOLD'}).encode(),code=409)
            elif path == '/api/lineage':
                try:
                    value = feed.snapshot()
                    content = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
                    self.send_payload(content)
                except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
                    self.send_payload(json.dumps({'error':str(exc),'merge_admission':'HOLD'}).encode(),code=409)
            elif path == '/api/events':
                self.push_events()
            elif path == '/health':
                try:
                    snap = feed.snapshot()
                    self.send_payload(json.dumps({'healthy':True,'revision':snap['revision'],
                                                 'merge_admission':'HOLD'}).encode())
                except (ValueError, OSError, KeyError) as exc:
                    self.send_payload(json.dumps({'healthy':False,'error':str(exc)}).encode(),code=503)
            else:
                self.send_payload(b'{"error":"not found"}', code=404)

        def push_events(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
            self.send_header('Cache-Control', 'no-store, max-age=0')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Accel-Buffering', 'no')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            last = None
            try:
                # Bounded connection lifetime; EventSource reconnects automatically.
                for step in range(90):
                    try:
                        revision = feed.snapshot()['revision']
                        if last != revision:
                            message = json.dumps({'revision':revision}, sort_keys=True)
                            self.wfile.write(f'event: revision\ndata: {message}\n\n'.encode())
                            last = revision
                        elif step % 7 == 0:
                            self.wfile.write(b': heartbeat\n\n')
                    except (ValueError, OSError, KeyError, json.JSONDecodeError):
                        self.wfile.write(b'event: feed_error\ndata: {"merge_admission":"HOLD"}\n\n')
                    self.wfile.flush()
                    time.sleep(2)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                return

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledgers', required=True, nargs='+', type=Path)
    parser.add_argument('--out-dir', type=Path)
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not args.serve and not args.out_dir:
        parser.error('specify --out-dir or --serve')
    if args.out_dir:
        manifest = export(args.ledgers, args.out_dir)
        print(json.dumps({'created':str(args.out_dir),'revision':manifest['revision'],
                          'outputs':list(manifest['outputs_sha256'])},sort_keys=True))
    if args.serve:
        with create_server(args.ledgers, port=args.port) as server:
            print(f'Read-only live G3P UI: http://127.0.0.1:{server.server_port}/', flush=True)
            print('SSE /api/events; cyclic JSON /api/lineage; CTRL-C stops', flush=True)
            try:
                server.serve_forever(poll_interval=.25)
            except KeyboardInterrupt:
                server.shutdown()


if __name__ == '__main__':
    main()
