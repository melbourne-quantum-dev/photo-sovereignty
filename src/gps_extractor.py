# src/gps_extractor.py
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIC support
register_heif_opener()


def convert_to_degrees(dms_tuple):
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
        tuple: (latitude, longitude, altitude) or None if no GPS
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
        lat = convert_to_degrees(lat_dms)
        lon = convert_to_degrees(lon_dms)

        # Apply hemisphere corrections
        if lat_ref == "S":
            lat = -lat
        if lon_ref == "W":
            lon = -lon

        # Convert altitude to float
        if altitude is not None:
            altitude = float(altitude)

        return (lat, lon, altitude)

    except Exception as e:
        print(f"Error extracting GPS from {image_path}: {e}")
        return None


if __name__ == "__main__":
    # Test file path
    from config import load_config, get_path

    config = load_config()
    
    # Test file path
    image_path = get_path(config, "test_image")
    
    # Check if file exists
    print(f"File path: {image_path}")
    print(f"File exists: {image_path.exists()}")

    # Extract GPS
    if gps_coords := extract_gps_coords(image_path):
        lat, lon, alt = gps_coords
        print(f"✅ GPS found: ({lat:.6f}, {lon:.6f}, {alt}m)")
    else:
        print("❌ No GPS data in this image")

        # Debug: Check if image opens at all
        try:
            img = Image.open(image_path)
            print(f"✅ Image opens OK: {img.size}")

            # Debug: Check if EXIF exists
            if exif := img.getexif():
                print(f"✅ EXIF exists: {len(exif)} tags")
                # Debug: Check if GPS IFD (location) exists
                if gps_ifd := exif.get_ifd(34853):
                    print(f"✅ GPS IFD exists: {len(gps_ifd)} fields")
                else:
                    print("❌ No GPS IFD - image has no location data")
            else:
                print("❌ No EXIF data at all")
        except Exception as e:
            print(f"❌ Error opening image: {e}")
