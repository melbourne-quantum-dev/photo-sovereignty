# Claude Context: Photo Sovereignty Pipeline

**Version**: v0.1.0  
**Last Updated**: 2025-11-19  
**Status**: Foundation complete, Stage 3 (YOLO) next

This document provides architectural context for Claude instances working on this codebase.

---

## Project Overview

Local-first ML-powered photo organization that replicates cloud service search capabilities (iCloud, Google Photos) while maintaining complete data sovereignty. All processing happens locally, no cloud APIs.

**Current State**: Stages 1-2 complete (EXIF/GPS extraction), Stage 3 (YOLO object detection) next.

---

## Architecture

### Three-Layer Design Pattern

**Foundation Principle**: Clear separation of concerns across all processing stages.

```
┌─────────────────────────────────────────┐
│  Layer 3: Orchestration                 │
│  (orchestration/*.py, dev_tools/*.py)   │
│  - CLI interfaces (typer)               │
│  - Combines extraction + persistence    │
│  - Progress reporting & user output     │
└─────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────┐
│  Layer 2: Persistence                   │
│  (src/database.py)                      │
│  - ALL SQLite operations                │
│  - Schema evolution                     │
│  - Query helpers                        │
└─────────────────────────────────────────┘
              ▼
┌─────────────────────────────────────────┐
│  Layer 1: Extraction & Organization     │
│  (src/exif_parser.py, gps_extractor.py, │
│   organize.py)                          │
│  - Pure functions (data in → data out)  │
│  - No database operations               │
│  - No user-facing output                │
│  - Returns Python native types          │
└─────────────────────────────────────────┘
```

**Why this matters**:
- Each layer testable independently
- Extraction logic reusable in other contexts
- Database backend swappable
- Orchestration can change without touching core logic

### Module Responsibilities

**`src/config.py`** (98.15% coverage)
- Cross-platform configuration via platformdirs
- Optional config.yaml (falls back to sensible defaults)
- Config precedence: explicit arg > local config > system config > defaults
- Returns Path objects (all paths auto-expanded with `~` support)

**`src/database.py`** (100% coverage)
- **ALL** SQL operations live here (centralized)
- Incremental schema evolution (add tables as features built)
- Idempotent operations (safe to re-run)
- LEFT JOIN pattern for finding unprocessed items

**`src/exif_parser.py`**
- EXIF metadata extraction only (separation from organization logic)
- Date extraction hierarchy: EXIF DateTimeOriginal > DateTime > filesystem
- Camera information extraction (make, model)
- Returns `(datetime, source_string)` tuple
- No user-facing output (returns None on errors)
- Handles HEIC via pillow-heif

**`src/organize.py`**
- File organization and path generation
- Generates organized paths: `YYYY/YYYY-MM-DD_HHMMSS.ext`
- Archive extraction (unzip iCloud exports, photo backups)
- File type classification (images, videos, metadata, other)
- Returns structured data dicts with file_type and processed fields
- No user-facing output (orchestration handles logging)

**`src/gps_extractor.py`** (91.43% coverage)
- Extracts GPS from EXIF IFD tag 34853
- DMS → decimal conversion with hemisphere corrections
- Returns `(lat, lon, alt)` tuple or None
- Converts PIL IFDRational to Python float internally

