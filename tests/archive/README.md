# Archived Development Scripts

This directory contains legacy development and exploration scripts from the early stages of the project (Weeks 1-2). These scripts served their purpose during incremental development but have been superseded by:

1. **Proper pytest suite** (`/tests/test_*.py`) - Automated testing with fixtures
2. **Database inspection tool** (`/dev_tools/inspect_db.py`) - Consolidated query functionality

## Archived Scripts

### `query_database.py`
Early database exploration script for EXIF metadata verification.

**Superseded by:**
- `/dev_tools/inspect_db.py` (production tool)
- `/tests/test_database.py` (automated tests)

### `query_gps.py`
GPS data verification and statistics script.

**Superseded by:**
- `/dev_tools/inspect_db.py --query gps_coverage` (production tool)
- `/tests/test_gps_extractor.py` (automated tests)

### `test_detailed_exif_inspection.py`
One-off EXIF tag exploration script for understanding datetime tag structure.

**Purpose served:**
- Informed implementation of date extraction hierarchy in `src/exif_parser.py`
- No longer needed; functionality covered by pytest suite

### `test_gps_manual.py`
Manual GPS insertion test for database operations validation (5-image subset).

**Superseded by:**
- `/tests/test_database.py::test_insert_location` (automated test)
- Full extraction via `examples/stage2_extract_gps.py`

## Why Archive (Not Delete)?

These scripts are preserved to demonstrate:

1. **Iterative development process** - How features were explored before implementation
2. **Evolution of testing approach** - From manual scripts to automated pytest
3. **Foundation-first methodology** - Building understanding before building features

They're kept in git history as part of the project's development narrative, but excluded from the main test suite to avoid confusion.

## v0.1.0 Cleanup

As of v0.1.0, the project transitioned from:
- **Ad-hoc manual testing** → **Automated pytest suite**
- **Scattered query scripts** → **Unified dev_tools/inspect_db.py**
- **Exploration scripts** → **Production-ready examples/**

This archive marks the completion of the Foundation Era (Stages 1-2) and readiness for Stage 3 (YOLO object detection).
