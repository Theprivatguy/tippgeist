"""Kommandozeile: Text wählen, Geist wählen, losrennen."""

from __future__ import annotations

import argparse
import curses
import locale
import random
import sys
from typing import List, Optional

from . import storage, texts, ui
from .engine import Run
from .texts import TextItem

__doc_epilog__ = """
Beispiele:
  python3 -m tippgeist                     zufälliger Text, Geist = deine Bestzeit
  python3 -m tippgeist -t kaffee -g last   fester Text, Geist = letzter Lauf
  python3 -m tippgeist -f notizen.txt      eigener Text
  python3 -m tippgeist --stats             was bisher geschah
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tippgeist",
        description="Tipptrainer, bei dem dein letzter Lauf als Geist gegen dich antritt.",
        epilog=__doc_epilog__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-t", "--text", help="ID eines eingebauten Textes")
    parser.add_argument("-f", "--file", help="eigene Textdatei statt der eingebauten")
    parser.add_argument(
        "-g",
        "--ghost",
        choices=["best", "last", "none"],
        default="best",
        help="gegen wen du fährst (Standard: best)",
    )
    parser.add_argument("-l", "--list", action="store_true", help="Texte auflisten")
    parser.add_argument("-s", "--stats", action="store_true", help="Statistik anzeigen")
    return parser


def pick_ghost(text_id: str, mode: str) -> Optional[Run]:
    if mode == "none":
        return None
    if mode == "last":
        return storage.last_for(text_id)
    return storage.best_for(text_id)


def random_text(exclude: Optional[TextItem] = None) -> TextItem:
    pool = [t for t in texts.TEXTS if exclude is None or t.id != exclude.id]
    return random.choice(pool or texts.TEXTS)


def app(stdscr, item: TextItem, ghost_mode: str, allow_switch: bool) -> List[Run]:
    ui.init_colors()
    finished: List[Run] = []

    while True:
        ghost_run = pick_ghost(item.id, ghost_mode)
        session = ui.race(stdscr, item, ghost_run)
        if session is None:
            return finished

        previous_best = storage.best_for(item.id)
        run = session.to_run(item.id, item.title)
        is_record = previous_best is None or run.wpm > previous_best.wpm
        storage.save_run(run)
        finished.append(run)

        action = ui.result_screen(
            stdscr,
            item,
            session,
            ghost_run,
            is_record=is_record,
            runs_played=len(storage.runs_for(item.id)),
        )
        if action == "quit":
            return finished
        if action == "next" and allow_switch:
            item = random_text(exclude=item)


def cmd_list() -> int:
    runs = storage.load_runs()
    print("Eingebaute Texte:\n")
    print("  %-11s %-22s %-4s %6s  %s" % ("ID", "TITEL", "SPR", "ZEICH", "BESTZEIT"))
    for item in texts.TEXTS:
        best = storage.best_for(item.id, runs)
        mark = "%.1f WPM" % best.wpm if best else "-"
        print("  %-11s %-22s %-4s %6d  %s" % (item.id, item.title, item.lang, item.length, mark))
    print("\n  Auswahl mit: python3 -m tippgeist -t <ID>")
    return 0


def cmd_stats() -> int:
    runs = storage.load_runs()
    if not runs:
        print("Noch keine Läufe. Einmal 'python3 -m tippgeist' und das ändert sich.")
        return 0

    print("%d Läufe, gespeichert in %s\n" % (len(runs), storage.history_file()))
    print("  %-22s %5s %8s %9s %9s" % ("TEXT", "LÄUFE", "BESTE", "SCHNITT", "GENAUIG."))

    seen = []
    for run in runs:
        if run.text_id not in seen:
            seen.append(run.text_id)
    for text_id in seen:
        subset = storage.runs_for(text_id, runs)
        best = max(r.wpm for r in subset)
        average = sum(r.wpm for r in subset) / len(subset)
        accuracy = sum(r.accuracy for r in subset) / len(subset)
        title = subset[-1].title[:22]
        print("  %-22s %5d %8.1f %9.1f %8.1f%%" % (title, len(subset), best, average, accuracy))

    recent = runs[-5:]
    print("\n  Die letzten %d Läufe:" % len(recent))
    for run in recent:
        print(
            "    %s  %-20s %6.1f WPM  %5.1f%%"
            % (run.started_at[:16].replace("T", " "), run.title[:20], run.wpm, run.accuracy)
        )

    overall = max(runs, key=lambda r: r.wpm)
    print("\n  Persönlicher Rekord: %.1f WPM auf \"%s\"." % (overall.wpm, overall.title))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    locale.setlocale(locale.LC_ALL, "")
    args = build_parser().parse_args(argv)

    if args.list:
        return cmd_list()
    if args.stats:
        return cmd_stats()

    allow_switch = True
    if args.file:
        try:
            item = texts.from_file(args.file)
        except (OSError, ValueError) as error:
            print("Datei konnte nicht gelesen werden: %s" % error, file=sys.stderr)
            return 1
        allow_switch = False
    elif args.text:
        found = texts.by_id(args.text)
        if found is None:
            known = ", ".join(t.id for t in texts.TEXTS)
            print("Unbekannter Text '%s'. Verfügbar: %s" % (args.text, known), file=sys.stderr)
            return 1
        item = found
    else:
        item = random_text()

    if not sys.stdout.isatty():
        print("Tippgeist braucht ein echtes Terminal.", file=sys.stderr)
        return 1

    try:
        finished = curses.wrapper(app, item, args.ghost, allow_switch)
    except KeyboardInterrupt:
        return 130
    except curses.error as error:
        print("Terminal mag nicht: %s" % error, file=sys.stderr)
        return 1

    if finished:
        best = max(finished, key=lambda r: r.wpm)
        print(
            "%d Lauf%s. Beste Runde: %.1f WPM bei %.1f%% Genauigkeit."
            % (len(finished), "" if len(finished) == 1 else "e", best.wpm, best.accuracy)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
