#!/usr/bin/env python3
"""GPS Extraction Orchestration Script.

This script orchestrates GPS coordinate extraction from organized photos and
persistence to the database. It serves as the Week 2 processing stage in the
incremental photo sovereignty pipeline.

Architecture Notes
------------------
This is a **modular development script** that will be refactored into a unified
CLI interface (main.py) in Week 6-7. The modular approach during development:

1. Enables independent testing of each pipeline stage
2. Maintains clear separation of concerns (extraction vs persistence)
3. Allows incremental feature addition without breaking existing stages
4. Provides simple CLI interface during development/debugging

Relationship with gps_extractor.py
-----------------------------------
- **gps_extractor.py**: Pure extraction logic (data in → data out)
  - extract_gps_coords(): Returns (lat, lon, alt) tuple or None
  - convert_to_degrees(): DMS → decimal conversion
  - No database operations, no file I/O side effects

- **extract_gps.py** (this file): Orchestration layer
  - Queries database for images needing GPS extraction
  - Calls gps_extractor functions for each image
  - Persists results using database.py functions
  - Provides CLI interface and progress reporting

This separation enables:
- Testing extraction logic independently (gps_extractor tests)
- Reusing extraction functions in other contexts
- Swapping database backends without touching extraction code
- Clear architectural boundaries (Foundation Era principle)

Future Refactoring (Week 6-7)
------------------------------
This script will be absorbed into main.py as:
    python main.py process --stage gps --db photo_archive.db

The extraction and database modules remain unchanged; only the CLI interface
is unified. This demonstrates modular → unified workflow in portfolio.

Usage
-----
    python extract_gps.py --db ~/data/media/images/organised/photo_archive.db

Examples
--------
    # Extract GPS from all unprocessed images
    python extract_gps.py --db photo_archive.db

    # Run on specific database (absolute path)
    python extract_gps.py --db /path/to/archive/photo_archive.db

Notes
-----
- Idempotent: Safe to re-run, only processes images without existing GPS data
- Incremental: Uses LEFT JOIN to find unprocessed images
- Progress: Reports extraction success/failure for each image
- Statistics: Shows coverage percentage at completion

Author: Leonardo
Date: 2025-10-27 (Session 3-4)
Stage: Week 2 - GPS Extraction
"""

from pathlib import Path
from typing import Optional

import typer

from src.config import load_config
from src.database import create_database, insert_location, query_images_without_gps
from src.gps_extractor import extract_gps_coords

app = typer.Typer()


