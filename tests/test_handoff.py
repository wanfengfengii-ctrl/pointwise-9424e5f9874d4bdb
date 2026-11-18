import json

from handoff.evidence import get_evidence
from handoff.export import ExportError, export_manifest
from handoff.lookup import get_manifest
from runs.lifecycle import RunStage
from runs.lines import find_line
from runs.store import initialize_store, load_run_record
from tests.fixtures import StationCase


class HandoffTests(StationCase):
    def test_two_issued_runs_keep_history_and_exports(self):
        older = self.issue_sample('normal')
        newer = self.issue_sample('full_turn')
        self.assertNotEqual(older.manifest.manifest_id, newer.manifest.manifest_id)
        self.assertNotEqual(older.manifest.evidence_id, newer.manifest.evidence_id)
        self.assertEqual(older.manifest.line_id, newer.manifest.line_id)
        self.reopen()
        initialize_store(self.db)
        self.assertEqual(self.publication_counts(), (2, 2, 2))

        cases = [
            (older, 'normal', [(0, 0, 8, 0), (1, 3, 17, 3), (2, 6, 5, 6)]),
            (newer, 'full_turn', [(0, 0, 4, 0), (1, 0, 19, 10), (2, 0, 6, 20)]),
        ]
        for original, name, expected in cases:
            with self.subTest(run_id=name):
                manifest_id = original.manifest.manifest_id
                delivered = get_manifest(self.db, manifest_id)
                self.assertEqual(delivered, original)
                evidence = get_evidence(self.db, original.manifest.evidence_id)
                self.assertEqual(evidence.run_id, name)
                self.assertEqual(evidence.origin, delivered.manifest.origin)
                target = self.root / f'{name}-handoff.json'
                self.assertEqual(export_manifest(self.db, manifest_id, target), target)
                payload = json.loads(target.read_text(encoding='utf-8'))
                self.assertEqual(payload, {
                    'manifest_id': manifest_id,
                    'evidence_id': evidence.evidence_id,
                    'line_id': 'ring',
                    'run_id': name,
                    'origin': {'path': evidence.origin.path, 'sha256': evidence.origin.sha256},
                    'receipt': {'manifest_id': manifest_id, 'evidence_id': evidence.evidence_id},
                    'rows': [dict(zip(('slot', 'tick', 'value', 'position'), row)) for row in expected],
                })

    def test_initialization_keeps_line_edits_and_history(self):
        issued = self.issue_sample('normal')
        run = load_run_record(self.db, 'ring', 'normal')
        self.assertEqual(run.stage, RunStage.RECORDED)
        self.assertEqual(find_line(self.db, 'ring').display_name, '检修环线')
        self.db.execute('UPDATE lines SET display_name = ? WHERE line_id = ?', ('北段检修环线', 'ring'))
        initialize_store(self.db)
        initialize_store(self.db)
        self.reopen()
        self.assertEqual(find_line(self.db, 'ring').display_name, '北段检修环线')
        self.assertEqual(load_run_record(self.db, 'ring', 'normal'), run)
        self.assertEqual(get_manifest(self.db, issued.manifest.manifest_id), issued)
        self.assertEqual(self.publication_counts(), (1, 1, 1))

    def test_unknown_positions_export_as_null(self):
        issued = self.issue_sample('ambiguous')
        self.reopen()
        manifest_id = issued.manifest.manifest_id
        retrieved = get_manifest(self.db, manifest_id)
        expected = [(0, 11, 0), (1, 22, None), (2, 33, None), (3, 44, 0), (4, 55, 0)]
        self.assertEqual([(row.slot, row.value, row.position) for row in retrieved.manifest.rows], expected)
        target = export_manifest(self.db, manifest_id, self.root / 'handoff.json')
        payload = json.loads(target.read_text(encoding='utf-8'))
        self.assertEqual([(row['slot'], row['value'], row['position']) for row in payload['rows']], expected)
        for index in (0, 3, 4):
            self.assertIs(type(payload['rows'][index]['position']), int)
        self.assertIsNone(payload['rows'][1]['position'])
        self.assertIsNone(payload['rows'][2]['position'])
        self.assertEqual(payload['evidence_id'], issued.manifest.evidence_id)
        self.assertEqual(payload['receipt']['manifest_id'], manifest_id)
        self.assertEqual(payload['receipt']['evidence_id'], issued.receipt.evidence_id)

    def test_export_failure_preserves_previous_delivery(self):
        older = self.issue_sample('normal')
        newer = self.issue_sample('ambiguous')
        target = export_manifest(self.db, older.manifest.manifest_id, self.root / 'handoff.json')
        original = target.read_bytes()
        with self.assertRaisesRegex(ExportError, 'before handoff replacement'):
            export_manifest(self.db, newer.manifest.manifest_id, target, fail_before_replace=True)
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(json.loads(original)['manifest_id'], older.manifest.manifest_id)
        self.assertEqual(list(self.root.glob('.handoff-*')), [])
        self.assertIsNone(get_manifest(self.db, 99999))
        with self.assertRaisesRegex(ExportError, 'unknown manifest'):
            export_manifest(self.db, 99999, target)
        self.assertEqual(target.read_bytes(), original)
        with self.assertRaisesRegex(ExportError, 'could not export'):
            export_manifest(self.db, newer.manifest.manifest_id, self.root / 'absent' / 'handoff.json')
        self.assertEqual(get_manifest(self.db, newer.manifest.manifest_id), newer)
