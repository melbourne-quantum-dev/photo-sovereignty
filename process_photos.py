#!/usr/bin/env python3
"""
Process photos: Extract EXIF, organize files, store in database.

Usage:
    python process_photos.py --source ~/Pictures/test --output ~/Pictures/organized
"""

import argparse
from pathlib import Path
from src.exif_parser import rename_and_organize
from src.database import create_database, insert_image

def process_photos(source_dir, output_dir, db_path="photo_archive.db"):
    """Main processing pipeline."""
    
    print(f"Processing photos from: {source_dir}")
    print(f"Organizing to: {output_dir}")
    print(f"Database: {db_path}\n")
    
    # Create/connect to database
    conn = create_database(db_path)
    
    # Process and organize files
    results = rename_and_organize(source_dir, output_dir)
    
    # Insert into database
    for image_data in results:
        image_id = insert_image(conn, image_data)
        print(f"  DB ID {image_id}: {image_data['filename']}")
    
    conn.close()
    
    print(f"\n✅ Processed {len(results)} images")
    print(f"✅ Organized into: {output_dir}")
    print(f"✅ Database: {db_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process photo archive")
    parser.add_argument("--source", required=True, help="Source directory with photos")
    parser.add_argument("--output", required=True, help="Output directory for organized photos")
    parser.add_argument("--db", default="photo_archive.db", help="Database file path")
    
    args = parser.parse_args()
    
    process_photos(args.source, args.output, args.db)