def extract_gps(db_path):
    """Main GPS extraction pipeline.

    Orchestrates the complete GPS extraction workflow:
    1. Connect to database (creates locations table if needed)
    2. Query images without GPS data (LEFT JOIN on locations table)
    3. Extract GPS coordinates from each image file
    4. Insert coordinates into locations table
    5. Report extraction statistics

    This function is idempotent - safe to run multiple times. Only processes
    images that don't have existing location records. This enables:
    - Resume after interruption (crash, manual stop)
    - Add new photos without reprocessing existing
    - Fix extraction bugs and re-run on affected images only

    Args:
        db_path (Path): Path to photo archive SQLite database.

    Returns:
        int: Number of images successfully processed with GPS extraction.

    Side Effects:
        - Creates locations table if not exists (via create_database)
        - Inserts GPS coordinates into database (via insert_location)
        - Prints progress messages to stdout

    Example:
        >>> db = Path("photo_archive.db")
        >>> success_count = extract_gps(db)
        Processing 535 images for GPS extraction...
        ✅ 2025-05-22_174534.heic: (-37.834667, 144.952592, 14.22m)
        ...
        >>> print(f"Extracted GPS from {success_count} images")
        Extracted GPS from 489 images

    Notes:
        - Images without GPS data are skipped (not errors)
        - Extraction errors logged but don't stop batch processing
        - Uses gps_extractor.py for actual coordinate extraction
        - Uses database.py for all database operations
    """
    print("GPS Extraction Pipeline")
    print(f"Database: {db_path}\n")

    # Step 1: Connect and ensure locations table exists
    # Foundation note: create_database() is idempotent - creates table if missing,
    # otherwise just returns connection. This enables running stages independently.
    conn = create_database(db_path)

    # Step 2: Find images needing GPS extraction
    # Uses LEFT JOIN to find images.id where locations.image_id IS NULL
    # This query pattern enables incremental processing across all stages
    images_to_process = query_images_without_gps(conn)

    if not images_to_process:
        print("✅ All images already have GPS data (or none available)")
        conn.close()
        return 0

    print(f"Processing {len(images_to_process)} images for GPS extraction...\n")

    # Step 3: Extract GPS from each image
    success_count = 0
    no_gps_count = 0
    error_count = 0

    for image_id, org_path in images_to_process:
        try:
            # Call extraction layer (pure function, no side effects)
            coords = extract_gps_coords(org_path)

            if coords:
                lat, lon, alt = coords

                # Call persistence layer (database.py handles SQL)
                insert_location(conn, image_id, lat, lon, alt)

                # Progress indicator with rounded altitude display
                filename = Path(org_path).name
                alt_str = f", {alt:.2f}m" if alt else ""
                print(f"✅ {filename}: ({lat:.6f}, {lon:.6f}{alt_str})")
                success_count += 1
            else:
                # Not an error - image just lacks GPS data
                # (Location services off, screenshot, edited photo, etc.)
                no_gps_count += 1

        except Exception as e:
            # Log error but continue processing other images
            print(f"❌ Error processing image {image_id}: {e}")
            error_count += 1

    conn.close()

    # Step 4: Report statistics
    total = len(images_to_process)
    gps_percentage = (success_count / total * 100) if total > 0 else 0

    print(f"\n{'=' * 60}")
    print("GPS Extraction Complete")
    print(f"{'=' * 60}")
    print(f"✅ GPS extracted: {success_count}/{total} images ({gps_percentage:.1f}%)")
    print(f"⏭️  No GPS data: {no_gps_count} images")

    if error_count > 0:
        print(f"❌ Errors: {error_count} images")

    print(f"{'=' * 60}")

    return success_count


@app.command()
def main(
    config: str = typer.Option(
        "config.yaml",
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    db: Optional[str] = typer.Option(
        None,
        "--db",
        "-d",
        help="Path to photo archive database (overrides config)",
    ),
):
    """Extract GPS coordinates from photos and store in database.

    Configuration Loading:
        Loads database path from config.yaml by default. CLI --db argument
        overrides config value. Enables privacy-preserving development while
        maintaining testing flexibility.

    Development Note:
        This is a standalone CLI script during Week 2-5 development.
        In Week 6-7, this functionality will be integrated into main.py
        as a subcommand: `python main.py process --stage gps`

        The extraction and database modules remain unchanged during refactoring;
        only the CLI interface is unified. This demonstrates clean architectural
        boundaries and modular -> unified development workflow.

    Examples:
        # Use config.yaml database path (recommended)
        python stage2_extract_gps.py

        # Override database path
        python stage2_extract_gps.py --db ~/test/photo_archive.db

        # Use custom config file
        python stage2_extract_gps.py --config production.yaml

    Foundation Note:
        This script processes only images without existing GPS data.
        Safe to run multiple times - enables incremental processing and error recovery.
    """

    # Load configuration
    try:
        config_data = load_config(config)
    except FileNotFoundError as e:
        typer.echo(f"❌ {e}")
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error loading config: {e}")
        raise typer.Exit(1)

    # Use CLI arg if provided, otherwise use config
    if db:
        db_path = Path(db).expanduser()
    else:
        db_path = config_data["paths"]["database"]

    # Validate database exists
    if not db_path.exists():
        typer.echo(f"❌ Database not found: {db_path}")
        typer.echo("Run stage1_process_photos.py first to create database")
        raise typer.Exit(1)

    # Run extraction pipeline
    extract_gps(db_path)


if __name__ == "__main__":
    app()
