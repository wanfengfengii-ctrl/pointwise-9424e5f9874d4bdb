import shutil
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from archive.issue import issue_manifest
from archive.locate import NoTrajectory
from capture.freeze import capture_run
from handoff.evidence import get_evidence
from handoff.export import export_manifest
from runs.register import open_run
from runs.store import initialize_store, open_store
from source.format import encode_json


def main():
    samples = Path(__file__).resolve().parent / 'samples'
    with TemporaryDirectory(prefix='track-demo-') as directory:
        root = Path(directory)
        db_path = root / 'station.sqlite'
        issued_ids = {}
        with closing(open_store(db_path)) as db:
            initialize_store(db)
            for name in ('normal', 'full_turn', 'ambiguous', 'rejected'):
                source = root / f'{name}.jsonl'
                shutil.copyfile(samples / source.name, source)
                open_run(db, 'ring', name, source)
                evidence_id = capture_run(db, 'ring', name)
                source.unlink()
                pack = get_evidence(db, evidence_id)
                try:
                    delivery = issue_manifest(db, pack)
                except NoTrajectory as error:
                    if name != 'rejected':
                        raise
                    print(encode_json({'run_id': name, 'evidence_id': evidence_id,
                                       'status': 'rejected', 'reason': str(error)}))
                    continue
                if name == 'rejected':
                    raise RuntimeError('the contradictory recording received a manifest')
                issued_ids[name] = delivery.manifest.manifest_id

        with closing(open_store(db_path)) as db:
            initialize_store(db)
            for name, manifest_id in issued_ids.items():
                target = export_manifest(db, manifest_id, root / f'{name}-handoff.json')
                print(target.read_text(encoding='utf-8'), end='')


if __name__ == '__main__':
    main()
