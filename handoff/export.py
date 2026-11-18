import os
from pathlib import Path
from sqlite3 import Connection
from tempfile import NamedTemporaryFile

from handoff.lookup import get_manifest
from handoff.render import render_manifest


class ExportError(RuntimeError):
    """A manifest could not be handed off at the requested destination."""


def export_manifest(
    db: Connection, manifest_id: int, destination: str | Path, *, fail_before_replace: bool = False
) -> Path:
    delivery = get_manifest(db, manifest_id)
    if delivery is None:
        raise ExportError(f'unknown manifest {manifest_id}')
    content = render_manifest(delivery)
    target = Path(destination)
    temporary_path = None
    try:
        with NamedTemporaryFile(
            mode='w', encoding='utf-8', newline='\n', dir=target.parent, prefix='.handoff-', delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(content)
        if fail_before_replace:
            raise OSError('injected failure before handoff replacement')
        os.replace(temporary_path, target)
    except OSError as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                error.add_note(f'failed to remove handoff temporary file: {cleanup_error}')
        raise ExportError(f'could not export manifest {manifest_id}: {error}') from error
    return target
