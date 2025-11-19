# tests/__init__.py
"""Test suite for photo sovereignty pipeline.

Test Structure:
    - test_config.py: Configuration loading and validation
    - test_database.py: Database operations (idempotency, duplicates)
    - test_exif_parser.py: EXIF extraction and file organization
    - test_gps_extractor.py: GPS coordinate extraction and conversion

Fixtures defined in conftest.py provide:
    - Sample images (HEIC, JPEG, PNG)
    - Temporary databases
    - Mock configurations
    - Test data cleanup

Coverage target: >90% for src/ modules

Run tests:
    pytest                                    # Run all tests
    pytest tests/test_exif_parser.py          # Run specific test file
    pytest --cov=src --cov-report=term-missing  # With coverage
    pytest -v                                 # Verbose output
    pytest -k "gps"                           # Run tests matching pattern

Author: Leonardo
Version: v0.1.0
"""
