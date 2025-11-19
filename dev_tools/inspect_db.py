#!/usr/bin/env python3
"""Database inspection utility for photo sovereignty pipeline.

Interactive tool for querying and validating database contents during development.
Consolidates functionality from legacy query scripts with improved interface.

Usage:
    # Use config.yaml database path
    python dev_tools/inspect_db.py

    # Specify database path
    python dev_tools/inspect_db.py --db ~/data/photo_archive.db

    # Run specific query
    python dev_tools/inspect_db.py --query gps_coverage

    # Available queries:
    #   schema       - Show database schema
    #   all_images   - List all images
    #   gps_coverage - GPS extraction statistics
    #   date_sources - Breakdown by date source quality
    #   cameras      - Photos grouped by camera
    #   gps_sample   - Sample of GPS data
    #   coord_ranges - Geographic bounds of photos
    #   missing_gps  - Images without GPS data

Author: Leonardo
Date: 2025-11-19
Version: v0.1.0 (consolidated from query_database.py + query_gps.py)
"""

import argparse
import sqlite3
import sys
from pathlib import Path
from typing import Optional

# Add src to path for config loading
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import get_path, load_config


def connect_db(db_path: Path) -> sqlite3.Connection:
    """Connect to SQLite database."""
    if not db_path.exists():
        raise FileNotFoundError(
            f"Database not found: {db_path}\n"
            f"Run examples/stage1_process_photos.py first to create database."
        )
    return sqlite3.connect(db_path)


def show_schema(conn: sqlite3.Connection):
    """Display database schema."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, sql FROM sqlite_master
        WHERE type='table'
        ORDER BY name
    """)

    print(f"\n{'=' * 80}")
    print("DATABASE SCHEMA")
    print(f"{'=' * 80}\n")

    for table_name, sql in cursor.fetchall():
        print(f"Table: {table_name}")
        print(f"{'-' * 80}")
        print(sql)
        print()


def show_all_images(conn: sqlite3.Connection, limit: int = 20):
    """Display all images in database."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM images")
    total = cursor.fetchone()[0]

    cursor.execute(f"""
        SELECT id, filename, date_taken, date_source, camera_make, camera_model
        FROM images
        ORDER BY date_taken DESC
        LIMIT {limit}
    """)

    print(f"\n{'=' * 80}")
    print(f"ALL IMAGES (showing {limit} of {total})")
    print(f"{'=' * 80}\n")

    for row in cursor.fetchall():
        img_id, filename, date, source, make, model = row
        camera = f"{make} {model}" if make else "No camera metadata"
        print(f"ID {img_id}: {filename}")
        print(f"  Date: {date} (source: {source})")
        print(f"  Camera: {camera}\n")


def show_gps_coverage(conn: sqlite3.Connection):
    """Show GPS coverage statistics."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM images")
    total_images = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM locations")
    gps_images = cursor.fetchone()[0]

    coverage = (gps_images / total_images * 100) if total_images > 0 else 0

    print(f"\n{'=' * 80}")
    print("GPS COVERAGE STATISTICS")
    print(f"{'=' * 80}")
    print(f"Total images: {total_images}")
    print(f"Images with GPS: {gps_images} ({coverage:.1f}%)")
    print(f"Images without GPS: {total_images - gps_images}")
    print(f"{'=' * 80}\n")


def show_date_sources(conn: sqlite3.Connection):
    """Group images by date source quality."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date_source, COUNT(*) as count
        FROM images
        GROUP BY date_source
        ORDER BY count DESC
    """)

    print(f"\n{'=' * 80}")
    print("DATE SOURCE BREAKDOWN")
    print(f"{'=' * 80}")

    for source, count in cursor.fetchall():
        print(f"  {source}: {count} images")

    print(f"{'=' * 80}\n")


def show_cameras(conn: sqlite3.Connection):
    """Show photos by camera."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            camera_make,
            camera_model,
            COUNT(*) as count
        FROM images
        GROUP BY camera_make, camera_model
        ORDER BY count DESC
    """)

    print(f"\n{'=' * 80}")
    print("CAMERA BREAKDOWN")
    print(f"{'=' * 80}")

    for make, model, count in cursor.fetchall():
        if make:
            print(f"  {make} {model}: {count} images")
        else:
            print(f"  No camera metadata: {count} images")

    print(f"{'=' * 80}\n")


