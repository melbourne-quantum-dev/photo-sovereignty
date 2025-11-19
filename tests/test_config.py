"""Tests for configuration loading and validation.

Tests cover:
- YAML loading from various sources
- Platform-specific default paths (platformdirs)
- Path expansion (~ to home directory)
- Config precedence (explicit > local > system > defaults)
- Missing config handling
- Malformed YAML handling

Author: Leonardo
Version: v0.1.0
"""

from pathlib import Path

import pytest
import yaml

from src.config import get_default_config_path, get_default_paths, get_path, load_config


class TestDefaultPaths:
    """Test platform-specific default path generation."""

    def test_get_default_paths_structure(self):
        """Default paths should include all required keys."""
        defaults = get_default_paths()

        assert "input_directory" in defaults
        assert "output_directory" in defaults
        assert "database" in defaults
        assert "model_cache" in defaults

    def test_default_paths_are_path_objects(self):
        """All default paths should be Path objects."""
        defaults = get_default_paths()

        for key, value in defaults.items():
            assert isinstance(value, Path), f"{key} should be a Path object"

    def test_default_config_path_exists(self):
        """Default config path should return valid Path object."""
        config_path = get_default_config_path()

        assert isinstance(config_path, Path)
        assert config_path.name == "config.yaml"


class TestConfigLoading:
    """Test configuration loading from various sources."""

    def test_load_config_with_defaults(self, temp_dir, monkeypatch):
        """Loading config without file should use platformdirs defaults."""
        # Change to temp directory so no local config.yaml exists
        monkeypatch.chdir(temp_dir)

        config = load_config()

        # Should have all required sections
        assert "paths" in config
        assert "processing" in config
        assert "models" in config

        # Paths should be set to defaults
        assert isinstance(config["paths"]["database"], Path)
        assert isinstance(config["paths"]["output_directory"], Path)

    def test_load_config_from_yaml(self, temp_dir, monkeypatch):
        """Loading from YAML file should override defaults."""
        monkeypatch.chdir(temp_dir)

        # Create test config file
        test_config = {
            "paths": {
                "database": "~/test/custom_db.db",
                "output_directory": "/custom/output",
            },
            "processing": {
                "batch_size": 64,
                "confidence_threshold": 0.7,
            },
        }

        config_file = temp_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(test_config, f)

        config = load_config()

        # Custom paths should be loaded and expanded
        assert config["paths"]["database"] == Path.home() / "test/custom_db.db"
        assert config["paths"]["output_directory"] == Path("/custom/output")

        # Custom processing settings
        assert config["processing"]["batch_size"] == 64
        assert config["processing"]["confidence_threshold"] == 0.7

    def test_load_explicit_config_path(self, temp_dir):
        """Loading with explicit path should use that config."""
        custom_config = temp_dir / "custom.yaml"

        test_data = {"paths": {"database": "/explicit/path/db.db"}}

        with open(custom_config, "w") as f:
            yaml.dump(test_data, f)

        config = load_config(str(custom_config))

        assert config["paths"]["database"] == Path("/explicit/path/db.db")

    def test_load_config_nonexistent_explicit_path(self, temp_dir):
        """Loading non-existent explicit path should raise FileNotFoundError."""
        nonexistent = temp_dir / "does_not_exist.yaml"

        with pytest.raises(FileNotFoundError):
            load_config(str(nonexistent))

    def test_tilde_expansion(self, temp_dir, monkeypatch):
        """Paths with ~ should expand to home directory."""
        monkeypatch.chdir(temp_dir)

        config_file = temp_dir / "config.yaml"
        test_config = {"paths": {"database": "~/Photos/archive.db"}}

        with open(config_file, "w") as f:
            yaml.dump(test_config, f)

        config = load_config()

        assert config["paths"]["database"] == Path.home() / "Photos/archive.db"
        assert "~" not in str(config["paths"]["database"])

    def test_malformed_yaml(self, temp_dir, monkeypatch):
        """Malformed YAML should raise YAMLError."""
        monkeypatch.chdir(temp_dir)

        config_file = temp_dir / "config.yaml"
        with open(config_file, "w") as f:
            f.write("invalid: yaml: syntax:\n  - broken")

        with pytest.raises(yaml.YAMLError):
            load_config()

    def test_partial_config_merges_with_defaults(self, temp_dir, monkeypatch):
        """Partial config should merge with defaults."""
        monkeypatch.chdir(temp_dir)

        # Config with only database path
        config_file = temp_dir / "config.yaml"
        partial_config = {"paths": {"database": "/custom/db.db"}}

        with open(config_file, "w") as f:
            yaml.dump(partial_config, f)

        config = load_config()

        # Custom database path
        assert config["paths"]["database"] == Path("/custom/db.db")

        # Other paths should use defaults
        assert "output_directory" in config["paths"]
        assert "model_cache" in config["paths"]

        # Processing defaults should be present
        assert config["processing"]["batch_size"] == 32
        assert config["processing"]["confidence_threshold"] == 0.5


class TestGetPath:
    """Test path extraction helper function."""

    def test_get_path_existing_key(self, mock_config):
        """Getting existing path key should return Path object."""
        db_path = get_path(mock_config, "database")

        assert isinstance(db_path, Path)
        assert db_path == mock_config["paths"]["database"]

    def test_get_path_nonexistent_key(self, mock_config):
        """Getting non-existent key should raise KeyError."""
        with pytest.raises(KeyError) as exc_info:
            get_path(mock_config, "nonexistent_path")

        # Error message should be helpful
        assert "nonexistent_path" in str(exc_info.value)
        assert "Available path keys" in str(exc_info.value)

    def test_get_path_all_standard_keys(self, mock_config):
        """All standard path keys should be retrievable."""
        standard_keys = [
            "input_directory",
            "output_directory",
            "database",
            "model_cache",
        ]

        for key in standard_keys:
            path = get_path(mock_config, key)
            assert isinstance(path, Path)


class TestConfigDefaults:
    """Test default values for processing and models."""

    def test_processing_defaults(self, temp_dir, monkeypatch):
        """Processing section should have sensible defaults."""
        monkeypatch.chdir(temp_dir)
        config = load_config()

        assert config["processing"]["batch_size"] == 32
        assert config["processing"]["confidence_threshold"] == 0.5

    def test_model_defaults(self, temp_dir, monkeypatch):
        """Models section should have sensible defaults."""
        monkeypatch.chdir(temp_dir)
        config = load_config()

        assert config["models"]["yolo"] == "yolo11m.pt"
        assert config["models"]["clip"] == "ViT-L-14"
        assert config["models"]["clip_pretrained"] == "laion2b_s32b_b82k"
        assert config["models"]["ocr_languages"] == ["en"]
        assert config["models"]["clip_pretrained"] == "laion2b_s32b_b82k"
        assert config["models"]["ocr_languages"] == ["en"]
