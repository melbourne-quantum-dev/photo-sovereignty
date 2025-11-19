#!/usr/bin/env python3
"""
Process photos: Extract EXIF, organize files, store in database.

Usage:
    # Use config.yaml paths (recommended)
    python process_photos.py
    
    # Override specific paths
    python process_photos.py --source ~/Downloads/photos --db test.db
    
    # Use custom config file
    python process_photos.py --config production.yaml
"""

import argparse
from pathlib import Path
from src.exif_parser import rename_and_organize
from src.database import create_database, insert_image

def process_photos(source_dir, output_dir, db_path="photo_archive.db"):
    """Main processing pipeline with duplicate checking.
    
    Foundation note: Idempotent processing enables:
    - Safe re-runs after interruptions
    - Adding new photos without reprocessing existing
    - Database recovery scenarios
    """
    print(f"\n{'='*60}")
    print("PROCESSING PHOTOS")
    print(f"{'='*60}")
    print(f"Processing photos from: {source_dir}")
    print(f"Organizing to: {output_dir}")
    print(f"Database: {db_path}\n")
    
    # Create/connect to database
    conn = create_database(db_path)
    
    # Check what's already been processed
    cursor = conn.cursor()
    cursor.execute("SELECT original_path FROM images")
    already_processed = {row[0] for row in cursor.fetchall()}
    
    print(f"📊 Database contains {len(already_processed)} processed images\n")
    
    # Process and organize files
    # Note: Printing currently in exif_parser.py (layer separation fix deferred to Week 6)
    results = rename_and_organize(source_dir, output_dir)
    
    # Insert only new images
    new_count = 0
    skip_count = 0
    MAX_SKIP_DISPLAY = 5  # Show first 5 skips, then summarize
    
    for image_data in results:
        # Check if already in database
        if image_data['original_path'] in already_processed:
            skip_count += 1
            
            # Show first few skips, then summarize rest
            if skip_count <= MAX_SKIP_DISPLAY:
                print(f"  ⏭️  Skip: {image_data['filename']}")
            elif skip_count == MAX_SKIP_DISPLAY + 1:
                remaining = len(results) - new_count - MAX_SKIP_DISPLAY
                print(f"  ⏭️  ... and {remaining} more skipped")
            
            continue
        
        # Insert new image
        image_id = insert_image(conn, image_data)
        new_count += 1
        print(f"  ✅ DB ID {image_id}: {image_data['filename']}")
    
    conn.close()
    
    # Summary
    print(f"\n{'='*60}")
    print("Processing Complete")
    print(f"{'='*60}")
    print(f"✅ New images: {new_count}")
    if skip_count > 0:
        print(f"⏭️  Skipped (already processed): {skip_count}")
    print(f"📊 Total in database: {len(already_processed) + new_count}")
    
    if new_count > 0:
        print(f"📁 Organized into: {output_dir}")
        print(f"🗄️  Database: {db_path}")
    else:
        print("⚠️  No new images processed")
    print(f"{'='*60}")


if __name__ == "__main__":
    """CLI entry point for photo processing.
    
    Configuration Loading:
        Loads paths from config.yaml by default. CLI arguments override config values.
        This enables privacy-preserving development (config.yaml gitignored) while
        maintaining flexible CLI interface for testing/debugging.
    
    Examples:
        # Use config.yaml paths (recommended)
        python process_photos.py
        
        # Override specific paths
        python process_photos.py --source ~/Downloads/photos --db test.db
        
        # Use custom config file
        python process_photos.py --config production.yaml
    """
    from src.config import load_config
    
    parser = argparse.ArgumentParser(
        description="Process photo archive: Extract EXIF, organize files, store metadata",
        epilog="""
        Privacy Note: Paths loaded from config.yaml (gitignored).
        CLI arguments override config values when provided.
        """
    )
    
    # Config file selection
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    
    # Path overrides (optional - use config if not provided)
    parser.add_argument(
        "--source",
        help="Source directory with photos (overrides config)"
    )
    parser.add_argument(
        "--output",
        help="Output directory for organized photos (overrides config)"
    )
    parser.add_argument(
        "--db",
        help="Database file path (overrides config)"
    )
    
    args = parser.parse_args()
    
    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        exit(1)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        exit(1)
    
    # Use CLI args if provided, otherwise use config
    source_dir = args.source if args.source else config['paths']['input_directory']
    output_dir = args.output if args.output else config['paths']['output_directory']
    db_path = args.db if args.db else config['paths']['database']
    
    # Expand paths if provided via CLI
    if args.source:
        source_dir = Path(source_dir).expanduser()
    if args.output:
        output_dir = Path(output_dir).expanduser()
    if args.db:
        db_path = Path(db_path).expanduser()
    
    # Validate source directory exists
    if not source_dir.exists():
        print(f"❌ Source directory not found: {source_dir}")
        exit(1)
    
    # Run processing
    process_photos(str(source_dir), str(output_dir), str(db_path))
