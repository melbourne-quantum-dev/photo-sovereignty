# src/config.py
"""Configuration management for photo sovereignty pipeline.

This module handles loading user-specific configuration from YAML files,
enabling privacy-preserving development by separating personal paths from code.

Foundation Note:
    Config-based paths prevent hardcoding directory structures in version control.
    Critical for portfolio projects where code is public but user data is private.
    Security-conscious development from foundation, not retroactive cleanup.

Architecture:
    - config.yaml: Gitignored user-specific paths
    - config.example.yaml: Public template for other users
    - This module: Validation and loading logic

Author: Leonardo
Date: 2025-10-29
Stage: Week 2 - Privacy hardening before GitHub push
"""

import yaml
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file with path expansion and validation.
    
    Loads user-specific configuration including paths, processing parameters,
    and model settings. Expands tilde (~) in paths for user home directory.
    
    Args:
        config_path (str): Path to YAML config file. Defaults to "config.yaml"
                          in current directory. Supports ~ expansion.
    
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
        FileNotFoundError: If config file doesn't exist. Error message includes
                          instructions to copy config.example.yaml.
        yaml.YAMLError: If config file is malformed.
        KeyError: If required config keys are missing.
    
    Example:
        >>> from src.config import load_config
        >>> config = load_config()
        >>> print(config['paths']['database'])
        PosixPath('/home/user/data/photo_archive.db')
        
        >>> # Override default config location
        >>> config = load_config("custom_config.yaml")
    
    Notes:
        Foundation Era principle: Separate personal data from code structure.
        Enables sharing code publicly while protecting directory structure.
        
        Privacy consideration: config.yaml should be gitignored. Only
        config.example.yaml (with placeholder paths) should be committed.
        
        Path expansion: All paths in config['paths'] dict automatically
        expand ~ to user home directory using Path.expanduser().
    """
    # Expand ~ in config path itself
    config_file = Path(config_path).expanduser()
    
    # Check if config exists
    if not config_file.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n\n"
            f"Setup instructions:\n"
            f"1. Copy config.example.yaml to config.yaml\n"
            f"2. Edit config.yaml with your personal paths\n"
            f"3. config.yaml is gitignored (keeps your paths private)\n\n"
            f"Example:\n"
            f"  cp config.example.yaml config.yaml\n"
            f"  nano config.yaml  # Edit paths for your system"
        )
    
    # Load YAML
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise yaml.YAMLError(
            f"Error parsing config file {config_path}:\n{e}\n\n"
            f"Check YAML syntax - common issues:\n"
            f"- Incorrect indentation (use 2 spaces)\n"
            f"- Missing colons after keys\n"
            f"- Unquoted special characters"
        )
    
    # Validate required keys
    required_keys = ['paths', 'processing', 'models']
    missing_keys = [key for key in required_keys if key not in config]
    
    if missing_keys:
        raise KeyError(
            f"Missing required config sections: {missing_keys}\n\n"
            f"Required structure:\n"
            f"  paths:\n"
            f"    input_directory: ~/Pictures/photos\n"
            f"    output_directory: ~/Pictures/organized\n"
            f"    database: ~/Pictures/photo_archive.db\n"
            f"    model_cache: ~/.cache/photo-sovereignty/models\n"
            f"  processing:\n"
            f"    batch_size: 32\n"
            f"    confidence_threshold: 0.5\n"
            f"  models:\n"
            f"    yolo: yolov8m.pt\n"
            f"    clip: ViT-L-14"
        )
    
    # Expand ~ in all path values
    if 'paths' in config:
        for key, value in config['paths'].items():
            if value:  # Handle None values gracefully
                config['paths'][key] = Path(value).expanduser()
    
    return config


def get_path(config: Dict[str, Any], path_key: str) -> Path:
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
        PosixPath('/home/user/data/photo_archive.db')
    
    Notes:
        Alternative to accessing config['paths']['database'] directly.
        Provides clearer error messages if path key is missing.
    """
    if path_key not in config.get('paths', {}):
        available_keys = list(config.get('paths', {}).keys())
        raise KeyError(
            f"Path key '{path_key}' not found in config.\n"
            f"Available path keys: {available_keys}\n\n"
            f"Check your config.yaml has:\n"
            f"  paths:\n"
            f"    {path_key}: /your/path/here"
        )
    
    return config['paths'][path_key]


# Module test
if __name__ == "__main__":
    """Test config loading with clear error messages."""
    
    print("Testing config.py module...\n")
    
    try:
        # Attempt to load config
        config = load_config()
        
        print("✅ Config loaded successfully")
        print(f"\nPaths:")
        for key, value in config['paths'].items():
            exists = "✅" if value.exists() else "⚠️  (doesn't exist yet)"
            print(f"  {key}: {value} {exists}")
        
        print(f"\nProcessing settings:")
        print(f"  batch_size: {config['processing']['batch_size']}")
        print(f"  confidence_threshold: {config['processing']['confidence_threshold']}")
        
        print(f"\nModels:")
        for key, value in config['models'].items():
            print(f"  {key}: {value}")
        
        # Test path extraction helper
        db_path = get_path(config, 'database')
        print(f"\nPath extraction test:")
        print(f"  Database path: {db_path}")
        
    except FileNotFoundError as e:
        print(f"❌ {e}")
        print("\nThis is expected if config.yaml doesn't exist yet.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
