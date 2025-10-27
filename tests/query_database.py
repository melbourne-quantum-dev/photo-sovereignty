# tests/query_database.py
import sqlite3
from pathlib import Path

def connect_db(db_path="test.db"):
    """Connect to database and return connection."""
    return sqlite3.connect(db_path)

def show_all_images(conn):
    """Display all images in database."""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM images")
    
    print("\n" + "="*80)
    print("ALL IMAGES")
    print("="*80)
    
    for row in cursor.fetchall():
        print(f"\nID: {row[0]}")
        print(f"  Original: {row[1]}")
        print(f"  Organized: {row[2]}")
        print(f"  Filename: {row[3]}")
        print(f"  Date: {row[4]}")
        print(f"  Source: {row[5]}")
        print(f"  Camera: {row[6]} {row[7]}")

def show_by_date_source(conn):
    """Group images by date source quality."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date_source, COUNT(*) as count
        FROM images
        GROUP BY date_source
    """)
    
    print("\n" + "="*80)
    print("DATE SOURCE BREAKDOWN")
    print("="*80)
    
    for source, count in cursor.fetchall():
        print(f"  {source}: {count} images")

def show_camera_breakdown(conn):
    """Show photos by camera."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            camera_make, 
            camera_model, 
            COUNT(*) as count
        FROM images
        GROUP BY camera_make, camera_model
    """)
    
    print("\n" + "="*80)
    print("CAMERA BREAKDOWN")
    print("="*80)
    
    for make, model, count in cursor.fetchall():
        if make:
            print(f"  {make} {model}: {count} images")
        else:
            print(f"  No camera metadata: {count} images")

def show_date_range(conn, start_date, end_date):
    """Query images in date range."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT filename, date_taken, camera_make, camera_model
        FROM images
        WHERE date_taken BETWEEN ? AND ?
        ORDER BY date_taken
    """, (start_date, end_date))
    
    print(f"\n" + "="*80)
    print(f"IMAGES BETWEEN {start_date} AND {end_date}")
    print("="*80)
    
    results = cursor.fetchall()
    if results:
        for filename, date, make, model in results:
            camera = f"{make} {model}" if make else "No camera"
            print(f"  {date}: {filename} ({camera})")
    else:
        print("  No images in this date range")


def show_filesystem_sources(conn):
    """Show only filesystem-sourced images."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT filename, date_taken, organized_path
        FROM images
        WHERE date_source = 'filesystem'
        ORDER BY date_taken
    """)
    
    print("\n" + "="*80)
    print("FILESYSTEM-SOURCED IMAGES (lower confidence)")
    print("="*80)
    
    for filename, date, path in cursor.fetchall():
        print(f"  {filename}")
        print(f"    Date: {date}")
        print(f"    Path: {path}")

def show_schema(conn):
    """Display database schema."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sql FROM sqlite_master 
        WHERE type='table' AND name='images'
    """)
    
    print("\n" + "="*80)
    print("DATABASE SCHEMA")
    print("="*80)
    print(cursor.fetchone()[0])

# Interactive playground
if __name__ == "__main__":
    db_path = Path("~/data/media/images/organised/photo_archive.db").expanduser()
    
    if not db_path.exists():
        print(f"Database {db_path} not found!")
        exit(1)
    
    conn = connect_db((db_path))
    
    # Run all queries
    show_schema(conn)
    show_all_images(conn)
    show_by_date_source(conn)
    show_camera_breakdown(conn)
    show_filesystem_sources(conn)
    show_date_range(conn, '2025-05-24', '2025-05-30')
    
    print("\n" + "="*80)
    print("✅ Query tests complete")
    print("="*80)
    
    conn.close()