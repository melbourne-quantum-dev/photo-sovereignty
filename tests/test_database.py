"""Tests for database operations.

Tests cover:
- Schema creation (tables, indexes)
- Image insertion and retrieval
- Idempotent operations
- Duplicate handling
- GPS location storage
- LEFT JOIN queries for incremental processing
- Date range queries
- Camera-based queries

Author: Leonardo
Version: v0.1.0
"""

import sqlite3
from datetime import datetime

import pytest

from src.database import (
    create_database,
    insert_image,
    insert_location,
    query_by_camera,
    query_by_date_range,
    query_images_without_gps,
)


class TestDatabaseCreation:
    """Test database schema creation."""

    def test_create_database_creates_file(self, temp_db):
        """Creating database should create file."""
        conn = create_database(temp_db)
        conn.close()

        assert temp_db.exists()

    def test_create_database_creates_images_table(self, temp_db):
        """Database should have images table with correct schema."""
        conn = create_database(temp_db)
        cursor = conn.cursor()

        # Check table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='images'
        """)
        assert cursor.fetchone() is not None

        # Check schema
        cursor.execute("PRAGMA table_info(images)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {
            "id",
            "original_path",
            "organized_path",
            "filename",
            "date_taken",
            "date_source",
            "camera_make",
            "camera_model",
            "created_at",
        }
        assert columns == expected_columns

        conn.close()

    def test_create_database_creates_locations_table(self, temp_db):
        """Database should have locations table for GPS data."""
        conn = create_database(temp_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='locations'
        """)
        assert cursor.fetchone() is not None

        # Check schema
        cursor.execute("PRAGMA table_info(locations)")
        columns = {row[1] for row in cursor.fetchall()}

        expected_columns = {"id", "image_id", "latitude", "longitude", "altitude"}
        assert columns == expected_columns

        conn.close()

    def test_create_database_creates_indexes(self, temp_db):
        """Database should have indexes for common queries."""
        conn = create_database(temp_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index'
        """)
        indexes = {row[0] for row in cursor.fetchall()}

        expected_indexes = {
            "idx_date_taken",
            "idx_camera",
            "idx_image_location",
            "idx_coordinates",
        }

        # Indexes should exist
        assert expected_indexes.issubset(indexes)

        conn.close()

    def test_create_database_is_idempotent(self, temp_db):
        """Calling create_database multiple times should be safe."""
        conn1 = create_database(temp_db)
        conn1.close()

        # Second call should not fail
        conn2 = create_database(temp_db)
        cursor = conn2.cursor()

        # Tables should still exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
        """)
        tables = {row[0] for row in cursor.fetchall()}

        assert "images" in tables
        assert "locations" in tables

        conn2.close()


class TestImageInsertion:
    """Test inserting image metadata."""

    def test_insert_image_returns_id(self, temp_db_with_schema, sample_image_data):
        """Inserting image should return auto-incremented ID."""
        conn = temp_db_with_schema

        image_id = insert_image(conn, sample_image_data)

        assert isinstance(image_id, int)
        assert image_id > 0

    def test_insert_image_stores_data(self, temp_db_with_schema, sample_image_data):
        """Inserted image should be retrievable from database."""
        conn = temp_db_with_schema

        image_id = insert_image(conn, sample_image_data)

        # Query it back
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM images WHERE id = ?", (image_id,))
        row = cursor.fetchone()

        assert row is not None
        assert row[1] == sample_image_data["original_path"]  # original_path
        assert row[2] == sample_image_data["organized_path"]  # organized_path
        assert row[3] == sample_image_data["filename"]  # filename

    def test_insert_multiple_images(self, temp_db_with_schema):
        """Multiple images can be inserted."""
        conn = temp_db_with_schema

        image_data_1 = {
            "original_path": "/test/IMG_001.jpg",
            "organized_path": "/organized/2025/2025-01-01_120000.jpg",
            "filename": "2025-01-01_120000.jpg",
            "date_taken": datetime(2025, 1, 1, 12, 0, 0),
            "date_source": "exif",
            "camera_make": "Canon",
            "camera_model": "EOS R5",
        }

        image_data_2 = {
            "original_path": "/test/IMG_002.jpg",
            "organized_path": "/organized/2025/2025-01-02_120000.jpg",
            "filename": "2025-01-02_120000.jpg",
            "date_taken": datetime(2025, 1, 2, 12, 0, 0),
            "date_source": "exif",
            "camera_make": "Canon",
            "camera_model": "EOS R5",
        }

        id1 = insert_image(conn, image_data_1)
        id2 = insert_image(conn, image_data_2)

        assert id2 == id1 + 1  # Auto-increment

        # Both should exist
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM images")
        assert cursor.fetchone()[0] == 2

    def test_insert_image_with_none_date(self, temp_db_with_schema):
        """Inserting image without date should work."""
        conn = temp_db_with_schema

        image_data = {
            "original_path": "/test/no_date.png",
            "organized_path": "/organized/no_date.png",
            "filename": "no_date.png",
            "date_taken": None,
            "date_source": "none",
            "camera_make": None,
            "camera_model": None,
        }

        image_id = insert_image(conn, image_data)

        assert image_id > 0

        # Verify NULL date is stored
        cursor = conn.cursor()
        cursor.execute("SELECT date_taken FROM images WHERE id = ?", (image_id,))
        date = cursor.fetchone()[0]

        assert date is None


