"""New live N-index UI, server push/poll, provenance and fail-closed tests."""
from __future__ import annotations

import copy
import hashlib
import contextlib
import io
from unittest.mock import patch
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / 'federation-atlas'
PATHS = [ROOT / 'CBD_GOLDEN_GRAPH_N3_20261017.json',
         ROOT / 'CBD_GOLDEN_GRAPH_N6_20261017.json']
sys.path.insert(0, str(HERE))
import g3p_live_dashboard as live
from n3_wave_federation import html_report


def copies(to):
    targets=[]
    for path in PATHS:
        p=Path(to)/path.name
        p.write_bytes(path.read_bytes())
        targets.append(p)
    return targets


class LiveDashboardTests(unittest.TestCase):
    def test_existing_six_pulses_and_notrun_semantics(self):
        p=live.load_snapshot(PATHS)
        self.assertEqual(p['schema'], live.SCHEMA)
        self.assertEqual((p['metrics']['pulses'],p['metrics']['edge_count'],p['metrics']['intervening_unproven_source_boundaries']), (6,5,1))
        self.assertEqual([(n['ordinal'],n['test_kind']) for n in p['nodes'] if n['test_kind']=='NOT_RUN'],[(1,'NOT_RUN'),(3,'NOT_RUN')])
        self.assertEqual(p['nodes'][-1]['passed_test_claim'],61)
        self.assertEqual(p['merge_admission'],'HOLD')
        self.assertFalse(p['authority_transfer'])
        self.assertEqual(p['metrics']['authenticated_native_pulse_receipts'],0)

    def test_two_digest_originals_are_preserved(self):
        p=live.load_snapshot(PATHS)
        self.assertEqual(p['waves'][0]['source_digest'],'64ce3270d156cfd3362b0618c6af4a3ecb6279e9ce88c6b23f9bd3618f7ca555')
        self.assertEqual(p['waves'][1]['source_digest'],'ecaefb8736f01cea203cdee5b5e9158e9eaa0e34be8a623efd3a0a05210314d0')

    def test_pure_replay_source_revision_stable(self):
        a=live.load_snapshot(PATHS);b=live.load_snapshot(PATHS)
        self.assertEqual(a['revision'],b['revision'])
        self.assertEqual(a['nodes'],b['nodes'])
        self.assertTrue(a['feeder_observed_at_utc'])
        self.assertNotIn('COMPLETED',a['capture_class'])

    def test_source_changed_with_same_pulse_id_revision_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=copies(tmp)
            before=live.load_snapshot(files)
            o=json.loads(files[1].read_text(encoding="utf-8"))
            o.setdefault('notes',[]).append('NEW_OBSERVATION_WHILE_HISTORY_PRESERVED_IN_GIT')
            files[1].write_text(json.dumps(o), encoding="utf-8", newline="\n")
            after=live.load_snapshot(files)
            self.assertNotEqual(before['revision'],after['revision'])
            self.assertEqual(after['metrics']['pulses'],6)
            self.assertEqual(after['merge_admission'],'HOLD')
            self.assertNotEqual(before['waves'][-1]['source_digest'],after['waves'][-1]['source_digest'])

    def test_broken_chain_no_new_valid_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=copies(tmp)
            o=json.loads(files[1].read_text(encoding="utf-8"))
            o['receipts'][0]['merge_admission']='PASS'
            files[1].write_text(json.dumps(o), encoding="utf-8", newline="\n")
            with self.assertRaises(ValueError): live.load_snapshot(files)

    def test_null_mission_is_a_structural_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=copies(tmp)
            o=json.loads(files[0].read_text(encoding="utf-8"))
            o['mission']=None
            files[0].write_text(json.dumps(o), encoding="utf-8", newline="\n")
            with self.assertRaisesRegex(ValueError,'invalid source ledger structure'):
                live.load_snapshot(files)

    def test_wrong_cross_wave_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=copies(tmp)
            o=json.loads(files[1].read_text(encoding="utf-8"));o['start_ordinal']=4
            files[1].write_text(json.dumps(o), encoding="utf-8", newline="\n")
            with self.assertRaises(ValueError):live.load_snapshot(files)

    def test_no_untrusted_or_external_scripts(self):
        h=live.render_html(live.load_snapshot(PATHS))
        self.assertEqual(h.count('<script>'),1)
        self.assertNotIn('<script src=',h)
        self.assertIn('EventSource',h)
        self.assertIn('id="ordinal"',h)
        self.assertIn('id="reload"',h)
        self.assertIn('id="poll"',h)
        self.assertIn('id="replay"',h)
        self.assertIn('#lineage-svg .pulse-node:focus-visible circle{stroke:#d35400',h)
        self.assertIn("function unprovenBoundary(e){return e.relationship==='inter_wave_source_lineage'&&e.source_ancestry_proven!==true;}",h)
        self.assertIn("el('ordinal').min=data.nodes[0].ordinal;el('ordinal').max=data.nodes.at(-1).ordinal;at=data.nodes.at(-1).ordinal",h)
        self.assertIn('NOT_RUN',h)
        self.assertIn('HOLD',h)

    def test_escaping_script_terminator(self):
        p=live.load_snapshot(PATHS)
        p['nodes'][0]['wave']='</script><script>alert(1)</script>'
        h=live.render_html(p)
        self.assertNotIn('</script><script>alert(1)',h)
        self.assertIn(r'\u003c/script',h)
        self.assertIn('&lt;/script&gt;',h)

    def test_refuse_unsupported_or_escalated_view(self):
        x=live.load_snapshot(PATHS)
        x['authority_transfer']=True
        with self.assertRaises(ValueError):live.render_html(x)
        x['authority_transfer']=False;x['merge_admission']='PASS'
        with self.assertRaises(ValueError):live.render_html(x)

    def test_legacy_html_generator_now_interactive(self):
        p=live.load_snapshot(PATHS)
        html=html_report(p)
        self.assertIn('Cyclic',html.replace('cyclic','Cyclic'))
        self.assertIn('missioncontrol.g3p.live_snapshot.v1',html)

    def test_export_standalone_and_hash_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            man=live.export(PATHS,d)
            first_hashes=man['outputs_sha256']
            j=json.loads((Path(d)/'g3p-lineage.json').read_text(encoding="utf-8"))
            self.assertNotIn('feeder_observed_at_utc',j)
            man=live.export(PATHS,d)
            self.assertEqual(man['outputs_sha256'],first_hashes)
            self.assertEqual(man['outputs_sha256'],json.loads((Path(d)/'g3p-manifest.json').read_text(encoding="utf-8"))['outputs_sha256'])
            for file,digest in man['outputs_sha256'].items():
                self.assertEqual(hashlib.sha256((Path(d)/file).read_bytes()).hexdigest(),digest)
            j=json.loads((Path(d)/'g3p-lineage.json').read_text(encoding="utf-8"))
            self.assertEqual((j['metrics']['pulses'],j['metrics']['edge_count']),(6,5))
            self.assertEqual((Path(d)/'g3p-lineage.mmd').read_text(encoding="utf-8").count('-.->'),1)

    def test_no_exposed_interface_bind(self):
        with self.assertRaisesRegex(ValueError,'external network binding disabled'):
            live.create_server(PATHS,port=0,host='0.0.0.0')

    def test_bad_initial_ledger_prevents_server_start(self):
        with tempfile.TemporaryDirectory() as d:
            files=copies(d)
            files[0].write_text('{', encoding="utf-8", newline="\n")
            with self.assertRaises(json.JSONDecodeError):live.create_server(files,port=0)

    def test_readonly_health_html_alias_and_404(self):
        server=live.create_server(PATHS,port=0)
        th=threading.Thread(target=server.serve_forever,daemon=True)
        th.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/g3p-lineage.html',timeout=3) as req:
                self.assertEqual(req.status,200)
                self.assertIn('text/html',req.headers['Content-Type'])
            with urlopen(base+'/health',timeout=3) as req:
                ok=json.load(req)
                self.assertTrue(ok['healthy'])
                self.assertEqual(ok['merge_admission'],'HOLD')
            with self.assertRaises(HTTPError) as e:
                urlopen(base+'/secret-data',timeout=3)
            self.assertEqual(e.exception.code,404)
        finally:
            server.shutdown();server.server_close();th.join(timeout=4)

    def test_cli_export_without_serve_is_readonly(self):
        with tempfile.TemporaryDirectory() as d:
            args=['g3p_live_dashboard.py','--ledgers',*(str(p) for p in PATHS),'--out-dir',d]
            with patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()) as out:
                live.main()
            self.assertIn('revision',out.getvalue())
            self.assertIn('outputs_sha256',json.loads((Path(d)/'g3p-manifest.json').read_text(encoding="utf-8")))

    def test_cli_missing_output_or_serve_fails(self):
        args=['g3p_live_dashboard.py','--ledgers',*(str(p) for p in PATHS)]
        with patch.object(sys,'argv',args),contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as e:live.main()
        self.assertEqual(e.exception.code,2)

    def test_cli_serve_dispatch_respects_loopback_and_stops(self):
        class FakeServer:
            server_port=8765
            def __enter__(self):return self
            def __exit__(self,exc_type,exc,tb):return None
            def serve_forever(self,poll_interval):raise KeyboardInterrupt
            def shutdown(self):pass
        args=['g3p_live_dashboard.py','--ledgers',*(str(p) for p in PATHS),'--serve']
        with patch.object(sys,'argv',args),patch.object(live,'create_server',return_value=FakeServer()) as fake:
            with contextlib.redirect_stdout(io.StringIO()) as out:
                live.main()
        self.assertEqual(fake.call_args.kwargs['port'],8765)
        self.assertIn('127.0.0.1',out.getvalue())

    def test_invalid_schema_and_missing_nodes_fail_renderer(self):
        p=live.load_snapshot(PATHS)
        p['schema']='unsupported'
        with self.assertRaisesRegex(ValueError,'invalid wave graph'):live.render_html(p)
        p=live.load_snapshot(PATHS);p['nodes']=[]
        with self.assertRaisesRegex(ValueError,'no pulse nodes'):live.render_html(p)

    def test_snapshot_requires_complete_inputs(self):
        with self.assertRaisesRegex(ValueError,'two or more'):live.load_snapshot(PATHS[:1])
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'missing.json'
            with self.assertRaises(FileNotFoundError):live.load_snapshot([PATHS[0],path])

    def test_unicode_script_safety(self):
        x=live._escape_bootstrap({'text':'</script><svg>&\u2028\u2029'})
        self.assertNotIn('</script>',x)
        self.assertIn('\\u003c',x)
        self.assertNotIn('<svg>',x)

    def test_sse_structurally_invalid_local_source_yields_hold_event(self):
        with tempfile.TemporaryDirectory() as d:
            files=copies(d)
            server=live.create_server(files,port=0)
            th=threading.Thread(target=server.serve_forever,daemon=True)
            th.start()
            try:
                with urlopen(f'http://127.0.0.1:{server.server_port}/api/events',timeout=10) as event_source:
                    event_source.readline();event_source.readline();event_source.readline()
                    o=json.loads(files[1].read_text(encoding="utf-8"))
                    o['mission']=None
                    files[1].write_text(json.dumps(o), encoding="utf-8", newline="\n")
                    received=False
                    for _ in range(14):
                        line=event_source.readline().decode().strip()
                        if line == 'event: feed_error':received=True;break
                    self.assertTrue(received)
            finally:
                server.shutdown();server.server_close();th.join(timeout=4)

    def test_structurally_invalid_ledger_returns_http_hold_responses(self):
        with tempfile.TemporaryDirectory() as d:
            files=copies(d)
            server=live.create_server(files,port=0)
            th=threading.Thread(target=server.serve_forever,daemon=True)
            th.start()
            try:
                o=json.loads(files[0].read_text(encoding="utf-8"))
                o['mission']=None
                files[0].write_text(json.dumps(o), encoding="utf-8", newline="\n")
                for path, expected in (('/api/lineage',409),('/health',503)):
                    with self.subTest(path=path):
                        with self.assertRaises(HTTPError) as error:
                            urlopen(f'http://127.0.0.1:{server.server_port}{path}',timeout=3)
                        self.assertEqual(error.exception.code,expected)
            finally:
                server.shutdown();server.server_close();th.join(timeout=4)

    def test_sse_push_changed_revision_without_reload(self):
        with tempfile.TemporaryDirectory() as d:
            files = copies(d)
            server = live.create_server(files, port=0)
            th = threading.Thread(target=server.serve_forever, daemon=True)
            th.start()
            try:
                with urlopen(f'http://127.0.0.1:{server.server_port}/api/events',timeout=9) as event_source:
                    self.assertEqual(event_source.readline().decode().strip(),'event: revision')
                    previous = json.loads(event_source.readline().decode()[6:])['revision']
                    event_source.readline()  # blank line
                    o = json.loads(files[1].read_text(encoding="utf-8"))
                    o.setdefault('notes',[]).append('VALID_LOCAL_FEED_REVISION_TEST')
                    files[1].write_text(json.dumps(o), encoding="utf-8", newline="\n")
                    event_type=None
                    revision=None
                    # Bounded SSE reader. Server checks input every 2 s.
                    for _ in range(12):
                        line=event_source.readline().decode().strip()
                        if line == 'event: revision':event_type='revision'
                        elif event_type=='revision' and line.startswith('data: '):
                            revision=json.loads(line[6:])['revision']
                            break
                    self.assertIsNotNone(revision)
                    self.assertNotEqual(previous,revision)
            finally:
                server.shutdown();server.server_close();th.join(timeout=4)

    def test_sse_connection_closes_after_bounded_stream(self):
        with tempfile.TemporaryDirectory() as d:
            files = copies(d)
            server = live.create_server(files, port=0)
            th = threading.Thread(target=server.serve_forever, daemon=True)
            th.start()
            try:
                with patch.object(live.time, 'sleep', return_value=None):
                    with urlopen(f'http://127.0.0.1:{server.server_port}/api/events', timeout=3) as stream:
                        self.assertEqual(stream.headers.get('Connection'), 'close')
                        self.assertEqual(stream.readline().decode().strip(), 'event: revision')
                        self.assertIn(b'data: ', stream.read())
            finally:
                server.shutdown();server.server_close();th.join(timeout=4)

    def test_http_reload_and_sse_revision(self):
        with tempfile.TemporaryDirectory() as d:
            files=copies(d)
            server=live.create_server(files,port=0)
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            base=f'http://127.0.0.1:{server.server_port}'
            try:
                with urlopen(base+'/api/lineage',timeout=3) as req:
                    self.assertEqual(req.status,200)
                    self.assertEqual(req.headers['Cache-Control'],'no-store, max-age=0')
                    initial=json.load(req)
                self.assertEqual(initial['metrics']['pulses'],6)
                with urlopen(base+'/',timeout=3) as req:
                    html=req.read().decode()
                    self.assertIn('id="reload"',html)
                    self.assertIn('id="lineage-svg"',html)
                with urlopen(base+'/api/events',timeout=3) as req:
                    first=req.readline().decode().strip()
                    second=req.readline().decode().strip()
                    self.assertEqual(first,'event: revision')
                    self.assertEqual(json.loads(second[6:])['revision'],initial['revision'])
                o=json.loads(files[1].read_text(encoding="utf-8"));o.setdefault('notes',[]).append('REVISION_UPDATED')
                files[1].write_text(json.dumps(o), encoding="utf-8", newline="\n")
                with urlopen(base+'/api/lineage',timeout=3) as req:
                    after=json.load(req)
                self.assertNotEqual(initial['revision'],after['revision'])
                self.assertEqual(after['metrics']['pulses'],6)
                o['receipts'][0]['authority_transfer']=True
                files[1].write_text(json.dumps(o), encoding="utf-8", newline="\n")
                with self.assertRaises(HTTPError) as err:
                    urlopen(base+'/api/lineage',timeout=3)
                self.assertEqual(err.exception.code,409)
                with self.assertRaises(HTTPError) as h:
                    urlopen(base+'/health',timeout=3)
                self.assertEqual(h.exception.code,503)
            finally:
                server.shutdown();server.server_close();worker.join(timeout=4)


if __name__=='__main__':unittest.main()
