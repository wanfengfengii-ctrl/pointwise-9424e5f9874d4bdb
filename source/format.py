import json
from collections.abc import Iterator
from dataclasses import dataclass
from decimal import Decimal

from source.opening import RecordingError


@dataclass(frozen=True, slots=True)
class RecordingRecord:
    number: int
    fields: dict[str, object]


def parse_integer(text: str) -> int:
    return int(Decimal(text))


def integer_text(value: int) -> str:
    return format(Decimal(value), 'f')


def encode_json(value: object) -> str:
    """Encode station data with exact integer tokens and stable field order."""
    if type(value) is int:
        return integer_text(value)
    if isinstance(value, dict):
        fields = (json.dumps(key) + ':' + encode_json(item) for key, item in value.items())
        return '{' + ','.join(fields) + '}'
    if isinstance(value, (list, tuple)):
        return '[' + ','.join(encode_json(item) for item in value) + ']'
    return json.dumps(value, allow_nan=False)


def _unique_fields(pairs: list[tuple[str, object]]) -> dict[str, object]:
    fields = {}
    for key, value in pairs:
        if key in fields:
            raise ValueError(f'duplicate field {key!r}')
        fields[key] = value
    return fields


def _reject_constant(token: str) -> None:
    raise ValueError(f'invalid JSON token {token}')


def read_recording_records(content: bytes) -> Iterator[RecordingRecord]:
    lines = content.split(b'\n')
    if lines[-1] == b'':
        lines.pop()
    for number, line in enumerate(lines, start=1):
        try:
            fields = json.loads(
                line.decode('utf-8'),
                parse_int=parse_integer,
                parse_constant=_reject_constant,
                object_pairs_hook=_unique_fields,
            )
        except (ValueError, RecursionError) as error:
            raise RecordingError(f'event {number}: malformed JSON record: {error}') from error
        if not isinstance(fields, dict):
            raise RecordingError(f'event {number}: expected a JSON object')
        yield RecordingRecord(number, fields)
