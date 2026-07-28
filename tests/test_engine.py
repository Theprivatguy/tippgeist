import unittest

from tippgeist.engine import Ghost, Session, line_of, wrap_indices


class FakeClock:
    """Uhr, die nur vorgeht, wenn man sie schiebt."""

    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def type_text(session, text, clock=None, step=0.1):
    for char in text:
        if clock is not None:
            clock.advance(step)
        session.press(char)


class SessionTest(unittest.TestCase):
    def test_clock_starts_with_first_keystroke(self):
        clock = FakeClock()
        session = Session("abc", clock=clock)
        clock.advance(5.0)
        self.assertFalse(session.started)
        self.assertEqual(session.elapsed(), 0.0)
        session.press("a")
        self.assertTrue(session.started)
        self.assertEqual(session.elapsed(), 0.0)

    def test_finishes_at_last_character(self):
        clock = FakeClock()
        session = Session("abc", clock=clock)
        type_text(session, "abc", clock)
        self.assertTrue(session.finished)
        self.assertAlmostEqual(session.elapsed(), 0.2, places=6)

    def test_wrong_character_advances_and_counts_as_error(self):
        session = Session("abc")
        session.press("x")
        self.assertEqual(session.pos, 1)
        self.assertEqual(session.errors, 1)
        self.assertEqual(session.correct_chars(), 0)

    def test_backspace_restores_position_but_not_accuracy(self):
        session = Session("abc")
        session.press("x")
        session.backspace()
        session.press("a")
        self.assertEqual(session.pos, 1)
        self.assertEqual(session.correct_chars(), 1)
        self.assertEqual(session.keystrokes, 2)
        self.assertAlmostEqual(session.accuracy(), 50.0)

    def test_backspace_on_empty_session_is_harmless(self):
        session = Session("abc")
        session.backspace()
        self.assertEqual(session.pos, 0)
        self.assertFalse(session.started)

    def test_press_after_finish_is_ignored(self):
        session = Session("ab")
        type_text(session, "ab")
        session.press("c")
        self.assertEqual(session.pos, 2)
        self.assertEqual(session.keystrokes, 2)

    def test_wpm_uses_five_characters_per_word(self):
        clock = FakeClock()
        # Die Uhr startet beim ersten Anschlag, nicht davor: 61 Zeichen im
        # Sekundentakt sind 60 Sekunden, nicht 61.
        text = "a" * 61
        session = Session(text, clock=clock)
        type_text(session, text, clock, step=1.0)
        self.assertAlmostEqual(session.elapsed(), 60.0, places=6)
        self.assertAlmostEqual(session.wpm(), 61 / 5.0, places=6)

    def test_first_keystroke_is_free(self):
        clock = FakeClock()
        session = Session("abc", clock=clock)
        clock.advance(3.0)
        session.press("a")
        self.assertEqual(session.elapsed(), 0.0)
        self.assertEqual(session.wpm(), 0.0)

    def test_raw_wpm_counts_mistakes_too(self):
        clock = FakeClock()
        session = Session("abcd", clock=clock)
        type_text(session, "abXd", clock, step=1.0)
        self.assertGreater(session.raw_wpm(), session.wpm())

    def test_accuracy_without_keystrokes_is_full(self):
        self.assertEqual(Session("abc").accuracy(), 100.0)

    def test_run_snapshot_carries_the_track(self):
        clock = FakeClock()
        session = Session("hallo", clock=clock)
        type_text(session, "hallo", clock)
        run = session.to_run("t", "Titel")
        self.assertEqual(run.text_id, "t")
        self.assertEqual(run.correct_chars, 5)
        self.assertEqual(run.track[-1][1], 5)


class GhostTest(unittest.TestCase):
    def make_ghost(self):
        clock = FakeClock()
        session = Session("abcde", clock=clock)
        type_text(session, "abcde", clock, step=1.0)
        return Ghost(session.to_run("t", "Titel"))

    def test_position_before_start_is_zero(self):
        self.assertEqual(self.make_ghost().position_at(-3.0), 0)

    def test_position_is_held_between_keystrokes(self):
        # Zeichen 1 fällt auf Sekunde 0, danach eines pro Sekunde.
        ghost = self.make_ghost()
        self.assertEqual(ghost.position_at(0.0), 1)
        self.assertEqual(ghost.position_at(2.0), 3)
        self.assertEqual(ghost.position_at(2.9), 3)
        self.assertEqual(ghost.position_at(3.0), 4)

    def test_position_after_the_end_stays_at_the_finish(self):
        ghost = self.make_ghost()
        self.assertEqual(ghost.position_at(9999.0), 5)
        self.assertEqual(ghost.final_position, 5)

    def test_time_at_position(self):
        ghost = self.make_ghost()
        self.assertAlmostEqual(ghost.time_at(4), 3.0, places=3)
        self.assertIsNone(ghost.time_at(99))

    def test_ghost_survives_a_run_without_keystrokes(self):
        from tippgeist.engine import Run

        ghost = Ghost(Run("t", "T", "now", 0.0, 0.0, 0.0, 100.0, 0, 0, 0, []))
        self.assertEqual(ghost.position_at(1.0), 0)


class WrapTest(unittest.TestCase):
    def test_every_index_appears_exactly_once(self):
        text = "Der Kaffeeautomat im dritten Stock hat ein Eigenleben entwickelt."
        for width in range(10, 40):
            lines = wrap_indices(text, width)
            covered = [i for start, end in lines for i in range(start, end)]
            self.assertEqual(covered, list(range(len(text))), "Breite %d" % width)

    def test_lines_stay_within_width(self):
        text = "ein zwei drei vier fuenf sechs sieben acht neun zehn"
        for width in range(12, 30):
            for start, end in wrap_indices(text, width):
                self.assertLessEqual(end - start, width)

    def test_word_longer_than_the_line_is_cut(self):
        lines = wrap_indices("x" * 25, 10)
        self.assertEqual(lines, [(0, 10), (10, 20), (20, 25)])

    def test_empty_text(self):
        self.assertEqual(wrap_indices("", 20), [])

    def test_line_of_finds_the_row(self):
        lines = wrap_indices("ein zwei drei vier", 9)
        self.assertEqual(line_of(lines, 0), 0)
        self.assertEqual(line_of(lines, len("ein zwei ")), 1)
        # Position hinter dem Text landet auf der letzten Zeile, statt zu werfen.
        self.assertEqual(line_of(lines, 999), len(lines) - 1)


if __name__ == "__main__":
    unittest.main()
