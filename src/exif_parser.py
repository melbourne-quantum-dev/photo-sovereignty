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

from datetime import datetime
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIC support
register_heif_opener()


def extract_exif_date(image_path):
    """Extract best available date from image.

    iPhone USB extraction: DateTime (306) is capture time.

    Args:
        image_path: Path to image file (str or Path)

    Returns:
        tuple: (datetime, source_type) or (None, None) on error

    Source types:
        - 'exif_original': EXIF DateTimeOriginal tag (36867)
        - 'exif_datetime_camera': EXIF DateTime tag (306) with camera make
        - 'exif_datetime_unknown': EXIF DateTime tag without camera info
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

        # Fallback: File system mtime
        path = Path(image_path)
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
