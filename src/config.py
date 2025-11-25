# src/config.py
"""Configuration management for photo sovereignty pipeline.

This module handles loading user-specific configuration from YAML files,
using platformdirs for cross-platform compatibility. Configuration is optional;
sensible defaults are provided for quick-start usage.

Design Principles:
    - Privacy-first: config.yaml is gitignored, keeping personal paths private
    - Cross-platform: Uses platformdirs for XDG/macOS/Windows compatibility
    - Optional configuration: Works out-of-the-box with sensible defaults
    - Flexible: Supports partial configs that merge with defaults

Architecture:
    - config.yaml: User-specific paths (gitignored)
    - config.example.yaml: Public template for customization
    - platformdirs: Platform-appropriate default directories
    - Validation: Clear error messages for configuration issues
"""

from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_cache_dir, user_config_dir, user_data_dir


def get_default_config_path() -> Path:
    """Get platform-appropriate config file location.

    Returns default config file path using platformdirs:
    - Linux: ~/.config/photo-pipeline/config.yaml
    - macOS: ~/Library/Application Support/photo-pipeline/config.yaml
    - Windows: %APPDATA%/photo-pipeline/config.yaml

    Returns:
        Path: Platform-specific config file location.

    Example:
        >>> get_default_config_path()
        PosixPath('/home/user/.config/photo-pipeline/config.yaml')
    """
    config_dir = Path(user_config_dir("photo-pipeline", appauthor=False))
    return config_dir / "config.yaml"


def get_default_paths() -> dict[str, Path]:
    """Get platform-appropriate default paths for data storage.

    Provides sensible defaults using platformdirs when config.yaml doesn't exist
    or lacks specific path entries. Follows XDG standards on Linux, Apple's
    conventions on macOS, and Windows AppData patterns.

    Returns:
        Dict[str, Path]: Dictionary with keys:
            - input_directory: User's Pictures directory
            - output_directory: App data dir for organized photos
            - database: App data dir for SQLite database
            - model_cache: App cache dir for ML models

    Example:
        >>> defaults = get_default_paths()
        >>> defaults['database']
        PosixPath('/home/user/.local/share/photo-pipeline/photo_archive.db')

    Notes:
        These are fallback defaults. Users should still create config.yaml
        for production use to specify exact paths.
    """
    data_dir = Path(user_data_dir("photo-pipeline", appauthor=False))
    cache_dir = Path(user_cache_dir("photo-pipeline", appauthor=False))

    # Use ~/Pictures as default input (fallback to home if Pictures doesn't exist)
    pictures_dir = Path.home() / "Pictures"

    return {
        "input_directory": pictures_dir if pictures_dir.exists() else Path.home(),
        "output_directory": data_dir / "organized",
        "database": data_dir / "photo_archive.db",
        "model_cache": cache_dir / "models",
    }


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load configuration from YAML file with path expansion and validation.

    Loads user-specific configuration including paths, processing parameters,
    and model settings. Uses platformdirs for cross-platform defaults.

    Args:
        config_path (Optional[str]): Path to YAML config file. If None, attempts:
            1. ./config.yaml (current directory)
            2. Platform-specific config directory via platformdirs
            If not found, uses platform-appropriate defaults.

    Returns:
        Dict[str, Any]: Configuration dictionary with structure:
            {
                'paths': {
                    'input_directory': Path,
                    'output_directory': Path,
                    'database': Path,
                    'model_cache': Path
                },
                'processing': {
                    'batch_size': int,
                    'confidence_threshold': float
                },
                'models': {
                    'yolo': str,
                    'clip': str,
                    'clip_pretrained': str
                }
            }

    Raises:
        yaml.YAMLError: If config file is malformed.

    Example:
        >>> from src.config import load_config
        >>> config = load_config()  # Auto-detects config location
        >>> print(config['paths']['database'])
        PosixPath('/home/user/.local/share/photo-pipeline/photo_archive.db')

        >>> # Override with specific config
        >>> config = load_config("custom_config.yaml")

    Notes:
        v0.1.0 change: Now uses platformdirs for cross-platform support.
        Falls back to sensible defaults if no config exists, making the
        tool more portable and easier to quick-start for testing.

        Config precedence:
        1. Explicit config_path argument
        2. ./config.yaml (current directory)
        3. ~/.config/photo-pipeline/config.yaml (Linux/platformdirs)
        4. Built-in defaults (no file required)
    """
    # Determine which config file to use
    if config_path:
        # Explicit path provided
        config_file = Path(config_path).expanduser()
        if not config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_path}\n"
                f"Specified config path does not exist."
            )
    else:
        # Try current directory first, then platformdirs location
        local_config = Path("config.yaml")
        system_config = get_default_config_path()

        if local_config.exists():
            config_file = local_config
        elif system_config.exists():
            config_file = system_config
        else:
            # No config found - use defaults
            config_file = None

    # If config exists, load it
    if config_file:
        try:
            with open(config_file) as f:
                config = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise yaml.YAMLError(
                f"Error parsing config file {config_file}:\n{e}\n\n"
                f"Check YAML syntax - common issues:\n"
                f"- Incorrect indentation (use 2 spaces)\n"
                f"- Missing colons after keys\n"
                f"- Unquoted special characters"
            ) from e
    else:
        # No config file - start with empty config, will use defaults
        config = {}

    # Ensure paths section exists (merge with defaults)
    if "paths" not in config:
        config["paths"] = {}

    # Merge with defaults (user config takes precedence)
    defaults = get_default_paths()
    for key, default_value in defaults.items():
        if key not in config["paths"] or config["paths"][key] is None:
            config["paths"][key] = default_value
        else:
            # Expand user-provided paths
            config["paths"][key] = Path(config["paths"][key]).expanduser()

    # Provide processing defaults if not specified
    if "processing" not in config:
        config["processing"] = {}

    config["processing"].setdefault("batch_size", 32)
    config["processing"].setdefault("confidence_threshold", 0.5)
    config["processing"].setdefault("preserve_filenames", "descriptive_only")
    config["processing"].setdefault("recursive", False)

    # Provide model defaults if not specified
    if "models" not in config:
        config["models"] = {}

    config["models"].setdefault("yolo", "yolo11m.pt")
    config["models"].setdefault("clip", "ViT-L-14")
    config["models"].setdefault("clip_pretrained", "laion2b_s32b_b82k")
    config["models"].setdefault("ocr_languages", ["en"])

    return config


def get_path(config: dict[str, Any], path_key: str) -> Path:
    """Get a specific path from config with validation.

    Helper function to extract and validate individual paths from config dict.
    Useful when only a single path is needed rather than full config.

    Args:
        config (Dict[str, Any]): Configuration dictionary from load_config().
        path_key (str): Key name in config['paths'] dict.
                       Examples: 'database', 'input_directory', 'output_directory'

    Returns:
        Path: Expanded Path object for requested key.

    Raises:
        KeyError: If path_key doesn't exist in config['paths'].

    Example:
        >>> config = load_config()
        >>> db_path = get_path(config, 'database')
        >>> print(db_path)
        PosixPath('/home/user/.local/share/photo-pipeline/photo_archive.db')

    Notes:
        Alternative to accessing config['paths']['database'] directly.
        Provides clearer error messages if path key is missing.
    """
    if path_key not in config.get("paths", {}):
        available_keys = list(config.get("paths", {}).keys())
        raise KeyError(
            f"Path key '{path_key}' not found in config.\n"
            f"Available path keys: {available_keys}\n\n"
            f"Check your config.yaml has:\n"
            f"  paths:\n"
            f"    {path_key}: /your/path/here"
        )

    return config["paths"][path_key]