def show_gps_sample(conn: sqlite3.Connection, limit: int = 10):
    """Show sample of images with GPS data."""
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            i.filename,
            i.date_taken,
            l.latitude,
            l.longitude,
            l.altitude
        FROM images i
        JOIN locations l ON i.id = l.image_id
        ORDER BY i.date_taken DESC
        LIMIT ?
    """,
        (limit,),
    )

    results = cursor.fetchall()

    print(f"\n{'=' * 80}")
    print(f"GPS DATA SAMPLE (showing {limit} most recent)")
    print(f"{'=' * 80}\n")

    if not results:
        print("No GPS data found in database\n")
        return

    for filename, date, lat, lon, alt in results:
        alt_str = f"{alt:.2f}m" if alt else "N/A"
        print(f"📍 {filename}")
        print(f"   Date: {date}")
        print(f"   Coords: ({lat:.6f}, {lon:.6f})")
        print(f"   Altitude: {alt_str}\n")


def show_coord_ranges(conn: sqlite3.Connection):
    """Show geographic range of photos."""
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            MIN(latitude) as min_lat,
            MAX(latitude) as max_lat,
            MIN(longitude) as min_lon,
            MAX(longitude) as max_lon,
            AVG(latitude) as avg_lat,
            AVG(longitude) as avg_lon,
            MIN(altitude) as min_alt,
            MAX(altitude) as max_alt,
            AVG(altitude) as avg_alt,
            COUNT(*) as count
        FROM locations
    """)

    result = cursor.fetchone()

    if not result or result[9] == 0:
        print(f"\n{'=' * 80}")
        print("GEOGRAPHIC RANGE")
        print(f"{'=' * 80}")
        print("No GPS data available\n")
        return

    (
        min_lat,
        max_lat,
        min_lon,
        max_lon,
        avg_lat,
        avg_lon,
        min_alt,
        max_alt,
        avg_alt,
        count,
    ) = result

    print(f"\n{'=' * 80}")
    print("GEOGRAPHIC RANGE")
    print(f"{'=' * 80}")
    print(f"Photos with GPS: {count}")
    print(f"\nLatitude range:  {min_lat:.6f} to {max_lat:.6f}")
    print(f"Longitude range: {min_lon:.6f} to {max_lon:.6f}")
    print(f"Center point: ({avg_lat:.6f}, {avg_lon:.6f})")

    # Calculate rough geographic spread
    lat_span_km = abs(max_lat - min_lat) * 111  # 1° ≈ 111km
    lon_span_km = (
        abs(max_lon - min_lon) * 111 * abs(avg_lat / 90)
    )  # Adjust for latitude

    print(f"\nGeographic spread:")
    print(f"  North-South: {lat_span_km:.2f}km")
    print(f"  East-West: {lon_span_km:.2f}km")

    if min_alt and max_alt and avg_alt:
        print(f"\nAltitude statistics:")
        print(f"  Range: {min_alt:.2f}m to {max_alt:.2f}m")
        print(f"  Average: {avg_alt:.2f}m")

    print(f"{'=' * 80}\n")


def show_missing_gps(conn: sqlite3.Connection, limit: int = 10):
    """Show sample of images without GPS data."""
    cursor = conn.cursor()

    cursor.execute(f"""
        SELECT i.filename, i.date_taken, i.date_source
        FROM images i
        LEFT JOIN locations l ON i.id = l.image_id
        WHERE l.id IS NULL
        ORDER BY i.date_taken DESC
        LIMIT {limit}
    """)

    results = cursor.fetchall()

    print(f"\n{'=' * 80}")
    print(f"IMAGES WITHOUT GPS (showing {limit})")
    print(f"{'=' * 80}\n")

    if not results:
        print("All images have GPS data!\n")
        return

    for filename, date, source in results:
        print(f"⏭️  {filename}")
        print(f"   Date: {date} (source: {source})\n")


# Query registry
QUERIES = {
    "schema": ("Database schema", show_schema),
    "all_images": ("List all images", show_all_images),
    "gps_coverage": ("GPS coverage statistics", show_gps_coverage),
    "date_sources": ("Date source breakdown", show_date_sources),
    "cameras": ("Camera breakdown", show_cameras),
    "gps_sample": ("Sample GPS data", show_gps_sample),
    "coord_ranges": ("Geographic coordinate ranges", show_coord_ranges),
    "missing_gps": ("Images without GPS", show_missing_gps),
}


def run_all_queries(conn: sqlite3.Connection):
    """Run all queries in sequence."""
    for query_name, (description, query_func) in QUERIES.items():
        query_func(conn)


def main():
    parser = argparse.ArgumentParser(
        description="Database inspection utility for photo sovereignty pipeline",
        epilog=f"Available queries: {', '.join(QUERIES.keys())}",
    )

    parser.add_argument("--db", help="Database path (default: from config.yaml)")

    parser.add_argument(
        "--query",
        choices=list(QUERIES.keys()) + ["all"],
        help="Run specific query (default: all)",
    )

    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Config file path (default: config.yaml)",
    )

    args = parser.parse_args()

    # Determine database path
    if args.db:
        db_path = Path(args.db).expanduser()
    else:
        try:
            config = load_config(args.config)
            db_path = get_path(config, "database")
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            print("\nSpecify database path explicitly:")
            print("  python dev_tools/inspect_db.py --db ~/path/to/photo_archive.db")
            sys.exit(1)

    # Connect to database
    try:
        conn = connect_db(db_path)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # Run queries
    try:
        if args.query and args.query != "all":
            description, query_func = QUERIES[args.query]
            print(f"\n🔍 Running query: {description}")
            query_func(conn)
        else:
            print(f"\n🔍 Running all database queries...")
            run_all_queries(conn)

        print(f"✅ Database inspection complete\n")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
