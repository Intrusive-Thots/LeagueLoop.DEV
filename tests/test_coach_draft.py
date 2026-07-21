import unittest
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])

from services.draft_service import get_draft_service
from ui.qt.pages.coach_page import CoachPage


class TestCoachDraft(unittest.TestCase):

    def setUp(self):
        self.draft_service = get_draft_service()
        self.page = CoachPage()

    def test_draft_comp_analysis(self):
        comp = self.draft_service.get_team_comp_analysis()
        self.assertIn("ad_ratio", comp)
        self.assertIn("ap_ratio", comp)
        self.assertIn("cc_score", comp)
        self.assertIn("frontline", comp)

    def test_draft_recommendations(self):
        recs = self.draft_service.get_recommendations(role="MIDDLE")
        self.assertEqual(len(recs), 5)
        self.assertEqual(recs[0]["name"], "Ahri")
        self.assertEqual(recs[0]["tier"], "S+")

    def test_coach_page_tab_change(self):
        self.page.tabs.setCurrentIndex(1)
        self.assertEqual(self.page.active_role, "JUNGLE")


if __name__ == "__main__":
    unittest.main()
