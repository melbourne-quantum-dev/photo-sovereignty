# Test all 5 samples with detailed EXIF inspection
from pathlib import Path

from PIL import Image
from pillow_heif import register_heif_opener

# Register HEIC support
register_heif_opener()


def inspect_exif_datetime_tags(image_path):
    """Show all datetime-related EXIF tags."""
    img = Image.open(image_path)
    exif = img.getexif()

    datetime_tags = {
        306: "DateTime",
        36867: "DateTimeOriginal",
        36868: "DateTimeDigitized",
    }

    print(f"\n{Path(image_path).name}:")
    for tag_id, tag_name in datetime_tags.items():
        if tag_id in exif:
            print(f"  ✅ {tag_name} ({tag_id}): {exif[tag_id]}")
        else:
            print(f"  ❌ {tag_name} ({tag_id}): NOT PRESENT")

    # Also show camera info for context
    if 271 in exif:
        print(f"  Camera: {exif[271]} {exif.get(272, 'unknown model')}")


# Run on all samples
samples = [
    "data/sample_photos/IMG_2990.HEIC",
    "data/sample_photos/IMG_3382.HEIC",
    "data/sample_photos/IMG_3630.HEIC",
    "data/sample_photos/IMG_2944.JPEG",
    "data/sample_photos/IMG_2945.PNG",
]

for sample in samples:
    inspect_exif_datetime_tags(sample)
