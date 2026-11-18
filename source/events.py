from dataclasses import dataclass

from source.format import RecordingRecord
from source.opening import RecordingError

TURN_LENGTH = 10


@dataclass(frozen=True, slots=True)
class ReadingEvent:
    number: int
    slot: int
    tick: int
    value: int


@dataclass(frozen=True, slots=True)
class MarkEvent:
    number: int
    slot: int
    position: int


@dataclass(frozen=True, slots=True)
class EndEvent:
    number: int


Event = ReadingEvent | MarkEvent | EndEvent


def _integer(record: RecordingRecord, name: str) -> int:
    value = record.fields.get(name)
    if type(value) is not int:
        raise RecordingError(f'event {record.number}: {name} must be an integer')
    return value


def decode_event(record: RecordingRecord) -> Event:
    kind = record.fields.get('kind')
    if kind == 'end':
        return EndEvent(record.number)
    if kind not in ('reading', 'mark'):
        raise RecordingError(f'event {record.number}: unknown event kind')
    slot = _integer(record, 'slot')
    if slot < 0:
        raise RecordingError(f'event {record.number}: negative slot number')
    if kind == 'mark':
        return MarkEvent(record.number, slot, _integer(record, 'position'))
    tick = _integer(record, 'tick')
    if not 0 <= tick < TURN_LENGTH:
        raise RecordingError(f'event {record.number}: tick must be from 0 to {TURN_LENGTH - 1}')
    return ReadingEvent(record.number, slot, tick, _integer(record, 'value'))
