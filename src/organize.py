# src/organize.py
"""File organization and archive extraction utilities.

This module handles:
- Generating organized file paths based on dates
- Organizing photos from source to destination directories
- Extracting photos from zip archives (iCloud exports, etc.)

Separation of concerns:
- This module performs file operations and returns data
- No user-facing output (print statements) - that belongs in orchestration layer
- Raises exceptions for error handling (caught by orchestration)
"""

import shutil
import zipfile
from pathlib import Path

from src.exif_parser import extract_camera_info, extract_exif_date


def _is_descriptive_name(stem: str) -> bool:
    """Check if filename is descriptive vs camera-generated.

    Camera-generated patterns include:
    - IMG_1234, DSC01234, DSCN1234
    - 20231215_143022 (date-based)
    - Screenshot patterns

    Args:
        stem: Filename without extension

    Returns:
        True if filename appears descriptive/meaningful
    """
    import re

    # Camera and auto-generated patterns
    camera_patterns = [
        r"^IMG_\d+$",  # IMG_1234
        r"^DSC[N]?\d+$",  # DSC01234, DSCN1234
        r"^\d{8}_\d{6}$",  # 20231215_143022
        r"^\d{4}-\d{2}-\d{2}_\d{6}$",  # 2023-12-15_143022 (already organized)
        r"^IMG-\d+",  # IMG-20231215-WA0001
        r"^PXL_",  # Pixel phone format (PXL_20231215_143022)
        r"^Screenshot",  # Screenshot_...
        r"^\d{4}-\d{2}-\d{2}",  # Starts with date
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",  # iCloud UUID exports
    ]

    return not any(re.match(pattern, stem, re.IGNORECASE) for pattern in camera_patterns)


def generate_organized_path(
    date, source_type, original_filename, preserve_filenames="descriptive_only"
):
    """Generate organized file path with optional filename preservation.

    Organization strategy:
    - Reliable EXIF dates → YYYY/ directory
    - Filesystem dates → filesystem_dates/ (needs review)
    - No date → unsorted/

    Args:
        date: datetime object or None
        source_type: 'exif_original', 'exif_datetime_camera', 'filesystem', etc.
        original_filename: 'IMG_3630.HEIC' or 'piazza-dei-signori.jpg'
        preserve_filenames: Filename preservation strategy:
            - 'descriptive_only': Preserve only non-camera names (default)
            - True: Always preserve original name
            - False: Never preserve (timestamp only)

    Returns:
        Path object like:
        - '2025/2025-06-02_001524.heic' (EXIF, camera name)
        - '2023/2023-06-15_143022_wedding-reception.jpg' (EXIF, descriptive)
        - 'filesystem_dates/2025-11-23_095802_piazza-dei-signori.jpg'
        - 'unsorted/corrupted-file.jpg'
    """
    # Extract original stem (without extension) and extension
    original_path = Path(original_filename)
    ext = original_path.suffix.lower()
    original_stem = original_path.stem

    # Case 1: No date at all (corrupted/unreadable)
    if date is None:
        return Path("unsorted") / original_filename

    # Generate timestamp
    timestamp = date.strftime("%Y-%m-%d_%H%M%S")

    # Determine if we should preserve the original filename
    should_preserve = False
    if preserve_filenames is True:
        should_preserve = True
    elif preserve_filenames == "descriptive_only":
        should_preserve = _is_descriptive_name(original_stem)
    # else preserve_filenames is False, should_preserve stays False

    # Build filename
    if should_preserve:
        filename = f"{timestamp}_{original_stem}{ext}"
    else:
        filename = f"{timestamp}{ext}"

    # Case 2: Filesystem date (unreliable - needs manual review)
    if source_type in ["filesystem", "exif_datetime_unknown"]:
        return Path("filesystem_dates") / filename

    # Case 3: Reliable EXIF date
    year = date.strftime("%Y")
    return Path(year) / filename


