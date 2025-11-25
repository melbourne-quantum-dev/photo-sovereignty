# src/exif_parser.py
"""EXIF metadata extraction from image files.

This module handles:
- Date extraction from EXIF metadata
- Camera information extraction
- Support for HEIC, JPEG, and PNG formats

Separation of concerns:
- Pure extraction logic - no file organization
- No user-facing output - returns data or None
- Orchestration layer handles progress reporting and error messages
"""

import re
from datetime import datetime
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIC support
register_heif_opener()


def extract_date_from_filename(filename: str) -> tuple[datetime | None, str | None]:
    """Parse date from filename patterns.

    Common patterns:
    - Screenshots: 'Screenshot 2025-07-06 121830', 'Screenshot 2025-03-29 at 18-38-44'
    - Computer-generated: '2025-09-02 200936', '20231215_143022'
    - Screen recordings: 'Screen Recording 2024-01-15 at 14.30.25'

    Args:
        filename: Filename (with or without extension)

    Returns:
        tuple: (datetime, source_description) or (None, None) if no pattern matched
        source_description helps identify which pattern was used
    """
    # Remove extension if present
    stem = Path(filename).stem

    # Pattern: YYYY-MM-DD HHMMSS (with spaces)
    # Example: "2025-09-02 200936" or "2025-09-02 200936 description"
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})\s+(\d{6})", stem)
    if match:
        year, month, day, time = match.groups()
        hour = time[0:2]
        minute = time[2:4]
        second = time[4:6]
        try:
            dt = datetime(
                int(year), int(month), int(day), int(hour), int(minute), int(second)
            )
            return (dt, "filename_timestamp")
        except ValueError:
            pass

    # Pattern: Screenshot YYYY-MM-DD at HH-MM-SS
    # Example: "Screenshot 2025-03-29 at 18-38-44"
    match = re.search(
        r"Screenshot\s+(\d{4})-(\d{2})-(\d{2})\s+at\s+(\d{2})-(\d{2})-(\d{2})",
        stem,
        re.IGNORECASE,
    )
    if match:
        year, month, day, hour, minute, second = match.groups()
        try:
            dt = datetime(
                int(year), int(month), int(day), int(hour), int(minute), int(second)
            )
            return (dt, "filename_timestamp")
        except ValueError:
            pass

    # Pattern: Screenshot YYYY-MM-DD HHMMSS (no 'at')
    # Example: "Screenshot 2025-07-06 121830"
    match = re.search(
        r"Screenshot\s+(\d{4})-(\d{2})-(\d{2})\s+(\d{6})", stem, re.IGNORECASE
    )
    if match:
        year, month, day, time = match.groups()
        hour = time[0:2]
        minute = time[2:4]
        second = time[4:6]
        try:
            dt = datetime(
                int(year), int(month), int(day), int(hour), int(minute), int(second)
            )
            return (dt, "filename_timestamp")
        except ValueError:
            pass

    # Pattern: YYYYMMDD_HHMMSS
    # Example: "20231215_143022"
    match = re.search(r"(\d{8})_(\d{6})", stem)
    if match:
        date_part, time_part = match.groups()
        year = date_part[0:4]
        month = date_part[4:6]
        day = date_part[6:8]
        hour = time_part[0:2]
        minute = time_part[2:4]
        second = time_part[4:6]
        try:
            dt = datetime(
                int(year), int(month), int(day), int(hour), int(minute), int(second)
            )
            return (dt, "filename_timestamp")
        except ValueError:
            pass

    return (None, None)


def extract_exif_date(image_path):
    """Extract best available date from image.

    Date extraction hierarchy:
    1. EXIF DateTimeOriginal (most reliable - from camera)
    2. EXIF DateTime (reliable if camera make present)
    3. Filename timestamp (screenshots, screen recordings)
    4. Filesystem mtime (least reliable - last modified)

    Args:
        image_path: Path to image file (str or Path)

    Returns:
        tuple: (datetime, source_type) or (None, None) on error

    Source types:
        - 'exif_original': EXIF DateTimeOriginal tag (36867)
        - 'exif_datetime_camera': EXIF DateTime tag (306) with camera make
        - 'exif_datetime_unknown': EXIF DateTime tag without camera info
        - 'filename_timestamp': Date parsed from filename (screenshots, etc.)
        - 'filesystem': File modification time (fallback)
    """
    try:
        img = Image.open(image_path)
        exif = img.getexif()

        if exif:
            # Priority 1: DateTimeOriginal (standard cameras)
            if 36867 in exif:
                date_str = exif[36867]
                dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                return (dt, "exif_original")

            # Priority 2: DateTime (iPhone USB extraction stores here)
            if 306 in exif:
                date_str = exif[306]
                dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")

                # Check if camera metadata present
                make = exif.get(271)
                if make:  # Has camera info = reliable capture time
                    return (dt, "exif_datetime_camera")
                else:
                    return (dt, "exif_datetime_unknown")

        # Priority 3: Try parsing date from filename
        path = Path(image_path)
        filename_date, source = extract_date_from_filename(path.name)
        if filename_date:
            return (filename_date, source)

        # Priority 4: Fallback to filesystem mtime
        mtime = path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime)
        return (dt, "filesystem")

    except Exception:
        # Return None on any error - orchestration handles logging
        return (None, None)


def extract_camera_info(image_path):
    """Extract camera make and model.

    Args:
        image_path: Path to image file (str or Path)

    Returns:
        dict: {'make': str or None, 'model': str or None}
              Returns None values on error or if no EXIF data present
    """
    try:
        img = Image.open(image_path)
        exif = img.getexif()

        if not exif:
            return {"make": None, "model": None}

        return {
            "make": exif.get(271),  # Make
            "model": exif.get(272),  # Model
        }

    except Exception:
        # Return None values on any error - orchestration handles logging
        return {"make": None, "model": None}
