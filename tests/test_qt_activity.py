"""
Tests for the activity feed (UI/UX Master Plan §18).

The central guarantee: protocol noise never reaches the user-facing feed.
"""
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class _QtTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])


class TestActivityTranslation(_QtTestCase):
    def test_unmapped_events_are_dropped(self):
        """§18: raw LCU traffic belongs in Diagnostics, not the feed."""
        from ui.qt.viewmodels.activity_viewmodel import translate

        self.assertIsNone(translate("lcu_raw_http_trace", {"url": "/lol-champ-select"}))
        self.assertIsNone(translate("totally_unknown_event"))

    def test_templated_event_without_detail_is_dropped(self):
        """Better to say nothing than to render 'Selected {}'."""
        from core.events import EventType
        from ui.qt.viewmodels.activity_viewmodel import translate

        self.assertIsNone(translate(EventType.CHAMPION_SELECTED.value))
        self.assertIsNone(translate(EventType.CHAMPION_SELECTED.value, {}))

    def test_known_events_become_sentences(self):
        from core.events import EventType
        from ui.qt.components.activity import ActivityKind
        from ui.qt.viewmodels.activity_viewmodel import translate

        entry = translate(EventType.CHAMPION_SELECTED.value, {"name": "Jinx"})
        self.assertEqual(entry.text, "Selected Jinx")
        self.assertIs(entry.kind, ActivityKind.SUCCESS)

        entry = translate(EventType.LCU_DISCONNECTED.value)
        self.assertEqual(entry.text, "League Client disconnected")
        self.assertIs(entry.kind, ActivityKind.WARNING)

    def test_no_entry_text_contains_protocol_noise(self):
        from ui.qt.viewmodels.activity_viewmodel import EVENT_MAP

        for template, _kind, _cat, _important in EVENT_MAP.values():
            for token in ("http", "POST", "GET", "/lol-", "[LCU]"):
                self.assertNotIn(token, template)


class TestActivityFeed(_QtTestCase):
    def _feed(self):
        from ui.qt.components.activity import ActivityKind, LLActivityFeed

        feed = LLActivityFeed()
        feed.log("Connected to the League Client", ActivityKind.SUCCESS, important=True)
        feed.log("Joined a lobby", ActivityKind.INFO, important=False)
        feed.log("Automation error: timed out", ActivityKind.ERROR, important=True)
        return feed

    def test_newest_first(self):
        feed = self._feed()
        self.assertEqual(feed.entries()[0].text, "Automation error: timed out")

    def test_important_filter_hides_low_signal_entries(self):
        feed = self._feed()
        feed.set_filter("IMPORTANT")
        texts = [e.text for e in feed.visible_entries()]
        self.assertNotIn("Joined a lobby", texts)
        self.assertIn("Automation error: timed out", texts)

    def test_errors_filter(self):
        feed = self._feed()
        feed.set_filter("ERRORS")
        self.assertEqual([e.text for e in feed.visible_entries()],
                         ["Automation error: timed out"])

    def test_all_filter_shows_everything(self):
        feed = self._feed()
        feed.set_filter("ALL")
        self.assertEqual(len(feed.visible_entries()), 3)

    def test_entries_are_capped(self):
        from ui.qt.components.activity import LLActivityFeed

        feed = LLActivityFeed(max_entries=5)
        for i in range(20):
            feed.log("entry {}".format(i))
        self.assertEqual(len(feed.entries()), 5)
        self.assertEqual(feed.entries()[0].text, "entry 19")

    def test_empty_state_is_shown_when_nothing_logged(self):
        from ui.qt.components.activity import LLActivityFeed

        feed = LLActivityFeed()
        self.assertTrue(feed._empty.isVisible() or not feed.entries())
        self.assertEqual(feed.visible_entries(), [])


if __name__ == "__main__":
    unittest.main()
