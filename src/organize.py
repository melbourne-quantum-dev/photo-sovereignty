# src/organize.py
"""File organization and archive extraction utilities.

This module handles:
- Generating organized file paths based on dates
- Organizing media (images and videos) from source to destination directories
- Extracting media from zip archives (iCloud exports, etc.)

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
    - Pure timestamp screenshots (Screenshot 2025-07-06 121830)
    - Date-only filenames (2023-12-15_143022)

    Descriptive patterns (preserved):
    - Screenshots with context (Screenshot 2025-03-29 at 18-38-44 Open Deep-Research...)
    - Date + description (2025-09-02 200936 holy grasp of undying zed)
    - Partial dates in context (birthday-2023, vacation-dec-2024)

    Args:
        stem: Filename without extension

    Returns:
        True if filename appears descriptive/meaningful
    """
    import re

    # Pure camera/auto-generated patterns (NO additional descriptive content)
    camera_patterns = [
        r"^IMG_\d+$",  # IMG_1234
        r"^DSC[N]?\d+$",  # DSC01234, DSCN1234
        r"^\d{8}_\d{6}$",  # 20231215_143022 (pure timestamp)
        r"^\d{4}-\d{2}-\d{2}_\d{6}$",  # 2023-12-15_143022 (already organized)
        r"^IMG-\d+",  # IMG-20231215-WA0001
        r"^PXL_",  # Pixel phone format (PXL_20231215_143022)
        r"^Screenshot \d{4}-\d{2}-\d{2}(( at)? \d{2}[:-]?\d{2}[:-]?\d{2})?$",  # Screenshot 2025-07-06 121830 or at 12:18:30 (no description)
        r"^Screenshot_\d+$",  # Screenshot_20231215
        r"^\d{4}-\d{2}-\d{2} \d{6}$",  # 2025-09-02 200936 (pure timestamp, no description)
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",  # iCloud UUID exports
    ]

    return not any(
        re.match(pattern, stem, re.IGNORECASE) for pattern in camera_patterns
    )


def _extract_description_from_timestamped_name(stem: str) -> str | None:
    """Extract description from filename that already has a timestamp prefix.

    Handles patterns like:
    - '2025-09-02 200936 holy grasp of undying zed' → 'holy grasp of undying zed'
    - '2025-01-22_121254 vacation photos' → 'vacation photos'
    - 'Screenshot 2025-03-29 at 18-38-44 Open Deep-Research' → 'Open Deep-Research'
    - '20231215_143022 family dinner' → 'family dinner'

    Args:
        stem: Filename without extension

    Returns:
        Description text if found, None if filename is pure timestamp or no timestamp
    """
    import re

    # Patterns that match timestamp prefixes with potential descriptions
    # Each pattern has a capture group for the description part
    timestamp_patterns = [
        # YYYY-MM-DD HHMMSS description
        r"^\d{4}-\d{2}-\d{2}\s+\d{6}\s+(.+)$",
        # YYYY-MM-DD_HHMMSS description
        r"^\d{4}-\d{2}-\d{2}_\d{6}\s+(.+)$",
        # YYYYMMDD_HHMMSS description
        r"^\d{8}_\d{6}\s+(.+)$",
        # Screenshot YYYY-MM-DD at HH-MM-SS description
        r"^Screenshot\s+\d{4}-\d{2}-\d{2}\s+at\s+\d{2}-\d{2}-\d{2}\s+(.+)$",
        # Screenshot YYYY-MM-DD HHMMSS description
        r"^Screenshot\s+\d{4}-\d{2}-\d{2}\s+\d{6}\s+(.+)$",
    ]

    for pattern in timestamp_patterns:
        match = re.match(pattern, stem, re.IGNORECASE)
        if match:
            description = match.group(1).strip()
            # Only return if there's actual descriptive content
            if description:
                return description

    return None


