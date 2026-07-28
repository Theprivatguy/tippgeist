"""Tipp-Logik, Kennzahlen und der Geist.

Ein Lauf zeichnet nicht nur das Ergebnis auf, sondern die komplette Fahrt:
`track` ist eine Liste von (Sekunden, Cursorposition). Damit lässt sich ein
alter Lauf später Zeichen für Zeichen nachspielen – das ist der Geist.
"""

from __future__ import annotations

import bisect
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple

Sample = Tuple[float, int]

# Ein "Wort" sind in der Tipp-Welt seit jeher fünf Anschläge.
CHARS_PER_WORD = 5.0


@dataclass
class Run:
    """Ein abgeschlossener Lauf, so wie er auf der Platte landet."""

    text_id: str
    title: str
    started_at: str
    duration: float
    wpm: float
    raw_wpm: float
    accuracy: float
    correct_chars: int
    typed_chars: int
    errors: int
    track: List[Sample] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["track"] = [[round(t, 3), p] for t, p in self.track]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Run":
        fields = set(cls.__dataclass_fields__)
        kwargs = {k: v for k, v in data.items() if k in fields}
        kwargs["track"] = [(float(t), int(p)) for t, p in kwargs.get("track", [])]
        return cls(**kwargs)


class Session:
    """Ein laufender Tippversuch.

    Der Cursor rückt bei jedem Anschlag vor – auch bei einem falschen. Falsche
    Zeichen bleiben rot stehen, bis sie weggelöscht werden. Die Uhr startet
    beim ersten Anschlag, nicht beim Aufbau des Bildschirms.
    """

    def __init__(self, text: str, clock: Callable[[], float] = time.monotonic):
        self.text = text
        self._clock = clock
        self.typed: List[str] = []
        self.start: Optional[float] = None
        self.end: Optional[float] = None
        self.keystrokes = 0
        self.errors = 0
        self.track: List[Sample] = [(0.0, 0)]

    @property
    def pos(self) -> int:
        return len(self.typed)

    @property
    def started(self) -> bool:
        return self.start is not None

    @property
    def finished(self) -> bool:
        return self.end is not None

    @property
    def progress(self) -> float:
        if not self.text:
            return 1.0
        return self.pos / len(self.text)

    def elapsed(self) -> float:
        if self.start is None:
            return 0.0
        stop = self.end if self.end is not None else self._clock()
        return max(0.0, stop - self.start)

    def press(self, char: str) -> None:
        if self.finished or self.pos >= len(self.text):
            return
        if self.start is None:
            self.start = self._clock()
        if char != self.text[self.pos]:
            self.errors += 1
        self.typed.append(char)
        self.keystrokes += 1
        if self.pos >= len(self.text):
            self.end = self._clock()
        self._record()

    def backspace(self) -> None:
        if self.finished or not self.typed:
            return
        self.typed.pop()
        self._record()

    def _record(self) -> None:
        self.track.append((round(self.elapsed(), 3), self.pos))

    # -- Kennzahlen ---------------------------------------------------------

    def correct_chars(self) -> int:
        return sum(1 for i, c in enumerate(self.typed) if c == self.text[i])

    def wpm(self) -> float:
        seconds = self.elapsed()
        if seconds <= 0:
            return 0.0
        return (self.correct_chars() / CHARS_PER_WORD) / (seconds / 60.0)

    def raw_wpm(self) -> float:
        seconds = self.elapsed()
        if seconds <= 0:
            return 0.0
        return (self.keystrokes / CHARS_PER_WORD) / (seconds / 60.0)

    def accuracy(self) -> float:
        if self.keystrokes == 0:
            return 100.0
        return 100.0 * (self.keystrokes - self.errors) / self.keystrokes

    def to_run(self, text_id: str, title: str) -> Run:
        return Run(
            text_id=text_id,
            title=title,
            started_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            duration=round(self.elapsed(), 3),
            wpm=round(self.wpm(), 2),
            raw_wpm=round(self.raw_wpm(), 2),
            accuracy=round(self.accuracy(), 2),
            correct_chars=self.correct_chars(),
            typed_chars=self.keystrokes,
            errors=self.errors,
            track=list(self.track),
        )


class Ghost:
    """Spielt einen alten Lauf in Echtzeit nach."""

    def __init__(self, run: Run):
        self.run = run
        track = [(float(t), int(p)) for t, p in run.track] or [(0.0, 0)]
        track.sort(key=lambda s: s[0])
        self.track = track
        self._times = [t for t, _ in track]

    @property
    def final_position(self) -> int:
        return self.track[-1][1]

    def position_at(self, elapsed: float) -> int:
        index = bisect.bisect_right(self._times, elapsed) - 1
        if index < 0:
            return 0
        return self.track[index][1]

    def time_at(self, position: int) -> Optional[float]:
        """Wann hatte der Geist diese Position erstmals erreicht?"""
        for seconds, pos in self.track:
            if pos >= position:
                return seconds
        return None


def wrap_indices(text: str, width: int) -> List[Tuple[int, int]]:
    """Zeilenumbruch, der die Zeichenindizes erhält.

    Jeder Index von 0 bis len(text)-1 liegt in genau einer Zeile – sonst
    würden Cursor und Geist an der falschen Stelle blinken. Das Leerzeichen
    an einer Umbruchstelle bleibt am Zeilenende sichtbar, weil es getippt
    werden muss.
    """
    width = max(10, width)
    lines: List[Tuple[int, int]] = []
    start, total = 0, len(text)
    while start < total:
        if total - start <= width:
            lines.append((start, total))
            break
        window_end = start + width
        cut = text.rfind(" ", start, window_end)
        end = cut + 1 if cut > start else window_end
        lines.append((start, end))
        start = end
    return lines


def line_of(lines: List[Tuple[int, int]], position: int) -> int:
    for index, (start, end) in enumerate(lines):
        if start <= position < end:
            return index
    return max(0, len(lines) - 1)
