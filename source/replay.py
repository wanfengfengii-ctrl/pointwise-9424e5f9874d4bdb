from dataclasses import dataclass

from source.completion import ReplayCompletion
from source.events import Event, decode_event
from source.format import read_recording_records
from source.opening import OpenedRecording, RecordingOrigin


@dataclass(frozen=True, slots=True)
class ReplayRecord:
    origin: RecordingOrigin
    events: tuple[Event, ...]


def replay_events(opened: OpenedRecording) -> ReplayRecord:
    completion = ReplayCompletion()
    events = []
    for record in read_recording_records(opened.content):
        event = decode_event(record)
        completion.observe(event)
        events.append(event)
    completion.finish()
    return ReplayRecord(opened.origin, tuple(events))