def generate_organized_path(
    date,
    source_type,
    original_filename,
    preserve_filenames: str | bool = "descriptive_only",
    media_type: str = "image",
):
    """Generate organized file path with optional filename preservation.

    Organization strategy:
    - Media split: images/ and videos/ directories
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
        media_type: 'image' or 'video' (determines top-level directory)

    Returns:
        Path object like:
        - 'photos/2025/2025-06-02_001524.heic' (EXIF, camera name)
        - 'photos/2023/2023-06-15_143022_wedding-reception.jpg' (EXIF, descriptive)
        - 'videos/2020/2020-03-15_143530.mov'
        - 'photos/filesystem_dates/2025-11-23_095802_piazza-dei-signori.jpg'
        - 'videos/unsorted/corrupted-file.mov'
    """
    # Extract original stem (without extension) and extension
    original_path = Path(original_filename)
    ext = original_path.suffix.lower()
    original_stem = original_path.stem

    # Determine media subdirectory (photos/ or videos/)
    media_dir = "photos" if media_type == "image" else "videos"

    # Case 1: No date at all (corrupted/unreadable)
    if date is None:
        return Path(media_dir) / "unsorted" / original_filename

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
        # Check if original filename already has a timestamp prefix
        # If so, extract just the description to avoid double timestamps
        description = _extract_description_from_timestamped_name(original_stem)
        if description:
            # Normalize description: replace spaces with hyphens for consistency
            normalized_desc = description.replace(" ", "-")
            filename = f"{timestamp}_{normalized_desc}{ext}"
        else:
            # No timestamp prefix detected, use full original stem
            # Also normalize spaces to hyphens
            normalized_stem = original_stem.replace(" ", "-")
            filename = f"{timestamp}_{normalized_stem}{ext}"
    else:
        filename = f"{timestamp}{ext}"

    # Case 2: Filesystem date (unreliable - needs manual review)
    if source_type in ["filesystem", "exif_datetime_unknown"]:
        return Path(media_dir) / "filesystem_dates" / filename

    # Case 3: Reliable date (EXIF or filename timestamp)
    year = date.strftime("%Y")
    return Path(media_dir) / year / filename


def rename_and_organize(
    source_dir, dest_dir, preserve_filenames="descriptive_only", recursive=False
):
    """Process all images and videos in source_dir, organize into dest_dir.

    This is a pure data processing function - no user output.
    Orchestration layer handles progress reporting.

    Media organization:
    - Images → photos/ subdirectory (organized by date)
    - Videos → videos/ subdirectory (organized by date)

    Args:
        source_dir: Source directory with images and videos
        dest_dir: Destination directory for organized media
        preserve_filenames: Filename preservation strategy:
            - 'descriptive_only': Preserve only non-camera names (default)
            - True: Always preserve original name
            - False: Never preserve (timestamp only)
        recursive: Process subdirectories recursively (default: False)
            - True: Recursively process all subdirectories (useful for multi-part iCloud exports)
            - False: Only process files in immediate directory (safer default)

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
        "*.webp",
        "*.WEBP",
    ]

    video_patterns = [
        "*.mov",
        "*.MOV",
        "*.mp4",
        "*.MP4",
        "*.avi",
        "*.AVI",
        "*.mkv",
        "*.MKV",
    ]

    # Store results
    results = []

    # Get file iterator based on recursive flag
    if recursive:
        # Recursively find all files
        file_iterator = source.rglob("*")
    else:
        # Only immediate directory
        file_iterator = source.iterdir()

    # Process all files
    for file_path in file_iterator:
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()

        # Check if supported media type
        is_image = any(file_path.match(pattern) for pattern in image_patterns)
        is_video = any(file_path.match(pattern) for pattern in video_patterns)

        if is_image or is_video:
            # Determine media type
            media_type = "image" if is_image else "video"
            # Extract metadata
            date, source_type = extract_exif_date(file_path)
            camera = extract_camera_info(file_path)

            # Generate organized path
            rel_path = generate_organized_path(
                date, source_type, file_path.name, preserve_filenames, media_type
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
                    "file_type": media_type,  # 'image' or 'video'
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
    """Extract media from zip archive (iCloud exports, photo backups, etc.).

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
