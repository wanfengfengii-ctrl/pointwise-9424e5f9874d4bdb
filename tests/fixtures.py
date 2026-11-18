import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.issue import issue_manifest
from capture.freeze import capture_run
from capture.packs import EvidencePack, persist_pack
from handoff.evidence import get_evidence
from runs.register import open_run
from runs.store import initialize_store, open_store, write_transaction


SAMPLES = Path(__file__).resolve().parents[1] / 'samples'


def reading(slot, tick, value):
    return {'kind': 'reading', 'slot': slot, 'tick': tick, 'value': value}


def mark(slot, position):
    return {'kind': 'mark', 'slot': slot, 'position': position}


def end():
    return {'kind': 'end'}


class StationCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.db_path = self.root / 'station.sqlite'
        self.db = open_store(self.db_path)
        self.addCleanup(lambda: self.db.close())
        initialize_store(self.db)

    def reopen(self):
        self.db.close()
        self.db = open_store(self.db_path)

    def sample(self, name):
        filename = f'{name}.jsonl'
        source = self.root / filename
        shutil.copyfile(SAMPLES / filename, source)
        return source

    def recording(self, name, events):
        source = self.root / f'{name}.jsonl'
        source.write_text(''.join(json.dumps(event) + '\n' for event in events), encoding='utf-8')
        return source

    def capture(self, run_id, source):
        open_run(self.db, 'ring', run_id, source)
        evidence_id = capture_run(self.db, 'ring', run_id)
        pack = get_evidence(self.db, evidence_id)
        self.assertIsNotNone(pack)
        return pack

    def capture_sample(self, name):
        source = self.sample(name)
        return source, self.capture(name, source)

    def manual_pack(self, name, slots):
        source = self.sample(name)
        run = open_run(self.db, 'ring', name, source)
        with write_transaction(self.db):
            evidence = persist_pack(self.db, EvidencePack(None, 'ring', name, run.origin, tuple(slots)))
        source.unlink()
        return evidence

    def issue_sample(self, name):
        source, evidence = self.capture_sample(name)
        source.unlink()
        return issue_manifest(self.db, get_evidence(self.db, evidence.evidence_id))

    def evidence_count(self):
        return self.db.execute('SELECT count(*) FROM evidence_packs').fetchone()[0]

    def publication_counts(self):
        row = self.db.execute('''
            SELECT (SELECT count(*) FROM manifests), (SELECT count(*) FROM issue_receipts),
                   (SELECT count(*) FROM handoff_entries)
        ''').fetchone()
        return tuple(row)
