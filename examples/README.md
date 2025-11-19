# Examples: Modular Processing Scripts

This directory contains standalone scripts demonstrating each stage of the photo sovereignty pipeline. These scripts were used during incremental development (Weeks 1-2) and serve as:

1. **Working examples** of how each pipeline component operates independently
2. **Testing utilities** for validating individual stages during development
3. **Portfolio demonstrations** of modular, foundation-first development approach

## Scripts

### `stage1_process_photos.py` - EXIF Extraction & Organization

Demonstrates Stage 1 of the pipeline:
- Extract EXIF metadata (date, camera, etc.)
- Generate standardized filenames (`YYYY-MM-DD_HHMMSS.ext`)
- Organize photos into year-based directory structure
- Store metadata in SQLite database with idempotent processing

**Usage:**
```bash
# Use config.yaml paths (recommended)
python examples/stage1_process_photos.py

# Override specific paths
python examples/stage1_process_photos.py --source ~/Downloads/photos --db test.db

# Use custom config file
python examples/stage1_process_photos.py --config production.yaml
```

**Key Features:**
- Idempotent: Safe to re-run multiple times
- Duplicate detection via database
- Handles HEIC, JPEG, PNG formats
- Fallback date extraction hierarchy (EXIF → filesystem → filename)

---

### `stage2_extract_gps.py` - GPS Coordinate Extraction

Demonstrates Stage 2 of the pipeline:
- Extract GPS coordinates from EXIF data
- Convert DMS (degrees/minutes/seconds) to decimal format
- Store location data in database with image linkage
- Incremental processing (only images without existing GPS)

**Usage:**
```bash
# Use config.yaml database path (recommended)
python examples/stage2_extract_gps.py

# Override database path
python examples/stage2_extract_gps.py --db ~/test/photo_archive.db

# Use custom config file
python examples/stage2_extract_gps.py --config production.yaml
```

**Key Features:**
- LEFT JOIN query pattern for incremental processing
- Graceful handling of images without GPS data
- Altitude extraction (when available)
- Statistics reporting (coverage percentage, etc.)

---

## Architecture Notes

### Modular Development Approach

These scripts demonstrate **separation of concerns**:

- **Extraction logic** (`src/exif_parser.py`, `src/gps_extractor.py`): Pure functions, no side effects
- **Persistence logic** (`src/database.py`): Database operations isolated
- **Orchestration** (these scripts): CLI interface + pipeline coordination

This architecture enables:
- Independent unit testing of each component
- Reusing extraction functions in other contexts
- Swapping database backends without touching extraction code
- Clear boundaries between data processing and I/O

### Future Refactoring (Week 6-7)

These scripts will be unified into a single CLI interface:

```bash
# Unified CLI (future)
python main.py process --stage exif --source ~/Photos
python main.py process --stage gps --db photo_archive.db
python main.py process --stage all  # Run full pipeline
```

The underlying modules (`src/*.py`) remain unchanged. Only the CLI interface is unified. This demonstrates:
- Clean architectural boundaries
- Modular → unified development workflow
- Foundation-first incremental development

---

## Dependencies

See `pyproject.toml` for full dependency list. Core requirements:
- `Pillow>=10.0.0` - Image handling
- `pillow-heif>=0.13.0` - HEIC format support
- `pyyaml>=6.0` - Configuration loading
- `platformdirs>=4.0.0` - Cross-platform paths

Install with:
```bash
uv pip install -e ".[dev]"
```

---

## Testing

For automated testing of these components, see the pytest suite in `/tests`:
- `test_exif_parser.py` - EXIF extraction logic
- `test_gps_extractor.py` - GPS coordinate conversion
- `test_database.py` - Idempotent operations, duplicate handling

Run tests:
```bash
pytest --cov=src --cov-report=term-missing
```

---

## Privacy Note

These scripts load paths from `config.yaml` (gitignored). Example configuration is in `config.example.yaml`. The application now uses platformdirs for cross-platform defaults, so `config.yaml` is optional unless you need custom paths.

**Default paths (no config needed):**
- Linux: `~/.local/share/photo-pipeline/`
- macOS: `~/Library/Application Support/photo-pipeline/`
- Windows: `%APPDATA%/photo-pipeline/`
