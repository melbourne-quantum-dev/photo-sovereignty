#!/usr/bin/env python3
"""Extract photos from iCloud CSV labels into organized directories.

Example use case:
- iCloud exports 'Zetta 2020.csv' with original filenames
- After organizing, photos are renamed and moved
- This script finds those photos and copies them to labeled directories
- Perfect for creating YOLO training sets

Usage:
    python dev_tools/extract_labeled_photos.py \
        --csv memories/Zetta_2020.csv \
        --label dog_zetta \
        --output labeled_photos/
"""

import csv
import shutil
import sqlite3
from pathlib import Path

import typer

app = typer.Typer()


def parse_csv_labels(csv_path: Path) -> list[str]:
    """Extract filenames from iCloud memory CSV.

    Args:
        csv_path: Path to CSV file with single column of filenames

    Returns:
        List of original filenames (e.g., ['IMG_41353.HEIC', 'IMG_41354.HEIC'])
    """
    filenames = []
    with open(csv_path, "r") as f:
        reader = csv.reader(f)
        for row in reader:
            if row:  # Skip empty rows
                filenames.append(row[0])
    return filenames


def find_organized_paths(conn, original_filenames: list[str]) -> dict[str, str]:
    """Map original filenames to their organized paths.

    Args:
        conn: Database connection
        original_filenames: List like ['IMG_41353.HEIC', 'IMG_41354.HEIC']

    Returns:
        Dict mapping original filename → organized path
        Example: {'IMG_41353.HEIC': '2020/2020-03-15_143022.HEIC'}
    """
    cursor = conn.cursor()
    mapping = {}

    for filename in original_filenames:
        # Search by original_path since filename column stores organized name
        # Use LIKE pattern to match filename at end of path
        cursor.execute(
            """
            SELECT organized_path
            FROM images
            WHERE original_path LIKE ?
        """,
            (f"%/{filename}",),
        )
        result = cursor.fetchone()
        if result:
            mapping[filename] = result[0]
        else:
            print(f"Warning: {filename} not found in database")

    return mapping


@app.command()
def main(
    csv: Path = typer.Option(..., help="Path to iCloud memory CSV file"),
    label: str = typer.Option(..., help="Label name for output directory"),
    output: Path = typer.Option(
        "labeled_photos/", help="Output directory for labeled photos"
    ),
    db: Path = typer.Option(
        "photo_archive.db", help="Path to photo database", envvar="PHOTO_DB"
    ),
    copy: bool = typer.Option(
        True, help="Copy files (True) or create symlinks (False)"
    ),
):
    """Extract labeled photos from CSV into organized directories.

    Example:
        python dev_tools/extract_labeled_photos.py \\
            --csv memories/Zetta_2020.csv \\
            --label dog_zetta \\
            --output yolo_training/labeled/
    """
    # Expand paths
    csv = csv.expanduser()
    output = output.expanduser()
    db = db.expanduser()

    # Parse CSV
    print(f"Reading labels from {csv}")
    original_filenames = parse_csv_labels(csv)
    print(f"Found {len(original_filenames)} labeled photos")

    # Connect to database
    conn = sqlite3.connect(db)

    # Map original → organized paths
    print(f"Querying database for organized paths...")
    mapping = find_organized_paths(conn, original_filenames)
    print(f"Found {len(mapping)}/{len(original_filenames)} photos in database")

    # Create output directory
    output_dir = output / label
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy/symlink files
    print(f"\n{'Copying' if copy else 'Symlinking'} to {output_dir}/")
    for original_name, organized_path in mapping.items():
        src = Path(organized_path)
        dst = output_dir / src.name  # Use organized filename

        if not src.exists():
            print(f"Warning: {src} not found on disk (database out of sync?)")
            continue

        if copy:
            shutil.copy2(src, dst)
        else:
            dst.symlink_to(src.absolute())

        print(f"  {original_name} → {src.name}")

    print(f"\nDone! {len(mapping)} photos in {output_dir}/")


if __name__ == "__main__":
    app()
