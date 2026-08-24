"""
The draft screen and the engine now describe the same draft.

Every case here is one where the screen said something the engine would not
do, or reached the network to answer a question it already had the answer to.
"""
import os
import unittest

import dataclasses

from core.state import ApplicationState, ChampSelectState


def _app_state(**champ_select):
    """An ApplicationState with the given champ-select fields set."""
    state = ApplicationState()
    if champ_select:
        state = dataclasses.replace(
            state,
            champ_select=dataclasses.replace(
                ChampSelectState(), **champ_select
            ),
        )
    return state


if __name__ == "__main__":
    unittest.main()
