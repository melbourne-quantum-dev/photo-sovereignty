# src/exif_extractor.py
"""EXIF metadata extraction from image files.

This module handles all EXIF-related operations:
- Date extraction from EXIF metadata and filenames
- Camera information extraction (make, model)
- GPS coordinates extraction
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

# Register HEIC support (single registration for entire module)
register_heif_opener()


# ============================================================================
# Date Extraction
# ============================================================================


def extract_date_from_filename(filename: str) -> tuple[datetime | None, str | None]:
    """Parse date from filename patterns.

    Common patterns:
    - Screenshots: 'Screenshot 2025-07-06 121830', 'Screenshot 2025-03-29 at 18-38-44'
    - Screenshot variations: 'Screenshot-2022-06-07-at-10.42.24-am', 'Screenshot_2022-01-22-09-13-25'
    - Computer-generated: '2025-09-02 200936', '20231215_143022'
    - Manual timestamps: '250710_1519', 'yeahnahallgood_250710_1519'
    - Screen recordings: 'Screen Recording 2024-01-15 at 14.30.25'

    Args:
        filename: Filename (with or without extension)

    Returns:
        tuple: (datetime, source_description) or (None, None) if no pattern matched
        source_description helps identify which pattern was used
    """
    # Remove extension if present
    stem = Path(filename).stem

    # Pattern: Screenshot with flexible separators and time formats
    # Matches: Screenshot-2022-06-07-at-10.42.24-am, Screenshot_2022-01-22-09-13-25-999
    # Matches: Screenshot-from-2025-03-18-02-57-03, Screenshot 2025-04-09 at 12.35.28 pm
    # Flexible: separators (space/-/_), preposition (at/from before or between), time separators (.-:-)
    match = re.search(
        r"Screenshot[\s\-_]+(?:from[\s\-_]+)?(\d{4})-(\d{2})-(\d{2})[\s\-_]+(?:at[\s\-_]+)?(\d{2})[\.\-:](\d{2})[\.\-:](\d{2})",
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

    # Pattern: YYMMDD_HHMM (manual date embedding)
    # Example: "yeahnahallgood_doormat_w1nst0n_250710_1519.png" → 2025-07-10 15:19:00
    # Example: "250710_1519_description.png" → 2025-07-10 15:19:00
    # Can appear at beginning, middle, or end of filename
    match = re.search(r"(\d{2})(\d{2})(\d{2})_(\d{2})(\d{2})", stem)
    if match:
        yy, mm, dd, hh, mn = match.groups()
        # Assume 21st century (2000-2099)
        year = 2000 + int(yy)
        try:
            dt = datetime(year, int(mm), int(dd), int(hh), int(mn), 0)
            return (dt, "filename_timestamp")
        except ValueError:
            pass

    return (None, None)


def extract_exif_date(image_path, photo_details: dict | None = None):
    """Extract best available date from image.

    Date extraction hierarchy:
    1. EXIF DateTimeOriginal (most reliable - from camera)
    2. EXIF DateTime (reliable if camera make present)
    3. Photo Details originalCreationDate (iCloud's canonical date)
    4. Filename timestamp (screenshots, screen recordings, manual timestamps)
    5. Filesystem mtime (least reliable - last modified)

    Args:
        image_path: Path to image file (str or Path)
        photo_details: Optional dict from photo_details_parser.load_photo_details()
                      Maps filename to {'date': datetime, 'checksum': str}

    Returns:
        tuple: (datetime, source_type) or (None, None) on error

    Source types:
        - 'exif_original': EXIF DateTimeOriginal tag (36867)
        - 'exif_datetime_camera': EXIF DateTime tag (306) with camera make
        - 'exif_datetime_unknown': EXIF DateTime tag without camera info
        - 'photo_details': iCloud Photo Details originalCreationDate
        - 'filename_timestamp': Date parsed from filename (screenshots, etc.)
        - 'filesystem': File modification time (fallback)
    """
    # Try EXIF extraction first (works for photos, fails for videos)
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
    except Exception:
        # PIL cannot open videos - expected, continue to fallback methods
        pass

    # Priority 3: Try Photo Details if provided (iCloud's canonical metadata)
    if photo_details:
        path = Path(image_path)
        filename = path.name
        if filename in photo_details:
            date = photo_details[filename].get("date")
            if date:
                return (date, "photo_details")

    # Priority 4: Try parsing date from filename (works for photos and videos)
    try:
        path = Path(image_path)
        filename_date, source = extract_date_from_filename(path.name)
        if filename_date:
            return (filename_date, source)
    except Exception:
        pass

    # Priority 5: Fallback to filesystem mtime (always works)
    try:
        path = Path(image_path)
        mtime = path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime)
        return (dt, "filesystem")
    except Exception:
        # Only return None if filesystem access also fails
        return (None, None)


# ============================================================================
# Camera Information
# ============================================================================


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


# ============================================================================
# GPS Coordinates
# ============================================================================


def _convert_to_degrees(dms_tuple):
    """Convert GPS DMS (degrees, minutes, seconds) to decimal degrees.

    Args:
        dms_tuple: (degrees, minutes, seconds) - e.g., (37, 50, 4.8)

    Returns:
        float: Decimal degrees - e.g., -37.834670
    """
    degrees, minutes, seconds = dms_tuple
    return degrees + (minutes / 60.0) + (seconds / 3600.0)


def extract_gps_coords(image_path):
    """Extract GPS coordinates from image EXIF data.

    Args:
        image_path: Path to image file

    Returns:
        tuple: (latitude, longitude, altitude) or None if no GPS data

    Note:
        Returns None silently on errors (no print statements) - consistent with
        other extraction functions. Orchestration layer handles logging.
    """
    try:
        img = Image.open(image_path)
        exif = img.getexif()

        if not exif:
            return None

        gps_ifd = exif.get_ifd(34853)

        if not gps_ifd:
            return None

        # Extract components
        lat_dms = gps_ifd.get(2)
        lat_ref = gps_ifd.get(1)
        lon_dms = gps_ifd.get(4)
        lon_ref = gps_ifd.get(3)
        altitude = gps_ifd.get(6)

        if not (lat_dms and lon_dms):
            return None

        # Convert to decimal
        lat = _convert_to_degrees(lat_dms)
        lon = _convert_to_degrees(lon_dms)

        # Apply hemisphere corrections
        if lat_ref == "S":
            lat = -lat
        if lon_ref == "W":
            lon = -lon

        # Convert altitude to float (SQLite compatibility)
        if altitude is not None:
            altitude = float(altitude)

        return (lat, lon, altitude)

    except Exception:
        # Return None silently - no print statements
        return None
