"""Pytest fixtures and configuration for photo sovereignty pipeline tests.

This module provides shared test fixtures for:
- Temporary databases (auto-cleanup)
- Sample images (HEIC, JPEG, PNG from data/sample_photos/)
- Mock configurations
- Test directory structures

Fixtures are automatically discovered by pytest and available to all test files.

Author: Leonardo
Version: v0.1.0
"""

import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator

import pytest

# Import modules to test
from src.config import load_config
from src.database import create_database


@pytest.fixture
def temp_db() -> Generator[Path, None, None]:
    """Create a temporary SQLite database for testing.

    Yields:
        Path: Path to temporary database file

    Cleanup:
        Automatically removes database after test completes

    Example:
        def test_database_operations(temp_db):
            conn = sqlite3.connect(temp_db)
            # ... perform tests ...
    """
    # Create temp database file
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Path(db_file.name)
    db_file.close()

    yield db_path

    # Cleanup after test
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def temp_db_with_schema(temp_db: Path) -> Generator[sqlite3.Connection, None, None]:
    """Create a temporary database with schema initialized.

    Yields:
        sqlite3.Connection: Connected database with images/locations tables

    Cleanup:
        Automatically closes connection and removes database

    Example:
        def test_insert_image(temp_db_with_schema):
            conn = temp_db_with_schema
            # Tables already exist, ready to insert data
    """
    conn = create_database(temp_db)
    yield conn
    conn.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for file operations.

    Yields:
        Path: Path to temporary directory

    Cleanup:
        Automatically removes directory and all contents

    Example:
        def test_file_organization(temp_dir):
            output_dir = temp_dir / "organized"
            # ... test file operations ...
    """
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path

    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def sample_photos_dir() -> Path:
    """Get path to sample photos directory.

    Returns:
        Path: Path to data/sample_photos/ directory

    Raises:
        FileNotFoundError: If sample photos directory doesn't exist

    Note:
        Sample photos should include:
        - HEIC files with EXIF data
        - JPEG files
        - PNG files (likely no EXIF)
        - Mix of GPS-enabled and non-GPS images
    """
    samples_dir = Path("data/sample_photos")

    if not samples_dir.exists():
        pytest.skip(f"Sample photos directory not found: {samples_dir}")

    return samples_dir


@pytest.fixture
def sample_heic_with_gps(sample_photos_dir: Path) -> Path:
    """Get a sample HEIC file known to have GPS data.

    Returns:
        Path: Path to HEIC file with GPS coordinates

    Note:
        Modify this if your sample photos have different filenames
    """
    heic_files = list(sample_photos_dir.glob("*.HEIC")) + list(
        sample_photos_dir.glob("*.heic")
    )

    if not heic_files:
        pytest.skip("No HEIC files found in sample photos")

    # Return first HEIC file (adjust if specific file needed)
    return heic_files[0]


@pytest.fixture
def sample_jpeg(sample_photos_dir: Path) -> Path:
    """Get a sample JPEG file.

    Returns:
        Path: Path to JPEG file
    """
    jpeg_files = (
        list(sample_photos_dir.glob("*.JPEG"))
        + list(sample_photos_dir.glob("*.jpeg"))
        + list(sample_photos_dir.glob("*.JPG"))
        + list(sample_photos_dir.glob("*.jpg"))
    )

    if not jpeg_files:
        pytest.skip("No JPEG files found in sample photos")

    return jpeg_files[0]


@pytest.fixture
def sample_png(sample_photos_dir: Path) -> Path:
    """Get a sample PNG file.

    Returns:
        Path: Path to PNG file
    """
    png_files = list(sample_photos_dir.glob("*.PNG")) + list(
        sample_photos_dir.glob("*.png")
    )

    if not png_files:
        pytest.skip("No PNG files found in sample photos")

    return png_files[0]


@pytest.fixture
def mock_config(temp_dir: Path, temp_db: Path) -> Dict[str, Any]:
    """Create a mock configuration for testing.

    Args:
        temp_dir: Temporary directory fixture
        temp_db: Temporary database fixture

    Returns:
        Dict: Configuration dictionary with temporary paths

    Example:
        def test_with_config(mock_config):
            db_path = mock_config['paths']['database']
            # ... use config in tests ...
    """
    return {
        "paths": {
            "input_directory": temp_dir / "input",
            "output_directory": temp_dir / "output",
            "database": temp_db,
            "model_cache": temp_dir / "models",
        },
        "processing": {
            "batch_size": 32,
            "confidence_threshold": 0.5,
        },
        "models": {
            "yolo": "yolo11m.pt",
            "clip": "ViT-L-14",
            "clip_pretrained": "laion2b_s32b_b82k",
            "ocr_languages": ["en"],
        },
    }


@pytest.fixture
def sample_image_data() -> Dict[str, Any]:
    """Create sample image metadata for database testing.

    Returns:
        Dict: Image metadata dictionary matching database schema

    Example:
        def test_insert_image(temp_db_with_schema, sample_image_data):
            conn = temp_db_with_schema
            image_id = insert_image(conn, sample_image_data)
            assert image_id > 0
    """
    return {
        "original_path": "/test/photos/IMG_1234.HEIC",
        "organized_path": "/test/organized/2025/2025-05-22_143022.heic",
        "filename": "2025-05-22_143022.heic",
        "date_taken": datetime(2025, 5, 22, 14, 30, 22),  # datetime object, not string
        "date_source": "exif",
        "camera_make": "Apple",
        "camera_model": "iPhone 14 Pro",
    }


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Get project root directory.

    Returns:
        Path: Project root path

    Note:
        Scope="session" means this is created once per test session
    """
    # conftest.py is in /tests, so parent is project root
    return Path(__file__).parent.parent


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests requiring sample data"
    )
