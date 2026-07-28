import os
import tempfile
import unittest
from pathlib import Path

from tippgeist import storage, texts
from tippgeist.engine import Run


def make_run(text_id="kaffee", wpm=50.0, title="Der Kaffeeautomat"):
    return Run(
        text_id=text_id,
        title=title,
        started_at="2026-07-28T10:00:00+00:00",
        duration=30.0,
        wpm=wpm,
        raw_wpm=wpm + 2,
        accuracy=97.5,
        correct_chars=120,
        typed_chars=125,
        errors=5,
        track=[(0.0, 0), (1.5, 10), (30.0, 120)],
    )


class StorageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = os.environ.get("TIPPGEIST_HOME")
        os.environ["TIPPGEIST_HOME"] = self.tmp.name

    def tearDown(self):
        if self.previous is None:
            os.environ.pop("TIPPGEIST_HOME", None)
        else:
            os.environ["TIPPGEIST_HOME"] = self.previous
        self.tmp.cleanup()

    def test_missing_history_is_empty_not_an_error(self):
        self.assertEqual(storage.load_runs(), [])

    def test_roundtrip_keeps_the_track(self):
        storage.save_run(make_run())
        loaded = storage.load_runs()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].track, [(0.0, 0), (1.5, 10), (30.0, 120)])
        self.assertEqual(loaded[0].wpm, 50.0)

    def test_broken_history_does_not_crash(self):
        storage.history_file().parent.mkdir(parents=True, exist_ok=True)
        storage.history_file().write_text("{ das ist kein json", encoding="utf-8")
        self.assertEqual(storage.load_runs(), [])

    def test_unknown_fields_are_ignored(self):
        storage.history_file().parent.mkdir(parents=True, exist_ok=True)
        storage.history_file().write_text(
            '{"version":1,"runs":[{"text_id":"a","title":"A","started_at":"x",'
            '"duration":1,"wpm":2,"raw_wpm":3,"accuracy":4,"correct_chars":5,'
            '"typed_chars":6,"errors":0,"track":[],"zukunft":"egal"}]}',
            encoding="utf-8",
        )
        runs = storage.load_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].text_id, "a")

    def test_best_and_last_are_per_text(self):
        storage.save_run(make_run("kaffee", 40))
        storage.save_run(make_run("nacht", 90))
        storage.save_run(make_run("kaffee", 60))
        storage.save_run(make_run("kaffee", 55))
        self.assertEqual(storage.best_for("kaffee").wpm, 60)
        self.assertEqual(storage.last_for("kaffee").wpm, 55)
        self.assertEqual(storage.best_for("nacht").wpm, 90)
        self.assertIsNone(storage.best_for("gibtsnicht"))
        self.assertIsNone(storage.last_for("gibtsnicht"))

    def test_history_is_capped(self):
        storage.write_runs([make_run(wpm=float(i)) for i in range(storage.MAX_RUNS + 5)])
        storage.save_run(make_run(wpm=999.0))
        runs = storage.load_runs()
        self.assertEqual(len(runs), storage.MAX_RUNS)
        self.assertEqual(runs[-1].wpm, 999.0)

    def test_home_follows_the_environment(self):
        self.assertEqual(storage.home(), Path(self.tmp.name))


class TextsTest(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = [t.id for t in texts.TEXTS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_texts_are_single_line(self):
        for item in texts.TEXTS:
            self.assertNotIn("\n", item.body)
            self.assertEqual(item.body, item.body.strip())
            self.assertGreater(item.length, 100)

    def test_by_id(self):
        self.assertEqual(texts.by_id("kaffee").title, "Der Kaffeeautomat")
        self.assertIsNone(texts.by_id("nope"))

    def test_normalize_collapses_whitespace_and_quotes(self):
        self.assertEqual(texts.normalize("  a\n\tb   c \n"), "a b c")
        self.assertEqual(texts.normalize("„nein“ – ‘doch’…"), '„nein" - \'doch\'...')

    def test_from_file(self):
        path = Path(self.enterContext_tmp()) / "eigener.txt"
        path.write_text("Zeile eins\nZeile zwei\n", encoding="utf-8")
        item = texts.from_file(str(path))
        self.assertEqual(item.body, "Zeile eins Zeile zwei")
        self.assertEqual(item.title, "eigener.txt")
        self.assertTrue(item.id.startswith("file:"))

    def test_from_file_rejects_empty(self):
        path = Path(self.enterContext_tmp()) / "leer.txt"
        path.write_text("   \n\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            texts.from_file(str(path))

    def enterContext_tmp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return tmp.name


if __name__ == "__main__":
    unittest.main()
