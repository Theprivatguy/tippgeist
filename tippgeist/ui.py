"""Curses-Oberfläche: Rennstrecke, Text, Ergebnis.

Bewusst ohne Emoji – in der Terminalzelle sind die doppelt breit und
verschieben die ganze Spalte. Blockzeichen für die Balken sind schmal und
werden auf ASCII zurückgestuft, wenn das Terminal kein UTF-8 spricht.
"""

from __future__ import annotations

import curses
import locale
from typing import List, Optional, Tuple

from .engine import Ghost, Session, line_of, wrap_indices
from .texts import TextItem

C_CORRECT = 1
C_WRONG = 2
C_GHOST = 3
C_YOU = 4
C_ACCENT = 5
C_MUTED = 6

MIN_WIDTH = 46
MIN_HEIGHT = 12

_UNICODE = (locale.getpreferredencoding(False) or "").lower().replace("-", "") == "utf8"
FILL = "█" if _UNICODE else "#"
EMPTY = "░" if _UNICODE else "."
RULE = "─" if _UNICODE else "-"


def init_colors() -> None:
    try:
        curses.start_color()
        curses.use_default_colors()
    except curses.error:
        return
    curses.init_pair(C_CORRECT, curses.COLOR_GREEN, -1)
    curses.init_pair(C_WRONG, curses.COLOR_RED, -1)
    curses.init_pair(C_GHOST, curses.COLOR_CYAN, -1)
    curses.init_pair(C_YOU, curses.COLOR_YELLOW, -1)
    curses.init_pair(C_ACCENT, curses.COLOR_MAGENTA, -1)
    curses.init_pair(C_MUTED, curses.COLOR_WHITE, -1)


def pair(number: int) -> int:
    try:
        return curses.color_pair(number)
    except curses.error:
        return 0


def add(win, y: int, x: int, text: str, attr: int = 0) -> None:
    """addstr, das an der Bildschirmkante nicht das Programm abschießt."""
    height, width = win.getmaxyx()
    if y < 0 or y >= height or x >= width:
        return
    if x < 0:
        text = text[-x:]
        x = 0
    space = width - x
    if space <= 0:
        return
    text = text[:space]
    # Die letzte Zelle unten rechts wirft in curses grundsätzlich einen Fehler.
    if y == height - 1 and x + len(text) >= width:
        text = text[: width - x - 1]
    if not text:
        return
    try:
        win.addstr(y, x, text, attr)
    except (curses.error, UnicodeEncodeError):
        try:
            win.addstr(y, x, text.encode("ascii", "replace").decode(), attr)
        except curses.error:
            pass


def bar(fraction: float, width: int) -> str:
    width = max(4, width)
    filled = int(round(max(0.0, min(1.0, fraction)) * width))
    return FILL * filled + EMPTY * (width - filled)


def too_small(stdscr) -> bool:
    height, width = stdscr.getmaxyx()
    return height < MIN_HEIGHT or width < MIN_WIDTH


def _draw_too_small(stdscr) -> None:
    stdscr.erase()
    add(stdscr, 0, 0, "Terminal zu klein.", curses.A_BOLD)
    add(stdscr, 1, 0, "Mindestens %dx%d wird gebraucht." % (MIN_WIDTH, MIN_HEIGHT))
    add(stdscr, 3, 0, "ESC = beenden")
    stdscr.refresh()


def _draw_header(stdscr, item: TextItem, width: int) -> None:
    add(stdscr, 0, 0, "TIPPGEIST", curses.A_BOLD | pair(C_ACCENT))
    label = "%s  (%d Zeichen)" % (item.title, item.length)
    add(stdscr, 0, 12, label, curses.A_DIM)
    add(stdscr, 1, 0, RULE * width, curses.A_DIM)


