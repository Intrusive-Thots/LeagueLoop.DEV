"""
The chain from power-on to in-game.

The switcher kept failing at a different step each time and the code had no
way to name which one. These check the description of that chain, so "it
didn't work" can become "step 4 of 9, and here is why".
"""
import unittest

from services.accounts.boot_chain import (
    GAMEFLOW_ORDER,
    ORDER,
    SPECS,
    ChainStatus,
    Stage,
    StageStatus,
    stage_for_phase,
)


def chain(met_up_to, detail=""):
    """A ChainStatus where the first `met_up_to` stages are satisfied."""
    return ChainStatus([
        StageStatus(stage, index < met_up_to, detail if index == met_up_to else "")
        for index, stage in enumerate(ORDER)
    ])


class ShapeTests(unittest.TestCase):
    def test_every_stage_is_ordered_exactly_once(self):
        self.assertEqual(len(ORDER), len(set(ORDER)))
        self.assertEqual(set(ORDER), set(Stage))

    def test_every_stage_has_an_observable_and_a_remedy(self):
        """A stage you cannot check is not a stage, it is a hope."""
        for stage in ORDER:
            spec = SPECS[stage]
            self.assertTrue(spec.title.strip(), stage)
            self.assertTrue(spec.observable.strip(), stage)
            self.assertTrue(spec.remedy.strip(), stage)

    def test_vanguard_is_marked_as_needing_a_human(self):
        """Its driver loads at boot and only at boot, so retrying is futile —
        the app must say "restart", not spin."""
        self.assertTrue(SPECS[Stage.VANGUARD].needs_human)
        self.assertIn("restart", SPECS[Stage.VANGUARD].remedy.lower())

    def test_the_session_stage_names_the_thing_that_actually_breaks(self):
        self.assertIn("age", SPECS[Stage.SESSION].observable.lower())


class BlockerTests(unittest.TestCase):
    def test_the_blocker_is_the_first_unmet_stage(self):
        status = chain(3)
        self.assertIs(status.blocker.stage, ORDER[3])

    def test_later_stages_are_not_reported_as_separate_problems(self):
        """They are unmet *because* of the blocker, not independently."""
        status = chain(2)
        self.assertEqual(status.reached, 2)
        self.assertIs(status.blocker.stage, ORDER[2])

    def test_a_complete_chain_has_no_blocker(self):
        status = chain(len(ORDER))
        self.assertIsNone(status.blocker)
        self.assertTrue(status.ready_to_play)
        self.assertEqual(status.summary(), "Ready to play.")

    def test_the_summary_numbers_the_step_and_says_why(self):
        status = chain(3, detail="the Riot Client is not running")
        summary = status.summary()
        self.assertIn("Step 4 of 9", summary)
        self.assertIn("not running", summary)

    def test_the_summary_falls_back_to_the_remedy_when_there_is_no_detail(self):
        status = chain(1)
        self.assertIn(SPECS[Stage.VANGUARD].title, status.summary())


class PhaseMappingTests(unittest.TestCase):
    def test_a_draft_is_placed_before_in_game(self):
        self.assertIs(stage_for_phase("ChampSelect"), Stage.LOBBY_TO_DRAFT)
        self.assertIs(stage_for_phase("InProgress"), Stage.IN_GAME)

    def test_every_known_phase_maps_somewhere(self):
        for phase in GAMEFLOW_ORDER:
            self.assertIsNotNone(stage_for_phase(phase), phase)

    def test_an_unknown_phase_is_not_guessed_as_in_game(self):
        """A phase from a future patch reported as in-game would have the app
        acting as though a match had started."""
        self.assertIsNone(stage_for_phase("SomeNewPhase"))
        self.assertIsNone(stage_for_phase(""))
        self.assertIsNone(stage_for_phase(None))

    def test_the_phase_order_starts_idle_and_ends_after_the_game(self):
        self.assertEqual(GAMEFLOW_ORDER[0], "None")
        self.assertIn("ChampSelect", GAMEFLOW_ORDER)
        self.assertLess(
            GAMEFLOW_ORDER.index("ChampSelect"),
            GAMEFLOW_ORDER.index("InProgress"),
        )


if __name__ == "__main__":
    unittest.main()
