# Photo Sovereignty Pipeline

**Version**: 0.1.0  
**Status**: Foundation complete - EXIF/GPS extraction working, YOLO object detection next

Local-first ML-powered photo organization that replicates cloud service search 
capabilities (iCloud, Google Photos) while maintaining complete data sovereignty.

## Features

### v0.1.0 - Foundation Complete ✅
- EXIF metadata extraction with fallback hierarchy (EXIF → filesystem → filename)
- GPS coordinate extraction and DMS→decimal conversion
- Cross-platform configuration system (platformdirs)
- Idempotent database operations (safe re-runs, duplicate detection)
- Incremental processing (LEFT JOIN pattern for unprocessed images)
- Privacy-preserving architecture (local processing, no cloud APIs)

### In Progress 🚧
- YOLO11m object detection (80 COCO classes)
- OpenCLIP semantic embeddings (natural language search)
- EasyOCR text extraction
- Unified query interface

## Quick Start

```bash
# Install with uv (recommended)
uv pip install -e ".[dev]"

# Or with pip
pip install -e ".[dev]"

# Process photos (uses platformdirs defaults or config.yaml)
python orchestration/stage1_process_photos.py --source ~/Pictures --output ~/organized

# Extract GPS coordinates
python orchestration/stage2_extract_gps.py

# Inspect database
python dev_tools/inspect_db.py --query gps_coverage
```

## Project Structure

```
photo-sovereignty/
├── src/                    # Core library modules
│   ├── config.py          # Cross-platform configuration
│   ├── database.py        # SQLite operations
│   ├── exif_parser.py     # EXIF metadata extraction
│   ├── organize.py        # File organization & archive handling
│   └── gps_extractor.py   # GPS coordinate extraction
├── orchestration/         # Modular stage scripts (typer CLIs)
│   ├── stage1_process_photos.py
│   └── stage2_extract_gps.py
├── tests/                 # Pytest suite
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_exif_parser.py
│   └── test_gps_extractor.py
├── dev_tools/            # Development utilities
│   └── inspect_db.py     # Database inspection CLI
└── docs/                 # Documentation
    └── public/blueprint.md
```

## Configuration

Configuration is **optional**. The application uses sensible platform-specific defaults via platformdirs:

- **Linux**: `~/.local/share/photo-pipeline/`
- **macOS**: `~/Library/Application Support/photo-pipeline/`
- **Windows**: `%APPDATA%/photo-pipeline/`

To customize paths, create `config.yaml`:

```bash
cp config.example.yaml config.yaml
# Edit paths as needed
```

## Architecture

**Three-layer design:**
- **Extraction & Organization**: Pure functions (src/exif_parser.py, src/organize.py, src/gps_extractor.py)
- **Persistence**: Database operations (src/database.py)
- **Orchestration**: Typer CLI interfaces (orchestration/, dev_tools/)

**Key principles:**
- Idempotent processing (safe to re-run)
- Incremental schema evolution (database migrations)
- Clean separation of concerns
- Type hints on all public functions

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Development

```bash
# Run tests
pytest

# With coverage
pytest --cov=src --cov-report=term-missing

# Run specific test file
pytest tests/test_config.py -v

# Lint
ruff check src/ tests/
```

## Tech Stack

- **Python 3.11+**: Modern type hints, pattern matching
- **SQLite**: Local-first persistence
- **Pillow + pillow-heif**: Image processing (HEIC support)
- **platformdirs**: Cross-platform paths (XDG standards)
- **typer**: Modern CLI framework with type hints
- **pytest**: Testing framework
- **uv**: Fast Python package manager

### Upcoming (Stage 3+)
- **ultralytics**: YOLO11 object detection
- **open-clip-torch**: Semantic embeddings
- **easyocr**: Text extraction from images

## Testing

**Current Coverage**: 90.19% (58/58 tests passing)

The test suite uses pytest with comprehensive fixtures and integration tests against real image files.

```bash
# Run full test suite with coverage
pytest --cov=src --cov-report=term-missing

# Quick test run
pytest -v

# Skip integration tests (no sample images needed)
pytest -m "not integration"

# Generate HTML coverage report
pytest --cov=src --cov-report=html
```

**Note**: Integration tests require sample images in `data/sample_photos/` (gitignored for privacy). Unit tests run without sample data.

## Portfolio Context

This project demonstrates capabilities relevant to legal tech and data-sensitive applications:

- **Privacy-first ML architecture**: All processing local, no cloud dependencies
- **Incremental development methodology**: Foundation-first approach (Stages 1-2 complete before ML)
- **Clean architectural boundaries**: Extraction, persistence, orchestration layers
- **Cross-platform compatibility**: Works on Linux, macOS, Windows
- **Professional Python practices**: Type hints, docstrings, pytest, conventional commits

Built using AI-augmented development workflow (industry standard practice, 2025).

## Roadmap

- [x] **v0.1.0**: Foundation (EXIF, GPS, config system, tests)
- [ ] **v0.2.0**: Object detection (YOLO11m integration)
- [ ] **v0.3.0**: Semantic search (OpenCLIP embeddings)
- [ ] **v0.4.0**: Text extraction (EasyOCR)
- [ ] **v1.0.0**: Unified CLI + query interface

## License

MIT
