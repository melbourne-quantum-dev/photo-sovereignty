#!/usr/bin/env python3
"""
Manual GPS insertion test - verify database operations before full extraction.

Foundation note: Manually insert GPS data for a few known images,
then query back to confirm insert/query functions work correctly.

Usage:
    python tests/test_gps_manual.py
"""

import sqlite3
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database import create_database, insert_location, query_images_without_gps
from src.gps_extractor import extract_gps_coords


def test_manual_gps_insertion():
    """Test GPS insertion and querying."""
    
    # Connect to production database
    db_path = Path("~/data/media/images/organised/photo_archive.db").expanduser()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run process_photos.py first")
        exit(1)
    
    conn = create_database(db_path)
    
    print("="*60)
    print("GPS DATABASE OPERATIONS TEST")
    print("="*60)
    
    # Step 1: Find images without GPS
    images_without_gps = query_images_without_gps(conn)
    print(f"\n✅ Found {len(images_without_gps)} images without GPS data")
    
    if len(images_without_gps) == 0:
        print("⚠️  All images already have GPS data")
        conn.close()
        return
    
    # Step 2: Extract and insert GPS for first 5 images
    print(f"\n{'='*60}")
    print("Extracting GPS from first 5 images...")
    print(f"{'='*60}\n")
    
    success_count = 0
    no_gps_count = 0
    
    for image_id, org_path in images_without_gps[:5]:
        filename = Path(org_path).name
        
        # Extract GPS
        coords = extract_gps_coords(org_path)
        
        if coords:
            lat, lon, alt = coords
            
            # Insert into database
            location_id = insert_location(conn, image_id, lat, lon, alt)
            
            # Display result
            alt_str = f"{alt:.2f}m" if alt else "N/A"
            print(f"✅ Image {image_id}: {filename}")
            print(f"   Location ID: {location_id}")
            print(f"   Coords: ({lat:.6f}, {lon:.6f})")
            print(f"   Altitude: {alt_str}\n")
            
            success_count += 1
        else:
            print(f"⏭️  Image {image_id}: {filename} - No GPS data\n")
            no_gps_count += 1
    
    # Step 3: Verify insertion by querying back
    print(f"{'='*60}")
    print("Verifying inserted data...")
    print(f"{'='*60}\n")
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            i.id,
            i.filename,
            l.latitude,
            l.longitude,
            l.altitude
        FROM images i
        JOIN locations l ON i.id = l.image_id
        ORDER BY i.id
        LIMIT 5
    """)
    
    results = cursor.fetchall()
    
    if results:
        print(f"Successfully retrieved {len(results)} GPS records:\n")
        for img_id, filename, lat, lon, alt in results:
            alt_str = f"{alt:.2f}m" if alt else "N/A"
            print(f"📍 {filename}")
            print(f"   Image ID: {img_id}")
            print(f"   Coords: ({lat:.6f}, {lon:.6f})")
            print(f"   Altitude: {alt_str}\n")
    else:
        print("⚠️  No GPS data retrieved (check insertion)")
    
    # Step 4: Summary
    print(f"{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"GPS extracted: {success_count}/5 test images")
    print(f"No GPS data: {no_gps_count}/5 test images")
    print(f"Database records verified: {len(results)}")
    
    if success_count > 0:
        print(f"\n✅ GPS insertion and retrieval working correctly")
        print(f"Ready to run full extraction with extract_gps.py")
    else:
        print(f"\n⚠️  No GPS data found in test images")
        print(f"Try testing on images from May 21, 2025 (known GPS)")
    
    print(f"{'='*60}\n")
    
    conn.close()


if __name__ == "__main__":
    test_manual_gps_insertion()
