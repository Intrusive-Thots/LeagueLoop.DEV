import unittest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from unittest.mock import patch, MagicMock
from agent.core.agent_loop import AutonomousAgent

class TestAgentLoop(unittest.TestCase):
    @patch('agent.core.agent_loop.Path.exists')
    @patch('builtins.open', new_callable=unittest.mock.mock_open, read_data="- [ ] Task 101: Test task")
    def test_discover_next_task(self, mock_open, mock_exists):
        mock_exists.return_value = True
        agent = AutonomousAgent()
        task = agent.discover_next_task()
        self.assertEqual(task, "Task 101: Test task")