def _draw_lanes(stdscr, session: Session, ghost: Optional[Ghost], width: int) -> None:
    bar_width = max(8, width - 36)
    total = max(1, len(session.text))

    you = session.progress
    add(stdscr, 3, 0, "DU   ", curses.A_BOLD | pair(C_YOU))
    add(stdscr, 3, 6, bar(you, bar_width), pair(C_YOU))
    add(
        stdscr,
        3,
        7 + bar_width,
        "%3d%%  %5.1f WPM  %5.1f%%" % (you * 100, session.wpm(), session.accuracy()),
    )

    if ghost is None:
        add(stdscr, 4, 0, "GEIST", curses.A_BOLD | pair(C_GHOST))
        add(
            stdscr,
            4,
            6,
            "noch keiner - dieser Lauf wird dein erster Geist.",
            curses.A_DIM,
        )
        return

    ghost_pos = ghost.position_at(session.elapsed())
    add(stdscr, 4, 0, "GEIST", curses.A_BOLD | pair(C_GHOST))
    add(stdscr, 4, 6, bar(ghost_pos / total, bar_width), pair(C_GHOST))
    add(
        stdscr,
        4,
        7 + bar_width,
        "%3d%%  %5.1f WPM  %5.1f%%"
        % (ghost_pos / total * 100, ghost.run.wpm, ghost.run.accuracy),
        curses.A_DIM,
    )


def _draw_text(
    stdscr,
    session: Session,
    ghost_pos: Optional[int],
    lines: List[Tuple[int, int]],
    top: int,
    first_row: int,
    rows: int,
) -> int:
    cursor_line = line_of(lines, min(session.pos, max(0, len(session.text) - 1)))
    if cursor_line < top:
        top = cursor_line
    elif cursor_line >= top + rows:
        top = cursor_line - rows + 1
    top = max(0, min(top, max(0, len(lines) - rows)))

    text = session.text
    for row, index in enumerate(range(top, min(len(lines), top + rows))):
        start, end = lines[index]
        for offset, i in enumerate(range(start, end)):
            char = text[i]
            if i < session.pos:
                if session.typed[i] == char:
                    attr = pair(C_CORRECT)
                else:
                    attr = pair(C_WRONG) | curses.A_REVERSE
            elif i == session.pos:
                attr = curses.A_REVERSE | curses.A_BOLD
            elif ghost_pos is not None and i == ghost_pos:
                attr = pair(C_GHOST) | curses.A_UNDERLINE | curses.A_BOLD
            else:
                attr = curses.A_DIM
            add(stdscr, first_row + row, offset, char, attr)
    return top


def race(stdscr, item: TextItem, ghost_run=None) -> Optional[Session]:
    """Ein Rennen fahren. Gibt die fertige Session zurück, oder None bei Abbruch."""
    curses.curs_set(0)
    stdscr.nodelay(True)
    ghost = Ghost(ghost_run) if ghost_run is not None else None

    session = Session(item.body)
    top = 0
    lines: List[Tuple[int, int]] = []
    last_width = -1

    while True:
        # Alle anstehenden Tasten pro Frame abholen, nicht nur eine - sonst
        # deckelt die Bildwiederholrate die Tippgeschwindigkeit.
        for key in _read_keys(stdscr):
            if key in ("\x1b", "\x03"):
                return None
            if key == "\t":
                session = Session(item.body)
                top = 0
            elif key in ("\x7f", "\b", "\x08", curses.KEY_BACKSPACE, curses.KEY_DC):
                session.backspace()
            elif isinstance(key, str) and (key.isprintable() or key == " "):
                session.press(key)
            if session.finished:
                break

        height, width = stdscr.getmaxyx()
        if height < MIN_HEIGHT or width < MIN_WIDTH:
            _draw_too_small(stdscr)
            curses.napms(60)
            continue

        text_width = width - 1
        if text_width != last_width:
            lines = wrap_indices(item.body, text_width)
            last_width = text_width

        first_row = 6
        rows = max(1, height - first_row - 2)

        stdscr.erase()
        _draw_header(stdscr, item, width)
        _draw_lanes(stdscr, session, ghost, width)
        ghost_pos = ghost.position_at(session.elapsed()) if ghost else None
        top = _draw_text(stdscr, session, ghost_pos, lines, top, first_row, rows)

        if session.started:
            hint = "%4.1fs   Tab = neu   ESC = raus" % session.elapsed()
        else:
            hint = "Einfach lostippen - die Uhr startet beim ersten Anschlag."
        add(stdscr, height - 1, 0, hint, curses.A_DIM)
        stdscr.refresh()

        if session.finished:
            curses.napms(350)
            return session
        curses.napms(16)


