#!/usr/bin/env python3
"""Consolidate Photo Details CSVs from iCloud export into unique files.

Problem:
- iCloud exports Photo Details across 5 parts
- Each part has Photo Details-1.csv, Photo Details-2.csv, etc.
- Moving them creates filename conflicts

Solution:
- Find all Photo Details CSVs
- Read and merge content (skip duplicate rows)
- Write to sequential files in Metadata/Photo_Details/
- Each output file ~2000 lines for manageability

Usage:
    python dev_tools/consolidate_photo_details.py \
        --source data/iCloud_Export \
        --output data/iCloud_Export/Metadata/Photo_Details
"""

import csv
import shutil
from collections import OrderedDict
from pathlib import Path

import typer

app = typer.Typer()


def find_all_photo_details(source_dir: Path) -> list[Path]:
    """Find all Photo Details CSV files across iCloud export parts.

    Args:
        source_dir: Root iCloud export directory

    Returns:
        List of Photo Details CSV paths
    """
    csv_files = []
    for csv_file in source_dir.rglob("Photo Details*.csv"):
        csv_files.append(csv_file)

    return sorted(csv_files)


def parse_csv_with_dedup(csv_path: Path) -> list[dict]:
    """Parse CSV and return rows as dicts.

    Args:
        csv_path: Path to Photo Details CSV

    Returns:
        List of row dicts
    """
    rows = []
    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as e:
        print(f"Warning: Failed to read {csv_path}: {e}")

    return rows


def merge_all_csvs(csv_files: list[Path]) -> list[dict]:
    """Merge all Photo Details CSVs, removing duplicates by fileChecksum.

    Args:
        csv_files: List of Photo Details CSV paths

    Returns:
        Deduplicated list of photo metadata dicts
    """
    # Use OrderedDict to preserve first occurrence order while deduplicating
    unique_photos = OrderedDict()

    for csv_file in csv_files:
        print(f"Reading {csv_file}...")
        rows = parse_csv_with_dedup(csv_file)

        for row in rows:
            checksum = row.get("fileChecksum", "")
            if checksum and checksum not in unique_photos:
                unique_photos[checksum] = row

    return list(unique_photos.values())


def write_split_csvs(
    merged_data: list[dict], output_dir: Path, rows_per_file: int = 2000
) -> None:
    """Write merged data to sequential CSV files.

    Args:
        merged_data: List of photo metadata dicts
        output_dir: Output directory
        rows_per_file: Max rows per output file
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine fieldnames from first row
    if not merged_data:
        print("No data to write!")
        return

    fieldnames = list(merged_data[0].keys())

    # Write in chunks
    file_index = 0
    for i in range(0, len(merged_data), rows_per_file):
        chunk = merged_data[i : i + rows_per_file]
        output_file = output_dir / f"Photo_Details_{file_index:03d}.csv"

        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(chunk)

        print(f"Wrote {len(chunk)} rows to {output_file}")
        file_index += 1


@app.command()
def main(
    source: Path = typer.Option(
        "data/iCloud_Export", help="Root iCloud export directory"
    ),
    output: Path = typer.Option(
        "data/iCloud_Export/Metadata/Photo_Details_Consolidated",
        help="Output directory for consolidated CSVs",
    ),
    rows_per_file: int = typer.Option(
        2000, help="Number of rows per output CSV file"
    ),
    dry_run: bool = typer.Option(
        False, help="Show what would be done without writing files"
    ),
):
    """Consolidate Photo Details CSVs from iCloud export.

    Example:
        python dev_tools/consolidate_photo_details.py \\
            --source data/iCloud_Export \\
            --output data/iCloud_Export/Metadata/Photo_Details_Consolidated
    """
    source = source.expanduser()
    output = output.expanduser()

    print(f"Searching for Photo Details CSVs in {source}...")
    csv_files = find_all_photo_details(source)
    print(f"Found {len(csv_files)} Photo Details CSV files\n")

    if not csv_files:
        print("No Photo Details CSVs found!")
        return

    print("Merging and deduplicating...")
    merged_data = merge_all_csvs(csv_files)
    print(f"\nTotal unique photos: {len(merged_data)}")

    if dry_run:
        print(f"\n[DRY RUN] Would write {len(merged_data)} rows to {output}/")
        print(
            f"[DRY RUN] Estimated files: {(len(merged_data) + rows_per_file - 1) // rows_per_file}"
        )
        return

    print(f"\nWriting consolidated CSVs to {output}/...")
    write_split_csvs(merged_data, output, rows_per_file)

    print("\nDone! Summary:")
    print(f"  - Processed {len(csv_files)} source CSV files")
    print(f"  - Merged {len(merged_data)} unique photos")
    print(f"  - Output: {output}/")


if __name__ == "__main__":
    app()
