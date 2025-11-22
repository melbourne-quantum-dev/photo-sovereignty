#!/usr/bin/env python3
"""
Process photos: Extract EXIF, organize files, store in database.

Usage:
    # Use config.yaml paths (recommended)
    python stage1_process_photos.py

    # Override specific paths
    python stage1_process_photos.py --source ~/Downloads/photos --db test.db

    # Use custom config file
    python stage1_process_photos.py --config production.yaml
"""

from pathlib import Path
from typing import Optional

import typer

from src.database import create_database, insert_image
from src.organize import rename_and_organize

app = typer.Typer()


def process_photos(
    source_dir, output_dir, db_path="photo_archive.db", preserve_filenames="descriptive_only"
):
    """Main processing pipeline with duplicate checking.

    Foundation note: Idempotent processing enables:
    - Safe re-runs after interruptions
    - Adding new photos without reprocessing existing
    - Database recovery scenarios
    """
    print(f"\n{'=' * 60}")
    print("PROCESSING PHOTOS")
    print(f"{'=' * 60}")
    print(f"Processing photos from: {source_dir}")
    print(f"Organizing to: {output_dir}")
    print(f"Database: {db_path}\n")

    # Create/connect to database
    conn = create_database(db_path)

    # Check what's already been processed
    cursor = conn.cursor()
    cursor.execute("SELECT original_path FROM images")
    already_processed = {row[0] for row in cursor.fetchall()}

    print(f"📊 Database contains {len(already_processed)} processed images\n")

    # Process and organize files
    results = rename_and_organize(source_dir, output_dir, preserve_filenames)

    # Separate results by file type
    images = [r for r in results if r["file_type"] == "image"]
    videos = [r for r in results if r["file_type"] == "video"]
    metadata_files = [r for r in results if r["file_type"] == "metadata"]
    other_files = [r for r in results if r["file_type"] == "other"]

    # Insert images and track progress
    new_count = 0
    skip_count = 0
    MAX_SKIP_DISPLAY = 5  # Show first 5 skips, then summarize

    for image_data in images:
        # Show processing progress
        print(f"📸 {Path(image_data['original_path']).name} → {image_data['filename']}")

        # Check if already in database
        if image_data["original_path"] in already_processed:
            skip_count += 1

            # Show first few skips, then summarize rest
            if skip_count <= MAX_SKIP_DISPLAY:
                print(f"  ⏭️  Skip: {image_data['filename']} (already in database)")
            elif skip_count == MAX_SKIP_DISPLAY + 1:
                remaining = len(images) - new_count - MAX_SKIP_DISPLAY
                print(f"  ⏭️  ... and {remaining} more skipped")

            continue

        # Insert new image
        image_id = insert_image(conn, image_data)
        new_count += 1
        print(f"  ✅ DB ID {image_id}: {image_data['filename']}")

    conn.close()

    # Report skipped files
    if videos:
        print(f"\n📹 Skipped {len(videos)} video files")
    if metadata_files:
        print(f"📄 Skipped {len(metadata_files)} metadata files")
    if other_files:
        print(f"❓ Skipped {len(other_files)} other files")

    # Summary
    print(f"\n{'=' * 60}")
    print("Processing Complete")
    print(f"{'=' * 60}")
    print(f"✅ New images: {new_count}")
    if skip_count > 0:
        print(f"⏭️  Skipped (already processed): {skip_count}")
    print(f"📊 Total in database: {len(already_processed) + new_count}")

    if new_count > 0:
        print(f"📁 Organized into: {output_dir}")
        print(f"🗄️  Database: {db_path}")
    else:
        print("⚠️  No new images processed")
    print(f"{'=' * 60}")


@app.command()
def main(
    config: str = typer.Option(
        "config.yaml",
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    source: Optional[str] = typer.Option(
        None,
        "--source",
        "-s",
        help="Source directory with photos (overrides config)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for organized photos (overrides config)",
    ),
    db: Optional[str] = typer.Option(
        None,
        "--db",
        "-d",
        help="Database file path (overrides config)",
    ),
):
    """Process photos: Extract EXIF, organize files, store in database.

    Configuration Loading:
        Loads paths from config.yaml by default. CLI arguments override config values.
        This enables privacy-preserving development (config.yaml gitignored) while
        maintaining flexible CLI interface for testing/debugging.

    Examples:
        # Use config.yaml paths (recommended)
        python stage1_process_photos.py

        # Override specific paths
        python stage1_process_photos.py --source ~/Downloads/photos --db test.db

        # Use custom config file
        python stage1_process_photos.py --config production.yaml
    """
    from src.config import load_config

    # Load configuration
    try:
        config_data = load_config(config)
    except FileNotFoundError as e:
        typer.echo(f"❌ {e}")
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"❌ Error loading config: {e}")
        raise typer.Exit(1)

    # Use CLI args if provided, otherwise use config
    source_dir = source if source else config_data["paths"]["input_directory"]
    output_dir = output if output else config_data["paths"]["output_directory"]
    db_path = db if db else config_data["paths"]["database"]

    # Expand paths if provided via CLI
    if source:
        source_dir = Path(source_dir).expanduser()
    if output:
        output_dir = Path(output_dir).expanduser()
    if db:
        db_path = Path(db_path).expanduser()

    # Validate source directory exists
    if not source_dir.exists():
        typer.echo(f"❌ Source directory not found: {source_dir}")
        raise typer.Exit(1)

    # Extract processing options
    preserve_filenames = config_data["processing"]["preserve_filenames"]

    # Run processing
    process_photos(str(source_dir), str(output_dir), str(db_path), preserve_filenames)


if __name__ == "__main__":
    app()
