from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


class RecordingError(ValueError):
    """A recording cannot be opened or interpreted."""


@dataclass(frozen=True, slots=True)
class RecordingOrigin:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class OpenedRecording:
    origin: RecordingOrigin
    content: bytes


def open_recording(path: str | Path) -> OpenedRecording:
    try:
        canonical_path = Path(path).resolve(strict=True)
        content = canonical_path.read_bytes()
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        raise RecordingError(f'cannot open recording {path!s}: {error}') from error

    origin = RecordingOrigin(str(canonical_path), sha256(content).hexdigest())
    return OpenedRecording(origin, content)
