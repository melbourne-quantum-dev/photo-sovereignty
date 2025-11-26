# src/photo_details_parser.py
"""Parse iCloud Photo Details CSVs for metadata extraction.

This module handles iCloud Photo Library export metadata:
- Parse Photo Details CSV format
- Extract original creation dates from iCloud's canonical metadata
- Build filename-to-metadata lookup dicts for Stage 1 processing
- Consolidate multi-part export CSVs

Separation of concerns:
- exif_extractor.py: Reads metadata from file contents (binary data)
- photo_details_parser.py: Reads metadata from CSV files (structured text)
- organize.py: Makes organizational decisions using both metadata sources

Integration:
- Stage 1 (organize photos) optionally loads Photo Details to improve date extraction
- Particularly valuable for screenshots/downloads that lack EXIF data
- iCloud's originalCreationDate provides canonical timestamp when available
"""

import csv
from datetime import datetime
from pathlib import Path


def parse_icloud_date(date_string: str) -> datetime | None:
    """Parse iCloud date format from Photo Details CSV.

    iCloud uses format: "Friday July 4,2025 3:46 AM GMT"

    Args:
        date_string: iCloud's date format string

    Returns:
        datetime object or None if parsing fails

    Examples:
        >>> parse_icloud_date("Friday July 4,2025 3:46 AM GMT")
        datetime(2025, 7, 4, 3, 46)
        >>> parse_icloud_date("Monday December 25,2023 11:30 PM GMT")
        datetime(2023, 12, 25, 23, 30)
    """
    if not date_string:
        return None

    try:
        # iCloud format: "Friday July 4,2025 3:46 AM GMT"
        # Remove day name (first word) and timezone (last word)
        parts = date_string.strip().split()

        if len(parts) < 5:
            return None

        # Skip day name (parts[0]) and timezone (parts[-1])
        # Keep: "July 4,2025 3:46 AM"
        clean_date = " ".join(parts[1:-1])

        # Try parsing with AM/PM
        for fmt in ["%B %d,%Y %I:%M %p", "%B %d,%Y %H:%M"]:
            try:
                return datetime.strptime(clean_date, fmt)
            except ValueError:
                continue

        return None
    except Exception:
        return None


def load_photo_details(csv_path: Path) -> dict[str, dict]:
    """Load Photo Details CSV into filename lookup dict.

    Args:
        csv_path: Path to Photo Details CSV file (consolidated or single)

    Returns:
        dict mapping filename to metadata:
        {
            "IMG_1234.HEIC": {
                "date": datetime(2025, 7, 4, 3, 46),
                "checksum": "abc123...",
            },
            ...
        }

    Note:
        Silently skips rows with missing filenames or unparseable dates.
        Returns empty dict if file doesn't exist or is malformed.
    """
    if not csv_path or not Path(csv_path).exists():
        return {}

    details = {}

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)

            for row in reader:
                filename = row.get("filename")
                date_str = row.get("originalCreationDate")
                checksum = row.get("fileChecksum")

                if not filename:
                    continue

                parsed_date = parse_icloud_date(date_str) if date_str else None

                details[filename] = {
                    "date": parsed_date,
                    "checksum": checksum,
                }

    except Exception:
        # Return empty dict on any error (file not found, malformed CSV, etc.)
        return {}

    return details


def consolidate_csvs(csv_paths: list[Path], output_path: Path) -> Path:
    """Consolidate multiple Photo Details CSVs from multi-part iCloud exports.

    When iCloud exports are split across multiple downloads, each part contains
    a "Photo Details.csv" file. This function merges them into a single CSV,
    deduplicating entries by filename (last occurrence wins).

    Args:
        csv_paths: List of Photo Details CSV file paths
        output_path: Where to write the consolidated CSV

    Returns:
        Path to consolidated CSV file (same as output_path)

    Raises:
        ValueError: If csv_paths is empty or output_path is None

    Example:
        >>> csv_files = [
        ...     Path("export_part1/Photo Details.csv"),
        ...     Path("export_part2/Photo Details.csv"),
        ... ]
        >>> consolidated = consolidate_csvs(csv_files, Path("consolidated.csv"))
    """
    if not csv_paths:
        raise ValueError("csv_paths cannot be empty")

    if not output_path:
        raise ValueError("output_path must be specified")

    # Use dict to deduplicate by filename (last occurrence wins)
    all_rows = {}
    fieldnames = None

    for csv_path in csv_paths:
        if not csv_path.exists():
            continue

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                # Capture fieldnames from first valid CSV
                if fieldnames is None and reader.fieldnames:
                    fieldnames = reader.fieldnames

                for row in reader:
                    filename = row.get("filename")
                    if filename:
                        all_rows[filename] = row  # Deduplicate by filename

        except Exception:
            # Skip malformed CSVs
            continue

    # Write consolidated CSV
    if not all_rows or not fieldnames:
        # Create empty file if no valid data
        output_path.touch()
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows.values())

    return output_path
