"""New live N-index UI, server push/poll, provenance and fail-closed tests."""
from __future__ import annotations

import copy
import hashlib
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
            o=json.loads(files[1].read_text())
            o.setdefault('notes',[]).append('NEW_OBSERVATION_WHILE_HISTORY_PRESERVED_IN_GIT')
            files[1].write_text(json.dumps(o))
            after=live.load_snapshot(files)
            self.assertNotEqual(before['revision'],after['revision'])
            self.assertEqual(after['metrics']['pulses'],6)
            self.assertEqual(after['merge_admission'],'HOLD')
            self.assertNotEqual(before['waves'][-1]['source_digest'],after['waves'][-1]['source_digest'])

    def test_broken_chain_no_new_valid_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=copies(tmp)
            o=json.loads(files[1].read_text())
            o['receipts'][0]['merge_admission']='PASS'
            files[1].write_text(json.dumps(o))
            with self.assertRaises(ValueError): live.load_snapshot(files)

    def test_wrong_cross_wave_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=copies(tmp)
            o=json.loads(files[1].read_text());o['start_ordinal']=4
            files[1].write_text(json.dumps(o))
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
            for file,digest in man['outputs_sha256'].items():
                self.assertEqual(hashlib.sha256((Path(d)/file).read_bytes()).hexdigest(),digest)
            j=json.loads((Path(d)/'g3p-lineage.json').read_text())
            self.assertEqual((j['metrics']['pulses'],j['metrics']['edge_count']),(6,5))
            self.assertEqual((Path(d)/'g3p-lineage.mmd').read_text().count('-.->'),1)

    def test_no_exposed_interface_bind(self):
        with self.assertRaisesRegex(ValueError,'external network binding disabled'):
            live.create_server(PATHS,port=0,host='0.0.0.0')

    def test_bad_initial_ledger_prevents_server_start(self):
        with tempfile.TemporaryDirectory() as d:
            files=copies(d)
            files[0].write_text('{')
            with self.assertRaises(json.JSONDecodeError):live.create_server(files,port=0)

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
                o=json.loads(files[1].read_text());o.setdefault('notes',[]).append('REVISION_UPDATED')
                files[1].write_text(json.dumps(o))
                with urlopen(base+'/api/lineage',timeout=3) as req:
                    after=json.load(req)
                self.assertNotEqual(initial['revision'],after['revision'])
                self.assertEqual(after['metrics']['pulses'],6)
                o['receipts'][0]['authority_transfer']=True
                files[1].write_text(json.dumps(o))
                with self.assertRaises(HTTPError) as err:
                    urlopen(base+'/api/lineage',timeout=3)
                self.assertEqual(err.exception.code,409)
                with self.assertRaises(HTTPError) as h:
                    urlopen(base+'/health',timeout=3)
                self.assertEqual(h.exception.code,503)
            finally:
                server.shutdown();server.server_close();worker.join(timeout=4)


if __name__=='__main__':unittest.main()
