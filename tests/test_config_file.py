"""Unit tests for acepace.toml config file support (Part H4)."""
import pytest
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import acepace


def _write_toml(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class TestLoadTomlConfig:
    def test_no_config_file_returns_empty_and_does_not_touch_env(self, temp_dir):
        config_path = os.path.join(temp_dir, "acepace.toml")
        with patch('acepace.get_config_path', return_value=config_path):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("NYAA_URL", None)
                applied = acepace.load_toml_config()
        assert applied == {}
        assert "NYAA_URL" not in os.environ

    def test_toml_values_are_injected_into_environ(self, temp_dir):
        config_path = os.path.join(temp_dir, "acepace.toml")
        _write_toml(config_path, 'VERSION = "extended"\nTORRENT_HOST = "myhost"\n')
        with patch('acepace.get_config_path', return_value=config_path):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("VERSION", None)
                os.environ.pop("TORRENT_HOST", None)
                applied = acepace.load_toml_config()
                assert os.environ.get("VERSION") == "extended"
                assert os.environ.get("TORRENT_HOST") == "myhost"
        assert "VERSION" in applied
        assert "TORRENT_HOST" in applied

    def test_existing_env_var_takes_precedence_over_toml(self, temp_dir):
        """env var > acepace.toml, so an already-set env var must not be overwritten."""
        config_path = os.path.join(temp_dir, "acepace.toml")
        _write_toml(config_path, 'VERSION = "extended"\n')
        with patch('acepace.get_config_path', return_value=config_path):
            with patch.dict(os.environ, {"VERSION": "normal"}):
                acepace.load_toml_config()
                assert os.environ.get("VERSION") == "normal"

    def test_unmapped_keys_are_ignored(self, temp_dir):
        config_path = os.path.join(temp_dir, "acepace.toml")
        _write_toml(config_path, 'NOT_A_REAL_KEY = "whatever"\n')
        with patch('acepace.get_config_path', return_value=config_path):
            with patch.dict(os.environ, {}, clear=False):
                acepace.load_toml_config()
                assert "NOT_A_REAL_KEY" not in os.environ

    def test_malformed_toml_is_ignored_gracefully(self, temp_dir):
        config_path = os.path.join(temp_dir, "acepace.toml")
        _write_toml(config_path, "this is not [valid toml =")
        with patch('acepace.get_config_path', return_value=config_path):
            applied = acepace.load_toml_config()
        assert applied == {}

    def test_config_dir_permission_error_is_handled_gracefully(self):
        with patch('acepace.get_config_path', side_effect=OSError("permission denied")):
            applied = acepace.load_toml_config()
        assert applied == {}


class TestConfigPrecedenceViaArgparseDefault(object):
    """CLI > env > toml > built-in default, exercised via the --version flag's
    argparse default (os.getenv("VERSION", "normal")), the same mechanism
    every other TOML-mapped key relies on."""

    def test_toml_sets_default_when_no_env_or_cli(self, temp_dir):
        config_path = os.path.join(temp_dir, "acepace.toml")
        _write_toml(config_path, 'VERSION = "extended"\n')
        with patch('acepace.get_config_path', return_value=config_path):
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("VERSION", None)
                acepace.load_toml_config()
                assert acepace._is_extended_mode(None) is True

    def test_env_var_overrides_toml_default(self, temp_dir):
        config_path = os.path.join(temp_dir, "acepace.toml")
        _write_toml(config_path, 'VERSION = "extended"\n')
        with patch('acepace.get_config_path', return_value=config_path):
            with patch.dict(os.environ, {"VERSION": "normal"}):
                acepace.load_toml_config()
                assert acepace._is_extended_mode(None) is False
