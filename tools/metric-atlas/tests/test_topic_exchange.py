"""Offline, synthetic-only source, ACK, receipt and anti-recensus proof gates."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'metric_atlas' / 'topic_exchange.py'
spec = importlib.util.spec_from_file_location('topic_exchange', SOURCE)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
A = 'a' * 40
B = 'b' * 40
X = '1' * 64
Y = '2' * 64
Z = '3' * 64
T0 = '2026-10-28T09:00:00Z'
T1 = '2026-10-28T09:10:00Z'
T2 = '2026-10-28T10:00:00Z'
T3 = '2026-10-29T09:00:00Z'


def make_packet(**kwargs):
    fields = dict(topic='electrical.icd.feeders', producer_repo='GBOGEB/cryoplant-project',
                  producer_head=A, scope_sha256=X, source_sha256=Y, receipt_sha256=Z,
                  recipients=['GBOGEB/pipeline-automation-hub', 'GBOGEB/cryoplant-project'],
                  sequence=1, observed_at=T0, expires_at=T3)
    fields.update(kwargs)
    return t.create_packet(**fields)


def publication(packet):
    return t.make_publication(packet, transport='GITHUB_PR_COMMENT',
                              locator='https://github.com/GBOGEB/cryoplant-project/pull/2162#issuecomment-42',
                              evidence_id='42', observed_at=T1)


def ack(packet, pub, **kwargs):
    args = dict(recipient='GBOGEB/pipeline-automation-hub', recipient_head=B,
                ack_at=T2, proof_locator='https://github.com/GBOGEB/pipeline-automation-hub/issues/123#issuecomment-43',
                proof_id='43', externally_verified=True)
    args.update(kwargs)
    return t.create_ack(packet, pub, **args)


def decision(packet, **kwargs):
    args = dict(recipient='GBOGEB/pipeline-automation-hub',current_head=A,
                current_scope_sha256=X,current_source_sha256=Y,at=T2)
    args.update(kwargs)
    return t.decide(packet, **args)


class PacketIntegrity(unittest.TestCase):
    def test_deterministic_recipient_order_and_hash(self):
        one = make_packet()
        other = make_packet(recipients=list(reversed(one['recipients'])))
        self.assertEqual(one, other)
        self.assertEqual(t.verify_packet(one), one)

    def test_invalid_topic_or_repo_denied(self):
        with self.assertRaises(t.ExchangeError):
            make_packet(topic='A')
        with self.assertRaises(t.ExchangeError):
            make_packet(producer_repo='not-a-repo')

    def test_source_hash_drift_invalidates_digest(self):
        p = make_packet()
        p['source_sha256'] = X
        with self.assertRaisesRegex(t.ExchangeError, 'PACKET_DIGEST_MISMATCH'):
            t.verify_packet(p)

    def test_unexpected_authority_flag_rejected(self):
        p = make_packet(); p['merge_authorized'] = True
        p['packet_sha256'] = t.digest({k:v for k,v in p.items() if k != 'packet_sha256'})
        with self.assertRaisesRegex(t.ExchangeError, 'PACKET_CONTAINS_UNSUPPORTED_CLAIM'):
            t.verify_packet(p)

    def test_recipients_must_be_unique_and_bounded(self):
        for group in ([], ['GBOGEB/CODEX']*2, ['GBOGEB/'+str(i) for i in range(9)]):
            with self.subTest(group=group), self.assertRaisesRegex(t.ExchangeError, 'INVALID_RECIPIENTS'):
                make_packet(recipients=group)

    def test_invalid_head_and_scope(self):
        for bad in ('a'*39,'a'*41,'A'*40):
            with self.subTest(bad=bad), self.assertRaises(t.ExchangeError):
                make_packet(producer_head=bad)
        with self.assertRaises(t.ExchangeError):
            make_packet(scope_sha256=A)

    def test_no_bogus_sequence_chain(self):
        with self.assertRaisesRegex(t.ExchangeError, 'MISSING_PREVIOUS_PACKET'):
            make_packet(sequence=2)
        with self.assertRaisesRegex(t.ExchangeError, 'MISSING_PREVIOUS_PACKET'):
            make_packet(sequence=1,prior_packet_sha256=Z)
        p = make_packet(sequence=2,prior_packet_sha256=X)
        t.verify_packet(p)

    def test_ttl_must_be_bounded(self):
        for expires in (T0,'2026-11-07T10:00:00Z'):
            with self.subTest(expires=expires), self.assertRaisesRegex(t.ExchangeError, 'UNBOUNDED_OR_NEGATIVE_TTL'):
                make_packet(expires_at=expires)
        with self.assertRaisesRegex(t.ExchangeError, 'NON_UTC_TIMESTAMP'):
            make_packet(observed_at='2026-10-28T09:00:00+01:00')

    def test_bad_timestamp_format_denied(self):
        with self.assertRaisesRegex(t.ExchangeError,'INVALID_TIMESTAMP'):
            make_packet(expires_at='2026-99-28T10:00:00Z')

    def test_cli_roundtrip_staged(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=make_packet()
            (root/'packet.json').write_text(json.dumps(p),encoding='utf-8')
            (root/'current.json').write_text(json.dumps(dict(recipient='GBOGEB/pipeline-automation-hub',
                current_head=A,current_scope_sha256=X,current_source_sha256=Y,at=T2)),encoding='utf-8')
            args=['--packet',str(root/'packet.json'),'--current',str(root/'current.json'),
                  '--out',str(root/'decision.json')]
            t.main(args)
            self.assertEqual(json.loads((root/'decision.json').read_text())['decision'],'STAGED_NOT_DELIVERED')

    def test_packet_is_data_only(self):
        p = make_packet()
        self.assertEqual(p['transport'],'STAGED_ONLY')
        self.assertFalse(p['source_mutation'])
        self.assertFalse(p['engineering_approval'])
        self.assertFalse(p['authority_transfer'])


class Acknowledgments(unittest.TestCase):
    def test_staged_packet_never_claims_delivery(self):
        self.assertEqual(decision(make_packet())['decision'],'STAGED_NOT_DELIVERED')

    def test_published_is_not_acknowledged(self):
        p = make_packet(); pub=publication(p)
        self.assertEqual(decision(p,publication=pub)['decision'],'PULL_EXISTING_PACKET_NO_RECENSUS')

    def test_unverified_ack_still_pulls(self):
        p = make_packet(); pub = publication(p)
        pending = ack(p,pub,externally_verified=False)
        self.assertEqual(decision(p,publication=pub,acknowledgments=[pending])['decision'],
                         'PULL_EXISTING_PACKET_NO_RECENSUS')

    def test_verified_ack_skips_topic_recensus(self):
        p = make_packet(); pub = publication(p)
        saved = decision(p,publication=pub,acknowledgments=[ack(p,pub)])
        self.assertEqual(saved['decision'],'REUSE_ACKNOWLEDGED_NO_RECENSUS')
        self.assertFalse(saved['producer_recensus_required'])
        self.assertFalse(saved['recipient_pull_required'])
        self.assertFalse(saved['ci_retest_authorized'])

    def test_ack_wrong_packet_or_publication_is_not_transferable(self):
        p = make_packet(); pub = publication(p); a=ack(p,pub)
        q=make_packet(source_sha256=X)
        with self.assertRaises(t.ExchangeError):
            decision(q,publication=publication(q),acknowledgments=[a],current_source_sha256=X)

    def test_unsubscribed_ack_rejected(self):
        p=make_packet(); pub=publication(p)
        with self.assertRaisesRegex(t.ExchangeError, 'UNSUBSCRIBED'):
            ack(p,pub,recipient='GBOGEB/ABACUS')

    def test_ack_after_publication(self):
        p=make_packet(); pub=publication(p)
        with self.assertRaisesRegex(t.ExchangeError,'ACK_BEFORE_PUBLICATION'):
            ack(p,pub,ack_at=T0)

    def test_conflicting_ack_for_same_recipient_rejected(self):
        p=make_packet(); pub=publication(p)
        a=ack(p,pub)
        b=ack(p,pub,proof_id='new')
        with self.assertRaisesRegex(t.ExchangeError, 'CONFLICTING_RECIPIENT_ACKS'):
            decision(p,publication=pub,acknowledgments=[a,b])

    def test_fake_publication_transport_denied(self):
        with self.assertRaisesRegex(t.ExchangeError,'UNSUPPORTED_PUBLICATION_TRANSPORT'):
            t.make_publication(make_packet(),transport='EMAIL',locator='https://example.com',
                               evidence_id='1',observed_at=T1)

    def test_corrupted_ack_digest_rejected(self):
        p=make_packet(); pub=publication(p); a=ack(p,pub)
        a['proof_id']='fake'
        with self.assertRaisesRegex(t.ExchangeError,'ACK_DIGEST_MISMATCH'):
            decision(p,publication=pub,acknowledgments=[a])

    def test_publication_wrong_packet_rejected(self):
        p=make_packet(); pub=publication(p)
        with self.assertRaises(t.ExchangeError):
            decision(make_packet(source_sha256=X),publication=pub,current_source_sha256=X)

    def test_not_subscribed_is_not_reuse(self):
        self.assertEqual(decision(make_packet(),recipient='GBOGEB/ABACUS')['decision'], 'NOT_SUBSCRIBED')


class TargetedInvalidation(unittest.TestCase):
    def test_source_drift_only_targeted_recensus(self):
        res=decision(make_packet(),current_source_sha256=Z)
        self.assertEqual(res['decision'],'TARGETED_RECENSUS_REQUIRED')
        self.assertTrue(res['producer_recensus_required'])

    def test_scope_drift_only_targeted_recensus(self):
        self.assertEqual(decision(make_packet(),current_scope_sha256=Y)['decision'],
                         'TARGETED_RECENSUS_REQUIRED')

    def test_pub_hash_drift_rejected(self):
        p=make_packet(); pub=publication(p)
        pub['locator']='https://other.invalid'
        with self.assertRaisesRegex(t.ExchangeError,'PUBLICATION_DIGEST_MISMATCH'):
            decision(p,publication=pub)

    def test_expiry_requires_recensus_even_when_acknowledged(self):
        p=make_packet(); pub=publication(p)
        self.assertEqual(decision(p,publication=pub,acknowledgments=[ack(p,pub)],at=T3)['decision'],
                         'TARGETED_RECENSUS_REQUIRED')

    def test_latest_sequence_cannot_be_older_than_packet(self):
        p=make_packet(sequence=2,prior_packet_sha256=X)
        with self.assertRaisesRegex(t.ExchangeError,'INVALID_LATEST_SEQUENCE'):
            decision(p,latest_sequence=1)

    def test_decision_before_source_observation_denied(self):
        with self.assertRaisesRegex(t.ExchangeError,'DECISION_BEFORE_OBSERVATION'):
            decision(make_packet(),at='2026-10-28T08:00:00Z')

    def test_unrelated_head_advance_requires_bridge_not_full_rescan(self):
        p=make_packet(); pub=publication(p)
        self.assertEqual(decision(p,publication=pub,acknowledgments=[ack(p,pub)],current_head=B)['decision'],
                         'VERIFY_HEAD_BRIDGE_NO_FULL_RECENSUS')

    def test_newer_packet_forces_targeted_pull(self):
        p=make_packet(); pub=publication(p)
        self.assertEqual(decision(p,publication=pub,latest_sequence=2)['decision'],
                         'STALE_PACKET_PULL_LATEST')

    def test_invalidated_receipt_forces_targeted_pull(self):
        self.assertEqual(decision(make_packet(), invalidated=True)['decision'],
                         'STALE_PACKET_PULL_LATEST')

    def test_unchanged_topic_cannot_skip_ci_proof(self):
        p=make_packet(evidence_class='EXACT_HEAD_CI_OBSERVATION'); pub=publication(p)
        res=decision(p,publication=pub,acknowledgments=[ack(p,pub)])
        self.assertFalse(res['ci_retest_authorized'])
        self.assertFalse(res['merge_authorized'])


class EventLedger(unittest.TestCase):
    def append(self, led, kind='STAGED', recipient=None, evidence=Z, expected=None):
        return t.append_event(led,kind=kind,topic='electrical.icd.feeders',packet_sha256=X,
                              recipient=recipient,evidence_sha256=evidence,
                              at=T0,expected_tail_sha256=expected)

    def test_invalid_event_scope_denied(self):
        with self.assertRaisesRegex(t.ExchangeError,'INVALID_EVENT_KIND'):
            self.append(t.new_ledger(),kind='MERGE')
        with self.assertRaisesRegex(t.ExchangeError,'BAD_EVENT_RECIPIENT'):
            self.append(t.new_ledger(),recipient='not a repo')

    def test_chain_append_and_validate(self):
        a=self.append(t.new_ledger())
        b=self.append(a,kind='PUBLICATION_POSTED',expected=a['tail_sha256'])
        self.assertEqual(len(b['events']),2)
        t.validate_ledger(b)

    def test_exact_replay_is_idempotent(self):
        a=self.append(t.new_ledger())
        b=self.append(a,expected=None)
        self.assertEqual(a,b)

    def test_conflicting_replay_is_rejected(self):
        a=self.append(t.new_ledger())
        with self.assertRaisesRegex(t.ExchangeError,'CONFLICTING_REPLAY'):
            self.append(a,evidence=Y,expected=a['tail_sha256'])

    def test_stale_cas_disallows_concurrent_second_writer(self):
        a=self.append(t.new_ledger())
        with self.assertRaisesRegex(t.ExchangeError,'STALE_TAIL_CAS'):
            self.append(a,kind='PUBLICATION_POSTED',expected=None)

    def test_tamper_broken_chain_detected(self):
        a=self.append(t.new_ledger())
        b=self.append(a,kind='PUBLICATION_POSTED',expected=a['tail_sha256'])
        b['events'][1]['previous_event_sha256']=Y
        with self.assertRaisesRegex(t.ExchangeError,'BROKEN_EVENT_CHAIN'):
            t.validate_ledger(b)

    def test_authority_escalation_denied(self):
        a=t.new_ledger(); a['merge_authorized']=True
        with self.assertRaisesRegex(t.ExchangeError,'INVALID_LEDGER'):
            t.validate_ledger(a)

    def test_ledger_duplicate_event_id_rejected(self):
        a=self.append(t.new_ledger())
        b=copy.deepcopy(a)
        b['events'].append(copy.deepcopy(a['events'][0]))
        with self.assertRaises(t.ExchangeError):
            t.validate_ledger(b)

    def test_no_raw_consumer_or_bidder_payload_in_event(self):
        a=self.append(t.new_ledger())
        self.assertEqual(set(a['events'][0]),{'kind','topic','packet_sha256','recipient',
                          'evidence_sha256','at','event_id','previous_event_sha256','event_sha256'})


if __name__=='__main__':
    unittest.main()
