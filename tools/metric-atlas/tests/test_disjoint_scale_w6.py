"""W6 disjoint scaling: fake heads, reverse edges, adversarial leases, 72 cohorts."""
import copy
import itertools
import tempfile
import unittest
from pathlib import Path
from metric_atlas.census import ALLOWED_REPOS, request
from metric_atlas.disjoint_scale import (DisjointScaleError, plan, verify_plan,
                                          main, mermaid_dag, mermaid_sipoc, mermaid_spline)

SHA={lane: format(i+1,'x')*40 for i,lane in enumerate(ALLOWED_REPOS)}


def manifest(availability=(1,1,1),fanout=3,selector='all'):
    heads={lane:SHA[lane] if yes else None for lane,yes in zip(ALLOWED_REPOS,availability)}
    return request('W6P',heads,selector=selector,max_fanout=fanout)


class DisjointScaleW6Tests(unittest.TestCase):
    def test_three_pulse_bounded_scale(self):
        out=[plan(manifest(fanout=i),slots=2) for i in (1,2,3)]
        self.assertEqual([x['route_population'] for x in out],[2,4,6])
        self.assertEqual([x['selected_repositories'] for x in out],[1,2,3])
        self.assertEqual([x['deferred_repositories'] for x in out],[2,1,0])
        self.assertTrue(all(not x['dispatch_performed'] for x in out))

    def test_72_three_repo_capability_scenarios(self):
        seen=0
        for available in itertools.product((0,1), repeat=3):
            for fanout in (1,2,3):
                for slots in (1,2,3):
                    with self.subTest(available=available,fanout=fanout,slots=slots):
                        m=manifest(available,fanout);x=plan(m,slots=slots)
                        self.assertEqual(x['eligible_repositories'],3)
                        self.assertEqual(x['selected_repositories'],len(m['requests']))
                        self.assertEqual(x['route_population'],2*len(m['requests']))
                        self.assertEqual(x['source_head_unknown'],3-sum(available))
                        self.assertEqual(x['selected_repositories']+x['deferred_repositories'],3)
                        self.assertLessEqual(max((len(y) for y in x['rounds']),default=0),slots)
                        self.assertTrue(all(len({t['lease_key'] for t in round_})==len(round_) for round_ in x['rounds']))
                        self.assertEqual(verify_plan(m,x),x)
                        self.assertIsNone(x['native_tests_credited'])
                        self.assertEqual(x['merge_admission'],'HOLD')
                        seen+=1
        self.assertEqual(seen,72)

    def test_route_selectors_conserve_counts(self):
        for selector in ('native_checks','coverage_catalog','all'):
            for fanout in (1,2,3):
                with self.subTest(selector=selector,fanout=fanout):
                    m=manifest(fanout=fanout,selector=selector)
                    x=plan(m,slots=2)
                    self.assertEqual(x['route_population'],len(m['requests'])*(2 if selector=='all' else 1))

    def test_duplicate_request_or_unrecognized_sha_rejected(self):
        source=manifest()
        for transform in (
            lambda m: m['requests'].append(copy.deepcopy(m['requests'][0])),
            lambda m: m['requests'][0].update(expected_sha='a'*40),
            lambda m: m['requests'][0].update(request_id='QPS-FAKE'),
            lambda m: m['requests'][0].update(state='DISPATCHED'),
            lambda m: m.update(authority_transfer=True),
            lambda m: m.update(dispatch_enabled=True),
            lambda m: m.update(max_fanout=True),
            lambda m: m['not_dispatched'].append({'lane':'FOREIGN','repo':'evil/evil'}),
        ):
            with self.subTest(transform=transform):
                m=copy.deepcopy(source);transform(m)
                with self.assertRaises(DisjointScaleError):plan(m)

    def test_missing_sources_remain_unknown_not_automatically_green(self):
        m=manifest((0,1,0)); x=plan(m)
        self.assertEqual((x['source_head_unknown'],x['route_population']), (2,2))
        self.assertTrue(all(t['native_evidence'] is None for row in x['rounds'] for t in row))
        self.assertEqual(x['causal_root_closures'],None)

    def test_no_slots_overflow_false_booleans(self):
        for slots in (0,4,-1,None,True,False,1.0,'2',[]):
            with self.subTest(slots=slots),self.assertRaises(DisjointScaleError):
                plan(manifest(),slots=slots)

    def test_explicit_source_priority_can_put_master_input_first(self):
        x=plan(manifest(),slots=2,source_priority=['QPS_ENGINEERING','ABACUS','CODEX'])
        self.assertEqual(x['rounds'][0][0]['lane'],'QPS_ENGINEERING')
        self.assertEqual(verify_plan(manifest(),x),x)
        self.assertFalse(x['dispatch_performed'])
        self.assertEqual(x['capacity_class'],'HYPOTHETICAL_NOT_MEASURED')

    def test_bad_source_priority_rejected(self):
        for p in ([],['CODEX'],['CODEX']*3,['FOREIGN','ABACUS','CODEX'],[1,2,3]):
            with self.subTest(order=p),self.assertRaises(DisjointScaleError):plan(manifest(),source_priority=p)

    def test_repeated_order_and_ticket_id_deterministic(self):
        m=manifest()
        samples=[plan(m,slots=2) for _ in range(12)]
        self.assertTrue(all(x==samples[0] for x in samples))
        self.assertEqual(len({t['ticket'] for row in samples[0]['rounds'] for t in row}),6)

    def test_inputs_immutable_even_after_mutated_output(self):
        m=manifest(); saved=copy.deepcopy(m)
        x=plan(m);self.assertEqual(m,saved)
        x['rounds'][0][0]['state']='EXECUTED'
        with self.assertRaises(DisjointScaleError):verify_plan(m,x)
        self.assertEqual(plan(m)['workers_launched'],0)

    def test_reverse_temporal_edge_excluded_from_same_pulse(self):
        graph=mermaid_dag();self.assertIn('N+1 feedback only',graph)
        self.assertNotIn('N --> MI',graph)
        self.assertIn('S 01',mermaid_sipoc())
        self.assertIn('N+3',mermaid_spline())

    def test_nested_rogue_objects_fail_controlled(self):
        for forged in ({},[],None,'garbage',{'schema':'fake'}):
            with self.subTest(forged=forged),self.assertRaises(DisjointScaleError):plan(forged)

    def test_cli_creates_three_diagrams_and_zero_workers(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            d=Path(d); src=d/'in.json';src.write_text(json.dumps(manifest()))
            out=d/'out'/'plan.json';images=d/'diagrams'
            self.assertEqual(main(['--manifest',str(src),'--output',str(out),'--diagrams',str(images),'--slots','3']),0)
            self.assertTrue(all((images/name).exists() for name in ('W6_DISJOINT_DAG.mmd','W6_DISJOINT_SIPOC.mmd','W6_DISJOINT_SPLINE.mmd')))
            self.assertEqual(json.loads(out.read_text())['workers_launched'],0)


if __name__ == '__main__':unittest.main()


class W6MalformedAndReverseTests(unittest.TestCase):
    def test_missing_population_and_unknown_authority(self):
        for key,val in (("requests",None),("not_dispatched",None),("engineering_acceptance",None),
                        ("mode","EXECUTE"),("eligible_repos",999)):
            m=manifest();m[key]=val
            with self.subTest(key=key),self.assertRaises(DisjointScaleError):plan(m)

    def test_foreign_lane_stays_rejected_even_if_count_is_three(self):
        m=manifest();m['requests'][0]['repo']='GBOGEB/other'
        with self.assertRaises(DisjointScaleError):plan(m)

    def test_mixed_route_selector_and_bad_wave_rejected(self):
        m=manifest();m['requests'][1]['selector']='native_checks'
        with self.assertRaises(DisjointScaleError):plan(m)
        m=manifest();m['wave']='/'
        with self.assertRaises(DisjointScaleError):plan(m)
        m=manifest();m.pop('wave')
        with self.assertRaises(DisjointScaleError):plan(m)

    def test_corrupted_recomputed_checksum_still_cannot_promote(self):
        from metric_atlas.census import canonical
        import hashlib
        m=manifest();x=plan(m)
        for key,value in (("execution_authority","GITHUB_EXECUTE"),
                          ("dispatch_performed",True),
                          ("merge_admission","GO"),
                          ("workers_launched",3),
                          ("native_tests_credited",888)):
            clone=copy.deepcopy(x);clone[key]=value
            clone['plan_sha256']=hashlib.sha256(canonical({k:v for k,v in clone.items() if k!='plan_sha256'}).encode()).hexdigest()
            with self.subTest(key=key),self.assertRaises(DisjointScaleError):verify_plan(m,clone)

    def test_plan_missing_and_wrong_checksum_rejected(self):
        m=manifest()
        for val in (None,{},[],{'schema':'WRONG'}):
            with self.subTest(value=val),self.assertRaises(DisjointScaleError):verify_plan(m,val)
        x=plan(m);x['plan_sha256']='bad'
        with self.assertRaises(DisjointScaleError):verify_plan(m,x)

    def test_empty_unknown_manifest_does_not_crash(self):
        m=manifest((0,0,0),fanout=1)
        self.assertEqual(verify_plan(m,plan(m)),plan(m))
        self.assertEqual(plan(m)['route_population'],0)

    def test_duplicate_const_guard_and_route_cap(self):
        from unittest.mock import patch
        from metric_atlas import disjoint_scale
        with patch.object(disjoint_scale,'ROUTES',('native_checks','native_checks')):
            with self.assertRaises(DisjointScaleError):plan(manifest(),slots=3)
        with patch.object(disjoint_scale,'ROUTES',('native_checks','coverage_catalog','fake_a','fake_b')):
            with self.assertRaises(DisjointScaleError):plan(manifest(),slots=3)

    def test_cli_bad_input_exits_before_writes(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            d=Path(d)
            f=d/'bad.json';f.write_text(json.dumps({'bad':'data'}))
            with self.assertRaises(SystemExit) as err:
                main(['--manifest',str(f),'--output',str(d/'unused.json'),'--diagrams',str(d/'unused')])
            self.assertEqual(err.exception.code,2)
            self.assertFalse((d/'unused.json').exists())
