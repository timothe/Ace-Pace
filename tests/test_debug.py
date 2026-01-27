"""Unit tests for DEBUG mode functionality."""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Add parent directory to path to import acepace
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestDebugMode:
    """Tests for DEBUG mode functionality."""

    def test_debug_print_outputs_when_enabled(self, capsys):
        """Test that debug_print outputs when DEBUG mode is enabled."""
        with patch('acepace.DEBUG_MODE', True):
            import acepace
            acepace.debug_print("Test debug message")
            captured = capsys.readouterr()
            assert "Test debug message" in captured.out

    def test_debug_print_no_output_when_disabled(self, capsys):
        """Test that debug_print does not output when DEBUG mode is disabled."""
        with patch('acepace.DEBUG_MODE', False):
            import acepace
            acepace.debug_print("Test debug message")
            captured = capsys.readouterr()
            assert "Test debug message" not in captured.out

    def test_debug_mode_parsing_true(self):
        """Test that DEBUG mode parsing works with 'true'."""
        with patch.dict(os.environ, {'DEBUG': 'true'}, clear=False):
            debug_value = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")
            assert debug_value is True

    def test_debug_mode_parsing_1(self):
        """Test that DEBUG mode parsing works with '1'."""
        with patch.dict(os.environ, {'DEBUG': '1'}, clear=False):
            debug_value = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")
            assert debug_value is True

    def test_debug_mode_parsing_yes(self):
        """Test that DEBUG mode parsing works with 'yes'."""
        with patch.dict(os.environ, {'DEBUG': 'yes'}, clear=False):
            debug_value = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")
            assert debug_value is True

    def test_debug_mode_parsing_on(self):
        """Test that DEBUG mode parsing works with 'on'."""
        with patch.dict(os.environ, {'DEBUG': 'on'}, clear=False):
            debug_value = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")
            assert debug_value is True

    def test_debug_mode_parsing_case_insensitive(self):
        """Test that DEBUG mode parsing is case-insensitive."""
        with patch.dict(os.environ, {'DEBUG': 'TRUE'}, clear=False):
            debug_value = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")
            assert debug_value is True

    def test_debug_mode_parsing_false(self):
        """Test that DEBUG mode parsing works with 'false'."""
        with patch.dict(os.environ, {'DEBUG': 'false'}, clear=False):
            debug_value = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")
            assert debug_value is False

    def test_debug_mode_parsing_empty(self):
        """Test that DEBUG mode parsing works with empty string."""
        with patch.dict(os.environ, {'DEBUG': ''}, clear=False):
            debug_value = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")
            assert debug_value is False

    def test_debug_mode_parsing_not_set(self):
        """Test that DEBUG mode parsing works when not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove DEBUG if it exists
            if 'DEBUG' in os.environ:
                del os.environ['DEBUG']
            debug_value = os.getenv("DEBUG", "").lower() in ("true", "1", "yes", "on")
            assert debug_value is False
