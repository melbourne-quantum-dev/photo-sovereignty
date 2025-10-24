# src/exif_parser.py
from PIL import Image
from datetime import datetime
from pathlib import Path
from pillow_heif import register_heif_opener

# Register HEIC support
register_heif_opener()

def extract_exif_date(image_path):
    """Extract best available date from image.
    
    iPhone USB extraction: DateTime (306) is capture time.
    
    Returns: tuple (datetime, source_type)
    """
    try:
        img = Image.open(image_path)
        exif = img.getexif()
        
        if exif:
            # Priority 1: DateTimeOriginal (standard cameras)
            if 36867 in exif:
                date_str = exif[36867]
                dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                return (dt, 'exif_original')
            
            # Priority 2: DateTime (iPhone USB extraction stores here)
            if 306 in exif:
                date_str = exif[306]
                dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                
                # Check if camera metadata present
                make = exif.get(271)
                if make:  # Has camera info = reliable capture time
                    return (dt, 'exif_datetime_camera')
                else:
                    return (dt, 'exif_datetime_unknown')
        
        # Fallback: File system mtime
        path = Path(image_path)
        mtime = path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime)
        return (dt, 'filesystem')
        
    except Exception as e:
        print(f"Error reading {image_path}: {e}")
        return (None, None)


def extract_camera_info(image_path):
    """Extract camera make and model.
    
    Returns dict with 'make' and 'model' keys.
    """
    try:
        img = Image.open(image_path)
        exif = img.getexif()
        
        if not exif:
            return {"make": None, "model": None}
            
        return {
            "make": exif.get(271),   # Make
            "model": exif.get(272)   # Model
        }
        
    except Exception as e:
        print(f"Error reading {image_path}: {e}")
        return {"make": None, "model": None}


def generate_organized_path(date, source_type, original_filename):
    """Generate organized file path: YYYY/YYYY-MM-DD_HHMMSS.ext
    
    Args:
        date: datetime object
        source_type: 'exif_datetime_camera', 'filesystem', etc.
        original_filename: 'IMG_3630.HEIC'
    
    Returns: Path object like '2025/2025-06-02_001524.heic'
    """
    if date is None:
        # Fallback: keep original structure for problem files
        return Path("unsorted") / original_filename
    
    # Extract extension (convert to lowercase)
    ext = Path(original_filename).suffix.lower()
    
    # Generate timestamp filename
    year = date.strftime("%Y")
    timestamp = date.strftime("%Y-%m-%d_%H%M%S")
    
    # Add quality marker for non-camera sources
    if source_type in ['filesystem', 'exif_datetime_unknown']:
        filename = f"{timestamp}_{source_type}{ext}"
    else:
        filename = f"{timestamp}{ext}"
    
    return Path(year) / filename


def rename_and_organize(source_dir, dest_dir):
    """Process all images in source_dir, organize into dest_dir.
    
    Returns: list of tuples (original_path, new_path, metadata)
    """
    source = Path(source_dir)
    dest = Path(dest_dir)
    
    # Supported formats
    patterns = ['*.heic', '*.HEIC', '*.jpg', '*.JPG', '*.jpeg', '*.JPEG', '*.png', '*.PNG']
    
    results = []
    
    for pattern in patterns:
        for img_path in source.glob(pattern):
            # Extract metadata
            date, source_type = extract_exif_date(img_path)
            camera = extract_camera_info(img_path)
            
            # Generate organized path
            rel_path = generate_organized_path(date, source_type, img_path.name)
            new_path = dest / rel_path
            
            # Create directory if needed
            new_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file (don't delete original yet - safety)
            import shutil
            shutil.copy2(img_path, new_path)
            
            # Store result
            results.append({
                'original_path': str(img_path),
                'organized_path': str(new_path),
                'filename': new_path.name,
                'date_taken': date,
                'date_source': source_type,
                'camera_make': camera['make'],
                'camera_model': camera['model']
            })
            
            print(f"✅ {img_path.name} → {rel_path}")
    
    return results

if __name__ == "__main__":
    # Test organization logic (dry run - copies to test output)
    results = rename_and_organize(
        "data/sample_photos",
        "data/organized_test"
    )
    
    print(f"\nProcessed {len(results)} images")
    for r in results:
        print(f"{r['filename']}: {r['date_source']}")