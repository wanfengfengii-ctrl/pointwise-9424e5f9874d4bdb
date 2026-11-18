from dataclasses import replace
from hashlib import sha256

from archive.issue import InvalidEvidence, IssueWriteError, issue_manifest
from archive.locate import NoTrajectory
from archive.manifest import ManifestRow
from archive.receipts import IssueReceipt
from capture.packs import EvidenceSlot
from handoff.evidence import get_evidence
from handoff.lookup import get_manifest
from tests.fixtures import StationCase, end, mark, reading


class IssueTests(StationCase):
    def test_normal_offline_issue(self):
        source, captured = self.capture_sample('normal')
        source_path = str(source.resolve())
        digest = sha256(source.read_bytes()).hexdigest()
        source.unlink()
        self.reopen()
        evidence = get_evidence(self.db, captured.evidence_id)
        self.assertEqual(evidence, captured)
        self.assertEqual((evidence.origin.path, evidence.origin.sha256), (source_path, digest))
        self.assertEqual((evidence.line_id, evidence.run_id), ('ring', 'normal'))
        self.assertEqual(evidence.slots, (
            EvidenceSlot(0, 0, 8, 1, 0, 2),
            EvidenceSlot(1, 3, 17, 3),
            EvidenceSlot(2, 6, 5, 4, 6, 5),
        ))
        self.assertIsNone(get_evidence(self.db, 99999))
        result = issue_manifest(self.db, evidence)
        self.assertEqual(result.manifest.rows, (
            ManifestRow(0, 0, 8, 0), ManifestRow(1, 3, 17, 3), ManifestRow(2, 6, 5, 6),
        ))
        self.assertEqual(result.receipt, IssueReceipt(result.manifest.manifest_id, evidence.evidence_id))
        self.assertEqual(get_manifest(self.db, result.manifest.manifest_id), result)
        self.assertEqual(self.publication_counts(), (1, 1, 1))

    def test_full_turn_pipeline(self):
        source, captured = self.capture_sample('full_turn')
        self.assertEqual(tuple(slot.value for slot in captured.slots), (4, 19, 6))
        source.unlink()
        result = issue_manifest(self.db, get_evidence(self.db, captured.evidence_id))
        self.assertEqual(result.manifest.rows, (
            ManifestRow(0, 0, 4, 0), ManifestRow(1, 0, 19, 10), ManifestRow(2, 0, 6, 20),
        ))
        self.assertEqual(result.receipt.evidence_id, captured.evidence_id)
        self.reopen()
        self.assertEqual(get_manifest(self.db, result.manifest.manifest_id), result)

    def test_full_turn_with_independent_evidence(self):
        pack = self.manual_pack('full_turn', (
            EvidenceSlot(0, 0, 4, 1, 0, 2),
            EvidenceSlot(1, 0, 19, 3),
            EvidenceSlot(2, 0, 6, 4, 20, 5),
        ))
        delivery = issue_manifest(self.db, pack)
        self.assertEqual([(row.value, row.position) for row in delivery.manifest.rows],
                         [(4, 0), (19, 10), (6, 20)])
        self.assertEqual(delivery.receipt.evidence_id, pack.evidence_id)

    def test_ambiguous_histories_that_merge(self):
        pack = self.manual_pack('ambiguous', (
            EvidenceSlot(0, 0, 11, 1, 0, 2),
            EvidenceSlot(1, 0, 22, 3),
            EvidenceSlot(2, 0, 33, 4),
            EvidenceSlot(3, 0, 44, 5, 0, 6),
            EvidenceSlot(4, 0, 55, 7, 0, 8),
        ))
        result = issue_manifest(self.db, pack)
        self.assertEqual(tuple(row.position for row in result.manifest.rows), (0, None, None, 0, 0))
        self.assertEqual(tuple(row.value for row in result.manifest.rows), (11, 22, 33, 44, 55))
        self.assertEqual(result.receipt.evidence_id, pack.evidence_id)
        self.assertEqual(self.publication_counts(), (1, 1, 1))

    def test_rejects_inconsistent_steps_and_terminal_anchor(self):
        source, change_conflict = self.capture_sample('rejected')
        source.unlink()
        terminal_source = self.recording('terminal', [reading(0, 0, 3), mark(0, 0),
            reading(1, 1, 7), reading(2, 0, 12), mark(2, 20), end()])
        terminal_conflict = self.capture('terminal', terminal_source)
        terminal_source.unlink()
        for pack in (change_conflict, terminal_conflict):
            with self.subTest(run_id=pack.run_id):
                with self.assertRaises(NoTrajectory):
                    issue_manifest(self.db, pack)
                self.assertEqual(self.publication_counts(), (0, 0, 0))
                self.assertEqual(get_evidence(self.db, pack.evidence_id), pack)

    def test_negative_single_slot_and_integer_round_trip(self):
        for name, position, value in [('single', -1, 7), ('large', -(10**100) - 1, 10**110)]:
            with self.subTest(name=name):
                source = self.recording(name, [mark(0, position), reading(0, 9, value), end()])
                original = self.capture(name, source)
                source.unlink()
                self.reopen()
                pack = get_evidence(self.db, original.evidence_id)
                self.assertEqual((pack.slots[0].mark, pack.slots[0].mark_event), (position, 1))
                result = issue_manifest(self.db, pack)
                self.reopen()
                stored = get_manifest(self.db, result.manifest.manifest_id)
                self.assertEqual(stored.manifest.rows, (ManifestRow(0, 9, value, position),))
                self.assertEqual(stored.receipt.evidence_id, original.evidence_id)

    def test_invalid_and_altered_evidence_cannot_publish(self):
        _, pack = self.capture_sample('normal')
        invalid = replace(pack, slots=pack.slots[1:])
        altered = replace(pack, slots=(replace(pack.slots[0], value=99), *pack.slots[1:]))
        for candidate in (invalid, altered):
            with self.assertRaises(InvalidEvidence):
                issue_manifest(self.db, candidate)
            self.assertEqual(self.publication_counts(), (0, 0, 0))
        self.assertEqual(get_evidence(self.db, pack.evidence_id), pack)


class RollbackTests(StationCase):
    def test_issue_rollback_and_retry_once(self):
        source, pack = self.capture_sample('normal')
        source.unlink()
        with self.assertRaisesRegex(IssueWriteError, 'before issue commit'):
            issue_manifest(self.db, pack, fail_before_commit=True)
        self.reopen()
        self.assertEqual(self.publication_counts(), (0, 0, 0))
        self.assertEqual(self.db.execute('SELECT count(*) FROM manifest_rows').fetchone()[0], 0)
        self.assertIsNone(get_manifest(self.db, 1))
        self.assertEqual(get_evidence(self.db, pack.evidence_id), pack)
        recovered = issue_manifest(self.db, get_evidence(self.db, pack.evidence_id))
        self.reopen()
        self.assertEqual(get_manifest(self.db, recovered.manifest.manifest_id), recovered)
        self.assertEqual(recovered.receipt, IssueReceipt(recovered.manifest.manifest_id, pack.evidence_id))
        self.assertEqual([row.position for row in recovered.manifest.rows], [0, 3, 6])
        self.assertEqual(issue_manifest(self.db, pack), recovered)
        self.assertEqual(self.publication_counts(), (1, 1, 1))