def rename_and_organize(source_dir, dest_dir, preserve_filenames="descriptive_only"):
    """Process all images in source_dir, organize into dest_dir.

    This is a pure data processing function - no user output.
    Orchestration layer handles progress reporting.

    Args:
        source_dir: Source directory with photos
        dest_dir: Destination directory for organized photos
        preserve_filenames: Filename preservation strategy:
            - 'descriptive_only': Preserve only non-camera names (default)
            - True: Always preserve original name
            - False: Never preserve (timestamp only)

    Returns:
        list of dicts: Each dict contains:
            - original_path: str
            - organized_path: str
            - filename: str
            - date_taken: datetime or None
            - date_source: str
            - camera_make: str or None
            - camera_model: str or None
            - file_type: str ('image', 'video', 'metadata', 'other')
            - processed: bool (True if copied, False if skipped)

    Raises:
        FileNotFoundError: If source_dir doesn't exist
        PermissionError: If dest_dir isn't writable
    """
    source = Path(source_dir)
    dest = Path(dest_dir)

    if not source.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    # Supported formats
    image_patterns = [
        "*.heic",
        "*.HEIC",
        "*.jpg",
        "*.JPG",
        "*.jpeg",
        "*.JPEG",
        "*.png",
        "*.PNG",
    ]

    # Store results
    results = []

    # Process all files
    for file_path in source.iterdir():
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()

        # Check if supported image
        is_image = any(file_path.match(pattern) for pattern in image_patterns)

        if is_image:
            # Extract metadata
            date, source_type = extract_exif_date(file_path)
            camera = extract_camera_info(file_path)

            # Generate organized path
            rel_path = generate_organized_path(
                date, source_type, file_path.name, preserve_filenames
            )
            new_path = dest / rel_path

            # Create directory if needed
            new_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy file (don't delete original yet - safety)
            shutil.copy2(file_path, new_path)

            # Store result
            results.append(
                {
                    "original_path": str(file_path),
                    "organized_path": str(new_path),
                    "filename": new_path.name,
                    "date_taken": date,
                    "date_source": source_type,
                    "camera_make": camera["make"],
                    "camera_model": camera["model"],
                    "file_type": "image",
                    "processed": True,
                }
            )

        else:
            # Track non-image files for orchestration reporting
            if suffix in {".mp4", ".mov", ".avi", ".mkv"}:
                file_type = "video"
            elif suffix in {".csv", ".txt", ".json"}:
                file_type = "metadata"
            else:
                file_type = "other"

            results.append(
                {
                    "original_path": str(file_path),
                    "organized_path": None,
                    "filename": file_path.name,
                    "date_taken": None,
                    "date_source": None,
                    "camera_make": None,
                    "camera_model": None,
                    "file_type": file_type,
                    "processed": False,
                }
            )

    return results


def unzip_archive(zip_path, extract_to=None):
    """Extract photos from zip archive (iCloud exports, photo backups, etc.).

    Common use cases:
    - iCloud Photo Library exports (often zipped)
    - Google Takeout archives
    - Photo backup archives

    Args:
        zip_path: Path to zip file
        extract_to: Destination directory (default: same dir as zip with '_extracted' suffix)

    Returns:
        Path: Directory where files were extracted

    Raises:
        FileNotFoundError: If zip file doesn't exist
        zipfile.BadZipFile: If file is not a valid zip archive
        PermissionError: If extraction directory isn't writable

    Example:
        >>> extract_dir = unzip_archive('~/Downloads/icloud_export.zip')
        >>> # Now use extract_dir as source for rename_and_organize()
    """
    zip_path = Path(zip_path).expanduser()

    if not zip_path.exists():
        raise FileNotFoundError(f"Zip file not found: {zip_path}")

    if not zipfile.is_zipfile(zip_path):
        raise zipfile.BadZipFile(f"Not a valid zip file: {zip_path}")

    # Default extraction directory: same name as zip without extension
    if extract_to is None:
        extract_to = zip_path.parent / f"{zip_path.stem}_extracted"
    else:
        extract_to = Path(extract_to).expanduser()

    # Create extraction directory
    extract_to.mkdir(parents=True, exist_ok=True)

    # Extract all files
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)

    return extract_to