**`orchestration/stage{N}_*.py`**
- Modular processing scripts (one per stage)
- Typer-based CLI interfaces (replaces argparse)
- Show component usage independently
- Will be unified into `main.py` in Week 6-7
- Each follows same pattern: query → extract → persist → report
- All user-facing output (print statements) lives here
- Orchestration layer: combines src/* modules with progress reporting

**`dev_tools/inspect_db.py`**
- Unified database inspection utility
- Query options: schema, all_images, gps_coverage, date_sources, cameras, etc.
- Replaces legacy query scripts

---

## Database Schema

### Current Tables (v0.1.0)

```sql
-- Stage 1: EXIF metadata
CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_path TEXT NOT NULL,
    organized_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    date_taken DATETIME,
    date_source TEXT,  -- 'exif_datetime_camera', 'filesystem', etc.
    camera_make TEXT,
    camera_model TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Stage 2: GPS coordinates
CREATE TABLE locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    latitude REAL NOT NULL,      -- Decimal degrees (-90 to 90)
    longitude REAL NOT NULL,     -- Decimal degrees (-180 to 180)
    altitude REAL,               -- Meters above sea level (can be NULL or negative)
    FOREIGN KEY (image_id) REFERENCES images(id)
);

-- Stage 3: YOLO detections (TODO)
-- CREATE TABLE object_tags (
--     id INTEGER PRIMARY KEY,
--     image_id INTEGER NOT NULL,
--     class_name TEXT NOT NULL,
--     confidence REAL NOT NULL,
--     bbox_x INTEGER, bbox_y INTEGER,
--     bbox_width INTEGER, bbox_height INTEGER,
--     FOREIGN KEY (image_id) REFERENCES images(id)
-- );
```

### Schema Evolution Strategy

**Pattern**: Incremental table addition in `create_database()`

- Week 1: Added `images` table
- Week 2: Added `locations` table
- Week 3: Will add `object_tags` table
- Week 4-5: Will add `embeddings`, `text_extracts` tables

**Why**: All schema visible in one place, incremental development, clear relationships.

### Idempotent Processing Pattern

**LEFT JOIN to find unprocessed items:**

```python
# Example: Find images without GPS
SELECT i.id, i.organized_path 
FROM images i
LEFT JOIN locations l ON i.id = l.image_id
WHERE l.id IS NULL
```

**Benefits**:
- Safe to re-run after crashes
- Add new photos incrementally
- Fix bugs and reprocess only affected images

---

## Testing Strategy

### Test Philosophy (v0.1.0 Breakthrough)

**High-level API tests with real data > low-level unit tests with synthetic data**

**Good Example** (matches production usage):
```python
@pytest.mark.integration
def test_extract_gps_from_sample_images(sample_photos_dir):
    """Test with REAL image files."""
    coords = extract_gps_coords(str(photo_path))  # Public API
    if coords:
        lat, lon, alt = coords
        assert -90 <= lat <= 90
```

**Avoid** (brittle, tests implementation details):
```python
def test_convert_dms_with_synthetic_data():
    """Test internal helper with synthetic rational tuples."""
    dms = ((37, 1), (48, 1), (54.6, 1))  # Assumes PIL internal format
    decimal = convert_to_degrees(dms)    # Private helper
```

**Why this works**:
1. Tests what users actually call (public API)
2. Tests with real data (actual EXIF/GPS from images)
3. Resilient to internal refactoring
4. Matches `orchestration/stage2_extract_gps.py` workflow

### Running Tests

```bash
# Full suite
pytest

# With coverage
pytest --cov=src --cov-report=term-missing

# Specific module
pytest tests/test_gps_extractor.py -v

# Skip integration tests (need sample images)
pytest -m "not integration"

# Show coverage HTML
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Fixtures (`tests/conftest.py`)

- `temp_db`: Temporary database file (auto-cleanup)
- `temp_db_with_schema`: Database with tables created
- `temp_dir`: Temporary directory
- `sample_photos_dir`: Points to `data/sample_photos/`
- `sample_heic_with_gps`, `sample_jpeg`, `sample_png`: Specific file types
- `mock_config`: Configuration dictionary with temp paths
- `sample_image_data`: Image metadata dict (datetime objects, not strings!)

---

## Development Standards

### Code Style

- **Type hints**: On all function signatures
- **Docstrings**: Google-style for public functions
- **Comments**: For non-obvious logic only
- **Formatting**: Ruff (configured in pyproject.toml)
- **Line length**: 88 characters (ruff default)
- **Testing**: Pytest with >90% coverage target
- **Python version**: 3.11+ (3.10 nearing EOL)

### Git Workflow

- **Conventional commits**: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`, `ci:`, `style:`
- **Tags**: Annotated tags for releases (`git tag -a v0.1.0 -m "message"`)
- **Commit messages**: Clear, descriptive, reference issues when applicable
- **Pre-commit hooks**: Run `pre-commit install` for automatic linting

### Package Management

- **Recommended**: `uv pip install -e ".[dev]"` (faster)
- **Alternative**: `pip install -e ".[dev]"`
- **Dependencies**: Defined in `pyproject.toml`
- **Optional groups**: `[dev]`, `[stage3]`, `[stage4]`, `[stage5]`

### CI/CD

**GitHub Actions workflows**:

1. **`.github/workflows/ci.yml`** - Main CI pipeline:
   - Runs on push to `main` and all PRs
   - Lint job: `ruff check` and `ruff format --check`
   - Test job: Matrix testing on Python 3.11 and 3.12
   - Unit tests only (integration tests skipped - no sample images in CI)
   - Coverage uploaded to Codecov (Python 3.11 only)

2. **`.github/workflows/pre-commit.yml`** - Pre-commit validation:
   - Runs on PRs to ensure code quality
   - Executes all pre-commit hooks

**Local pre-commit setup** (optional but recommended):
```bash
# Install pre-commit hooks
uv pip install pre-commit
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

**Pre-commit hooks** (`.pre-commit-config.yaml`):
- Ruff linting with auto-fix
- Ruff formatting
- Trailing whitespace removal
- End-of-file fixer
- YAML validation
- Large file detection (max 1MB)
- Merge conflict detection

---

## Gotchas & Important Notes

### 1. Path Objects vs Strings

**`generate_organized_path()` returns Path, not string!**

```python
# WRONG
path = generate_organized_path(date, 'exif', 'IMG_1234.HEIC')
assert '2025/' in path  # TypeError: argument of type 'PosixPath' is not iterable

# RIGHT
path = generate_organized_path(date, 'exif', 'IMG_1234.HEIC')
assert '2025/' in str(path)  # Convert to string first
```

### 2. Fixture Date Types

**`sample_image_data` fixture uses datetime objects, not strings!**

```python
# In conftest.py
'date_taken': datetime(2025, 5, 22, 14, 30, 22),  # datetime object

# NOT this:
'date_taken': '2025-05-22 14:30:22',  # String - causes AttributeError
```

**Why**: `insert_image()` expects datetime and calls `.strftime()` on it.

### 3. PIL IFDRational Conversion

**GPS extraction must convert IFDRational to Python float:**

```python
# Altitude comes back as IFDRational from PIL
altitude = gps_ifd.get(6)

# MUST convert before returning (SQLite doesn't accept IFDRational)
if altitude is not None:
    altitude = float(altitude)

return (lat, lon, altitude)  # All Python native types
```

**Why**: SQLite only accepts Python native types. Lat/lon auto-convert via arithmetic, but altitude doesn't.

### 4. Date Range Queries with BETWEEN

**String dates in BETWEEN default to midnight:**

```python
# This excludes 2025-01-04 at 12:00:00!
query_by_date_range(conn, "2025-01-02", "2025-01-04")
# Because "2025-01-04" = "2025-01-04 00:00:00" (midnight)

# To include full day:
query_by_date_range(conn, "2025-01-02", "2025-01-04 23:59:59")
```

### 5. Config Loading Precedence

**Config loads in this order:**

1. Explicit `--config` argument
2. `./config.yaml` (current directory)
3. `~/.config/photo-pipeline/config.yaml` (platformdirs)
4. Built-in defaults (no file needed)

**Partial configs merge with defaults** - you don't need to specify everything.

### 6. Sample Photos Requirements

**For integration tests:**
- Add sample images to `data/sample_photos/` (gitignored)
- Mix of HEIC and JPEG formats
- Include at least one image with GPS EXIF data
- All gitignored (privacy-first)

### 7. Test Imports

**Always import from src/, not relative:**

```python
# RIGHT
from src.gps_extractor import extract_gps_coords
from src.database import insert_image

# WRONG
from gps_extractor import extract_gps_coords  # ModuleNotFoundError
```

### 8. Archive Directory Exclusion

**pytest must exclude `tests/archive/`:**

```toml
# In pyproject.toml
[tool.pytest.ini_options]
norecursedirs = ["tests/archive", ".git", ".venv", "__pycache__"]
```

**Why**: Archive contains legacy scripts that aren't proper pytest files.

---

## Common Tasks

### Adding a New Processing Stage

Follow the established pattern:

1. **Create extraction module**: `src/{stage}_extractor.py`
   - Pure functions, no database operations
   - Return Python native types

2. **Update database.py**: Add table + helpers
   ```python
   # In create_database()
   cursor.execute("CREATE TABLE IF NOT EXISTS {stage}_table (...)")
   
   def insert_{stage}(conn, image_id, data):
       # Insert logic
   
   def query_images_without_{stage}(conn):
       # LEFT JOIN to find unprocessed
   ```

3. **Create orchestration script**: `orchestration/stage{N}_{stage}.py`
   - Import from src/
   - Query → Extract → Persist → Report
   - CLI with typer
   - All user-facing output (print statements) here

4. **Write tests**: `tests/test_{stage}.py`
   - Use high-level API with real sample data
   - Integration tests with sample images

5. **Test incrementally**:
   - iPython on single image
   - Small batch (5-10 images)
   - Full run

### Debugging GPS Extraction

```python
# In iPython
from PIL import Image
from pillow_heif import register_heif_opener
register_heif_opener()

img = Image.open('data/sample_photos/your_image.HEIC')
exif = img.getexif()

# Check for GPS IFD
gps_ifd = exif.get_ifd(34853)
print(gps_ifd)  # Should show GPS tags

# Extract specific tags
lat = gps_ifd.get(2)  # Latitude
lon = gps_ifd.get(4)  # Longitude
print(f"Lat: {lat}, Lon: {lon}")
```

### Running Individual Orchestration Scripts

```bash
# Stage 1: EXIF extraction and organization
python orchestration/stage1_process_photos.py --source ~/Pictures --output ~/organized

# Stage 2: GPS extraction
python orchestration/stage2_extract_gps.py --db ~/organized/photo_archive.db

# Database inspection
python dev_tools/inspect_db.py --query gps_coverage
```

---

## Performance Considerations

### Performance Characteristics

- **EXIF extraction**: I/O bound (~100-200 images/minute)
- **GPS extraction**: EXIF parsing overhead (~50-100 images/minute)
- **Expected YOLO** (Stage 3): GPU bound, batch processing required

### Batch Processing Patterns

**Stages 1-2**: Sequential (I/O bound, batching doesn't help)

**Stages 3-5**: Batch processing needed (GPU/ML bound)
```python
# YOLO example (future)
for batch in batch_images(unprocessed, batch_size=32):
    detections = model.predict(batch)  # GPU batch inference
    for image_id, objects in zip(batch, detections):
        insert_object_tags(conn, image_id, objects)
```

---

## Cross-Platform Notes

### Path Handling

**Always use Path objects, expanduser() for CLI:**

```python
from pathlib import Path

# CLI arguments
db_path = Path(args.db).expanduser()  # Handles ~

# Programmatic
db_path = Path.home() / "data" / "photo_archive.db"
```

### Default Directories (platformdirs)

- **Linux**: 
  - Config: `~/.config/photo-pipeline/`
  - Data: `~/.local/share/photo-pipeline/`
  - Cache: `~/.cache/photo-pipeline/`

- **macOS**:
  - Config/Data: `~/Library/Application Support/photo-pipeline/`
  - Cache: `~/Library/Caches/photo-pipeline/`

- **Windows**:
  - Config/Data: `%APPDATA%/photo-pipeline/`
  - Cache: `%LOCALAPPDATA%/photo-pipeline/Cache/`

---

## Future Refactoring (Week 6-7)

### Unified CLI Plan

**Current** (modular scripts with typer):
```bash
python orchestration/stage1_process_photos.py --source ~/photos
python orchestration/stage2_extract_gps.py --db photo_archive.db
```

**Future** (unified interface):
```bash
python main.py init --source ~/photos --output ~/organized
python main.py process --stage gps
python main.py process --stage yolo --device cuda
python main.py search --object dog
```

**Implementation**:
- Keep `src/` modules unchanged
- Create `main.py` with typer (already using typer in orchestration scripts)
- Import and call existing functions from orchestration scripts
- Optional: Add rich/questionary for enhanced TUI

---

## Resources & References

### Key Files for Context

- `docs/public/blueprint.md`: Original project plan and technical specs
- `ARCHITECTURE.md`: High-level architecture overview
- `orchestration/README.md`: Modular script documentation
- `tests/archive/README.md`: Why legacy scripts were archived

### Session Summaries

- `docs/private/session-summaries/sessions-3-4-gps-extraction-summary.md`: Week 2 GPS extraction, architectural decisions

### External Dependencies

- **Pillow**: Image processing and EXIF reading
- **pillow-heif**: HEIC format support
- **platformdirs**: Cross-platform paths
- **pytest + pytest-cov**: Testing infrastructure
- **pyyaml**: Configuration loading

---

**Last Updated**: 2025-11-19 after v0.1.0 test suite completion  
**Next**: Install YOLO dependencies, Stage 3 object detection
