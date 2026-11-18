from dataclasses import dataclass
from sqlite3 import Connection


@dataclass(frozen=True, slots=True)
class Line:
    line_id: str
    display_name: str


def install_line_schema(db: Connection) -> None:
    db.execute('''
        CREATE TABLE lines (
            line_id TEXT PRIMARY KEY NOT NULL,
            display_name TEXT NOT NULL
        )
    ''')


def seed_lines(db: Connection) -> None:
    db.execute(
        'INSERT INTO lines (line_id, display_name) VALUES (?, ?)',
        ('ring', '检修环线'),
    )


def find_line(db: Connection, line_id: str) -> Line | None:
    row = db.execute(
        'SELECT line_id, display_name FROM lines WHERE line_id = ?', (line_id,)
    ).fetchone()
    if row is None:
        return None
    return Line(row['line_id'], row['display_name'])
