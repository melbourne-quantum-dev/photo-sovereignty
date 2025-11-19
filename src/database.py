# src/database.py
import sqlite3
from datetime import datetime

def create_database(db_path="photo_archive.db"):
    """Create SQLite database with images table.
    
    Returns connection object.
    """
    # conn object represents established connection, acting as the link between your Python program and the database
    conn = sqlite3.connect(db_path)
    # cursor object = control structure that allows you to execute SQL commands and manage the results within the context of that database connection
    cursor = conn.cursor()
    # create a table (like a spreadsheet)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_path TEXT NOT NULL,
            organized_path TEXT NOT NULL,
            filename TEXT NOT NULL,
            date_taken DATETIME,
            date_source TEXT,
            camera_make TEXT,
            camera_model TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Index for common queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_date_taken 
        ON images(date_taken)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_camera 
        ON images(camera_make, camera_model)
    """)
    
    # Week 2: Locations table for GPS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            altitude REAL,
            FOREIGN KEY (image_id) REFERENCES images(id)
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_image_location 
        ON locations(image_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_coordinates 
        ON locations(latitude, longitude)
    """)
    
    conn.commit()
    return conn

# Image helper functions
def insert_image(conn, image_data):
    """Insert image metadata into database.
    
    Args:
        conn: SQLite connection
        image_data: dict from rename_and_organize() results
        
    Returns: image_id (int)
    """
    cursor = conn.cursor()
    
    # Convert datetime to string if present
    date_str = None
    if image_data.get('date_taken'):
        date_str = image_data['date_taken'].strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT INTO images (
            original_path, 
            organized_path, 
            filename, 
            date_taken, 
            date_source,
            camera_make, 
            camera_model
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        image_data['original_path'],
        image_data['organized_path'],
        image_data['filename'],
        date_str,
        image_data['date_source'],
        image_data['camera_make'],
        image_data['camera_model']
    ))
    
    conn.commit()
    return cursor.lastrowid


def query_by_date_range(conn, start_date, end_date):
    """Query images within date range.
    
    Args:
        start_date, end_date: datetime objects or strings 'YYYY-MM-DD'
    
    Returns: list of image records
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM images
        WHERE date_taken BETWEEN ? AND ?
        ORDER BY date_taken
    """, (str(start_date), str(end_date)))
    
    return cursor.fetchall()


def query_by_camera(conn, make=None, model=None):
    """Query images by camera."""
    cursor = conn.cursor()
    
    if make and model:
        cursor.execute("""
            SELECT * FROM images
            WHERE camera_make = ? AND camera_model = ?
        """, (make, model))
    elif make:
        cursor.execute("""
            SELECT * FROM images
            WHERE camera_make = ?
        """, (make,))
    else:
        cursor.execute("SELECT * FROM images")
    
    return cursor.fetchall()

# GPS helper functions
def insert_location(conn, image_id, lat, lon, alt=None):
    """Insert GPS coordinates into locations table."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO locations (image_id, latitude, longitude, altitude)
        VALUES (?, ?, ?, ?)
    """, (image_id, lat, lon, alt))
    conn.commit()
    return cursor.lastrowid


def query_images_without_gps(conn):
    """Find images that haven't been GPS processed yet."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT i.id, i.organized_path 
        FROM images i
        LEFT JOIN locations l ON i.id = l.image_id
        WHERE l.id IS NULL
    """)
    return cursor.fetchall()