_NO_INPUT = object()


def _read_key(stdscr):
    try:
        return stdscr.get_wch()
    except curses.error:
        return _NO_INPUT
    except KeyboardInterrupt:
        return "\x03"


def _read_keys(stdscr, limit: int = 64) -> list:
    keys = []
    for _ in range(limit):
        key = _read_key(stdscr)
        if key is _NO_INPUT:
            break
        if key == curses.KEY_RESIZE:
            continue
        keys.append(key)
    return keys


def _verdict(session: Session, ghost: Optional[Ghost]) -> Tuple[str, int]:
    """Ergebnissatz plus Farbe."""
    if ghost is None:
        return ("Erster Lauf auf diesem Text - ab jetzt hast du einen Geist.", C_ACCENT)
    delta = ghost.run.duration - session.elapsed()
    if abs(delta) < 0.05:
        return ("Fotofinish. Exakt gleich schnell wie dein Geist.", C_ACCENT)
    if delta > 0:
        return ("Gewonnen! %.1fs schneller als dein Geist." % delta, C_CORRECT)
    return ("Dein Geist war %.1fs schneller. Nochmal?" % -delta, C_WRONG)


def result_screen(
    stdscr,
    item: TextItem,
    session: Session,
    ghost_run=None,
    is_record: bool = False,
    runs_played: int = 0,
) -> str:
    """Zeigt das Ergebnis. Gibt 'again', 'next' oder 'quit' zurück."""
    stdscr.nodelay(False)
    ghost = Ghost(ghost_run) if ghost_run is not None else None

    while True:
        height, width = stdscr.getmaxyx()
        if height < MIN_HEIGHT or width < MIN_WIDTH:
            _draw_too_small(stdscr)
            if stdscr.getch() == 27:
                return "quit"
            continue

        stdscr.erase()
        add(stdscr, 0, 0, "ERGEBNIS", curses.A_BOLD | pair(C_ACCENT))
        add(stdscr, 0, 12, item.title, curses.A_DIM)
        add(stdscr, 1, 0, RULE * width, curses.A_DIM)

        add(stdscr, 3, 2, "%-8s %6s %9s %8s" % ("", "WPM", "GENAUIG.", "ZEIT"), curses.A_DIM)
        add(
            stdscr,
            4,
            2,
            "%-8s %6.1f %8.1f%% %7.1fs"
            % ("DU", session.wpm(), session.accuracy(), session.elapsed()),
            curses.A_BOLD | pair(C_YOU),
        )
        if ghost is not None:
            add(
                stdscr,
                5,
                2,
                "%-8s %6.1f %8.1f%% %7.1fs"
                % ("GEIST", ghost.run.wpm, ghost.run.accuracy, ghost.run.duration),
                pair(C_GHOST),
            )
        else:
            add(stdscr, 5, 2, "%-8s      -         -        -" % "GEIST", curses.A_DIM)

        message, color = _verdict(session, ghost)
        add(stdscr, 7, 2, message, curses.A_BOLD | pair(color))

        detail = "%d Anschläge, davon %d daneben - roh %.1f WPM." % (
            session.keystrokes,
            session.errors,
            session.raw_wpm(),
        )
        add(stdscr, 8, 2, detail, curses.A_DIM)

        if is_record:
            add(stdscr, 9, 2, "NEUER REKORD auf diesem Text.", curses.A_BOLD | pair(C_ACCENT))
        elif runs_played:
            add(stdscr, 9, 2, "Lauf Nummer %d auf diesem Text." % runs_played, curses.A_DIM)

        add(
            stdscr,
            height - 1,
            0,
            "[Leertaste] nochmal   [n] anderer Text   [q] Schluss",
            curses.A_DIM,
        )
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord(" "), ord("\n"), curses.KEY_ENTER, 10, 13):
            return "again"
        if key in (ord("n"), ord("N")):
            return "next"
        if key in (ord("q"), ord("Q"), 27):
            return "quit"
        if key == curses.KEY_RESIZE:
            continue
