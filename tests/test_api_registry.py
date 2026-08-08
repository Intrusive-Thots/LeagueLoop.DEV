import unittest
from unittest.mock import MagicMock

from services.api.registry import GET_ROUTES, POST_ROUTES


class TestAPIRegistry(unittest.TestCase):
    def setUp(self):
        # Clear registries before each test to ensure isolation
        GET_ROUTES.clear()
        POST_ROUTES.clear()

    def tearDown(self):
        # Clear registries after each test to avoid side effects
        GET_ROUTES.clear()
        POST_ROUTES.clear()

    def test_get_routes_initialization(self):
        """Test that GET_ROUTES is a dictionary and starts empty in a clean state."""
        self.assertIsInstance(GET_ROUTES, dict)
        self.assertEqual(len(GET_ROUTES), 0)

    def test_post_routes_initialization(self):
        """Test that POST_ROUTES is a dictionary and starts empty in a clean state."""
        self.assertIsInstance(POST_ROUTES, dict)
        self.assertEqual(len(POST_ROUTES), 0)

    def test_register_get_route(self):
        """Test registering and calling a mock handler in GET_ROUTES."""
        mock_handler = MagicMock()
        mock_handler.return_value = {"status": "success"}

        # Register the route
        GET_ROUTES["/api/test_get"] = mock_handler

        # Verify it's in the registry
        self.assertIn("/api/test_get", GET_ROUTES)

        # Call the registered handler
        result = GET_ROUTES["/api/test_get"]()

        # Assertions
        mock_handler.assert_called_once()
        self.assertEqual(result, {"status": "success"})

    def test_register_post_route(self):
        """Test registering and calling a mock handler in POST_ROUTES."""
        mock_handler = MagicMock()
        mock_handler.return_value = {"status": "created"}

        # Register the route
        POST_ROUTES["/api/test_post"] = mock_handler

        # Verify it's in the registry
        self.assertIn("/api/test_post", POST_ROUTES)

        # Call the registered handler with some mock data
        mock_data = {"key": "value"}
        result = POST_ROUTES["/api/test_post"](mock_data)

        # Assertions
        mock_handler.assert_called_once_with(mock_data)
        self.assertEqual(result, {"status": "created"})

    def test_registry_mocking_with_engine(self):
        """Test storing a route handler that wraps a mock automation engine object."""
        mock_engine = MagicMock()
        mock_engine.perform_action.return_value = True

        def mock_engine_handler(*args, **kwargs):
            success = mock_engine.perform_action(*args, **kwargs)
            return {"success": success}

        # Register the route wrapper
        POST_ROUTES["/api/engine_action"] = mock_engine_handler

        # Call the registered wrapper
        result = POST_ROUTES["/api/engine_action"](action="start")

        # Assertions
        mock_engine.perform_action.assert_called_once_with(action="start")
        self.assertEqual(result, {"success": True})

if __name__ == '__main__':
    unittest.main()
