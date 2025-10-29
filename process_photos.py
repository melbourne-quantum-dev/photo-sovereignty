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
    
    print(f"\n✅Processed {len(results)} images")
    print(f"✅ Organized into: {output_dir}")
    print(f"✅ Database: {db_path}")

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