class TestIdempotency:
    """Test idempotent database operations."""

    def test_duplicate_detection_by_original_path(self, temp_db_with_schema):
        """Application should detect duplicates by checking original_path."""
        conn = temp_db_with_schema

        image_data = {
            "original_path": "/test/duplicate.jpg",
            "organized_path": "/organized/2025/file.jpg",
            "filename": "file.jpg",
            "date_taken": datetime(2025, 1, 1),
            "date_source": "exif",
            "camera_make": "Test",
            "camera_model": "Camera",
        }

        # Insert first time
        id1 = insert_image(conn, image_data)

        # Check if already processed (this is what process_photos.py does)
        cursor = conn.cursor()
        cursor.execute("SELECT original_path FROM images")
        already_processed = {row[0] for row in cursor.fetchall()}

        # Should detect duplicate
        assert image_data["original_path"] in already_processed


class TestLocationOperations:
    """Test GPS location storage and retrieval."""

    def test_insert_location(self, temp_db_with_schema, sample_image_data):
        """Inserting GPS coordinates should work."""
        conn = temp_db_with_schema

        # Insert image first
        image_id = insert_image(conn, sample_image_data)

        # Insert GPS location
        lat, lon, alt = -37.814, 144.963, 10.5
        location_id = insert_location(conn, image_id, lat, lon, alt)

        assert location_id > 0

        # Verify storage
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
        row = cursor.fetchone()

        assert row[1] == image_id  # image_id
        assert row[2] == lat  # latitude
        assert row[3] == lon  # longitude
        assert row[4] == alt  # altitude

    def test_insert_location_without_altitude(
        self, temp_db_with_schema, sample_image_data
    ):
        """GPS coordinates without altitude should work."""
        conn = temp_db_with_schema

        image_id = insert_image(conn, sample_image_data)
        location_id = insert_location(conn, image_id, -37.814, 144.963)

        cursor = conn.cursor()
        cursor.execute("SELECT altitude FROM locations WHERE id = ?", (location_id,))
        alt = cursor.fetchone()[0]

        assert alt is None

    def test_query_images_without_gps(self, temp_db_with_schema):
        """LEFT JOIN query should find images without GPS data."""
        conn = temp_db_with_schema

        # Insert three images
        image_data_1 = {
            "original_path": "/test/with_gps.jpg",
            "organized_path": "/organized/with_gps.jpg",
            "filename": "with_gps.jpg",
            "date_taken": datetime(2025, 1, 1),
            "date_source": "exif",
            "camera_make": None,
            "camera_model": None,
        }

        image_data_2 = {
            "original_path": "/test/without_gps_1.jpg",
            "organized_path": "/organized/without_gps_1.jpg",
            "filename": "without_gps_1.jpg",
            "date_taken": datetime(2025, 1, 2),
            "date_source": "exif",
            "camera_make": None,
            "camera_model": None,
        }

        image_data_3 = {
            "original_path": "/test/without_gps_2.jpg",
            "organized_path": "/organized/without_gps_2.jpg",
            "filename": "without_gps_2.jpg",
            "date_taken": datetime(2025, 1, 3),
            "date_source": "exif",
            "camera_make": None,
            "camera_model": None,
        }

        id1 = insert_image(conn, image_data_1)
        id2 = insert_image(conn, image_data_2)
        id3 = insert_image(conn, image_data_3)

        # Add GPS to only first image
        insert_location(conn, id1, -37.814, 144.963)

        # Query images without GPS
        without_gps = query_images_without_gps(conn)

        # Should return the two images without GPS
        assert len(without_gps) == 2

        # Check IDs
        ids_without_gps = {row[0] for row in without_gps}
        assert ids_without_gps == {id2, id3}

    def test_query_images_without_gps_empty(
        self, temp_db_with_schema, sample_image_data
    ):
        """Query should return empty when all images have GPS."""
        conn = temp_db_with_schema

        image_id = insert_image(conn, sample_image_data)
        insert_location(conn, image_id, -37.814, 144.963)

        without_gps = query_images_without_gps(conn)

        assert len(without_gps) == 0


class TestQueryOperations:
    """Test various query functions."""

    def test_query_by_date_range(self, temp_db_with_schema):
        """Date range queries should return matching images."""
        conn = temp_db_with_schema

        # Insert images with different dates
        for day in range(1, 6):
            image_data = {
                "original_path": f"/test/day{day}.jpg",
                "organized_path": f"/organized/day{day}.jpg",
                "filename": f"day{day}.jpg",
                "date_taken": datetime(2025, 1, day, 12, 0, 0),
                "date_source": "exif",
                "camera_make": None,
                "camera_model": None,
            }
            insert_image(conn, image_data)

        # Query range 2025-01-02 to 2025-01-04
        results = query_by_date_range(conn, "2025-01-02", "2025-01-04")

        # Should return 3 images
        assert len(results) == 3

    def test_query_by_camera_make_and_model(self, temp_db_with_schema):
        """Camera queries should filter by make and model."""
        conn = temp_db_with_schema

        # Insert images from different cameras
        cameras = [
            ("Apple", "iPhone 14 Pro"),
            ("Apple", "iPhone 15 Pro"),
            ("Canon", "EOS R5"),
        ]

        for make, model in cameras:
            image_data = {
                "original_path": f"/test/{make}_{model}.jpg",
                "organized_path": f"/organized/{make}_{model}.jpg",
                "filename": f"{make}_{model}.jpg",
                "date_taken": datetime(2025, 1, 1),
                "date_source": "exif",
                "camera_make": make,
                "camera_model": model,
            }
            insert_image(conn, image_data)

        # Query for specific camera
        results = query_by_camera(conn, make="Apple", model="iPhone 14 Pro")
        assert len(results) == 1

        # Query by make only
        results = query_by_camera(conn, make="Apple")
        assert len(results) == 2

        # Query all
        results = query_by_camera(conn)
        assert len(results) == 3
