#!/usr/bin/env python3
"""
Query and verify GPS data in database.

Foundation note: Comprehensive verification of GPS extraction results.
Tests coverage, coordinate validity, altitude stats.

Usage:
    python tests/query_gps.py
"""

import sqlite3
from pathlib import Path


def connect_db(db_path):
    """Connect to database."""
    return sqlite3.connect(db_path)


def show_gps_coverage(conn):
    """Show GPS coverage statistics."""
    cursor = conn.cursor()
    
    # Total images
    cursor.execute("SELECT COUNT(*) FROM images")
    total_images = cursor.fetchone()[0]
    
    # Images with GPS
    cursor.execute("SELECT COUNT(*) FROM locations")
    gps_images = cursor.fetchone()[0]
    
    # Calculate coverage
    coverage = (gps_images / total_images * 100) if total_images > 0 else 0
    
    print(f"\n{'='*60}")
    print(f"GPS COVERAGE STATISTICS")
    print(f"{'='*60}")
    print(f"Total images: {total_images}")
    print(f"Images with GPS: {gps_images} ({coverage:.1f}%)")
    print(f"Images without GPS: {total_images - gps_images}")
    print(f"{'='*60}")


def show_gps_sample(conn, limit=10):
    """Show sample of images with GPS data."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            i.filename,
            i.date_taken,
            l.latitude,
            l.longitude,
            l.altitude
        FROM images i
        JOIN locations l ON i.id = l.image_id
        ORDER BY i.date_taken
        LIMIT ?
    """, (limit,))
    
    results = cursor.fetchall()
    
    print(f"\n{'='*60}")
    print(f"GPS DATA SAMPLE (first {limit} with GPS)")
    print(f"{'='*60}")
    
    if not results:
        print("No GPS data found in database")
        return
    
    for filename, date, lat, lon, alt in results:
        alt_str = f"{alt:.2f}m" if alt else "N/A"
        print(f"\n📍 {filename}")
        print(f"   Date: {date}")
        print(f"   Coords: ({lat:.6f}, {lon:.6f})")
        print(f"   Altitude: {alt_str}")


def show_coordinate_ranges(conn):
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
            COUNT(*) as count
        FROM locations
    """)
    
    result = cursor.fetchone()
    
    if not result or result[6] == 0:
        print(f"\n{'='*60}")
        print("GEOGRAPHIC RANGE")
        print(f"{'='*60}")
        print("No GPS data available")
        return
    
    min_lat, max_lat, min_lon, max_lon, avg_lat, avg_lon, count = result
    
    print(f"\n{'='*60}")
    print("GEOGRAPHIC RANGE")
    print(f"{'='*60}")
    print(f"Latitude range:  {min_lat:.6f} to {max_lat:.6f}")
    print(f"Longitude range: {min_lon:.6f} to {max_lon:.6f}")
    print(f"Center point: ({avg_lat:.6f}, {avg_lon:.6f})")
    print(f"Photos with GPS: {count}")
    
    # Calculate rough geographic spread
    lat_span_km = abs(max_lat - min_lat) * 111  # 1° ≈ 111km
    lon_span_km = abs(max_lon - min_lon) * 111 * 0.85  # Adjust for Melbourne latitude
    
    print(f"\nGeographic spread:")
    print(f"  North-South: {lat_span_km:.2f}km")
    print(f"  East-West: {lon_span_km:.2f}km")
    
    # Melbourne sanity check (rough bounds: -38 to -37 lat, 144 to 145 lon)
    if -38 < avg_lat < -37 and 144 < avg_lon < 145:
        print(f"\n✅ Center point confirms Melbourne area")
    else:
        print(f"\n⚠️  Center point outside Melbourne (check coordinates)")
    
    print(f"{'='*60}")


def show_altitude_stats(conn):
    """Show altitude statistics."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            COUNT(*) as count,
            MIN(altitude) as min_alt,
            MAX(altitude) as max_alt,
            AVG(altitude) as avg_alt
        FROM locations
        WHERE altitude IS NOT NULL
    """)
    
    result = cursor.fetchone()
    count, min_alt, max_alt, avg_alt = result
    
    print(f"\n{'='*60}")
    print("ALTITUDE STATISTICS")
    print(f"{'='*60}")
    
    if count and count > 0:
        print(f"Images with altitude: {count}")
        print(f"Range: {min_alt:.2f}m to {max_alt:.2f}m")
        print(f"Average: {avg_alt:.2f}m")
        
        # Melbourne sanity check (mostly 0-100m, some hills to 200m)
        if 0 <= avg_alt <= 200:
            print(f"✅ Altitude range reasonable for Melbourne")
        else:
            print(f"⚠️  Unusual altitude range (check data)")
    else:
        print("No altitude data available")
    
    print(f"{'='*60}")


def show_images_without_gps(conn, limit=10):
    """Show sample of images that lack GPS data."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT i.filename, i.date_taken, i.date_source
        FROM images i
        LEFT JOIN locations l ON i.id = l.image_id
        WHERE l.id IS NULL
        ORDER BY i.date_taken
        LIMIT ?
    """, (limit,))
    
    results = cursor.fetchall()
    
    print(f"\n{'='*60}")
    print(f"IMAGES WITHOUT GPS (sample of {limit})")
    print(f"{'='*60}")
    
    if not results:
        print("All images have GPS data!")
        return
    
    for filename, date, source in results:
        print(f"⏭️  {filename}")
        print(f"   Date: {date} (source: {source})")


def show_gps_by_date(conn):
    """Show GPS data grouped by date."""
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            DATE(i.date_taken) as photo_date,
            COUNT(*) as photos_with_gps
        FROM images i
        JOIN locations l ON i.id = l.image_id
        WHERE i.date_taken IS NOT NULL
        GROUP BY DATE(i.date_taken)
        ORDER BY photo_date
    """)
    
    results = cursor.fetchall()
    
    print(f"\n{'='*60}")
    print("GPS DATA BY DATE")
    print(f"{'='*60}")
    
    if not results:
        print("No GPS data with valid dates")
        return
    
    for date, count in results:
        print(f"  {date}: {count} photos")
    
    print(f"{'='*60}")


if __name__ == "__main__":
    # Connect to production database
    db_path = Path("~/data/media/images/organised/photo_archive.db").expanduser()
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print("Run process_photos.py first to create database")
        exit(1)
    
    conn = connect_db(db_path)
    
    # Run all GPS verification queries
    show_gps_coverage(conn)
    show_gps_sample(conn, limit=10)
    show_coordinate_ranges(conn)
    show_altitude_stats(conn)
    show_images_without_gps(conn, limit=5)
    show_gps_by_date(conn)
    
    print(f"\n{'='*60}")
    print("✅ GPS verification complete")
    print(f"{'='*60}\n")
    
    conn.close()
