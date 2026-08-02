import pytest
import re
from core import constants
from core.version import __version__

class TestConstantsAndVersion:
    def test_version_format(self):
        # Format: 1-{month}-{days_left_in_year}-{HHMM}
        pattern = r"^1-\d{2}-\d{1,3}-\d{4}$"
        assert re.match(pattern, __version__) is not None

    def test_queue_constants(self):
        assert constants.QUEUE_DRAFT == 400
        assert constants.QUEUE_RANKED_SOLO == 420
        assert constants.QUEUE_RANKED_FLEX == 440
        assert constants.QUEUE_ARAM == 450
        assert constants.QUEUE_ARENA == 1700
        assert constants.QUEUE_ARENA_3V6 == 1710

    def test_ui_and_timing_constants(self):
        assert constants.SIDEBAR_WIDTH > 0
        assert constants.SIDEBAR_HEIGHT > 0
        assert constants.DOCKING_POLL_INTERVAL > 0
        assert constants.LCU_REQUEST_TIMEOUT > 0
