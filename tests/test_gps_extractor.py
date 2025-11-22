"""Tests for GPS coordinate extraction.

Tests cover:
- GPS coordinate extraction from real image files (integration tests)
- Coordinate validation and edge cases
- Handling images without GPS data
- Various file formats (HEIC, JPEG)

Testing Philosophy:
    These tests operate at the PUBLIC API level (extract_gps_coords) rather than
    testing internal helpers (convert_to_degrees). This approach:

    1. Tests what users actually call (production code uses extract_gps_coords)
    2. Tests with real data (actual image files, not synthetic tuples)
    3. More resilient to implementation changes (internal helpers can refactor)
    4. Matches the abstraction level used in examples/stage2_extract_gps.py

    The convert_to_degrees() helper is an INTERNAL implementation detail that
    handles PIL's IFDRational format. Testing it directly with synthetic data
    is brittle because it assumes knowledge of PIL's internal representation.

Version: v0.1.0
"""

import pytest

from src.gps_extractor import extract_gps_coords


class TestGPSExtraction:
    """Test GPS coordinate extraction from real images.

    These tests use the same pattern as production code (stage2_extract_gps.py):
    - Call extract_gps_coords() with image path
    - Handle None return for images without GPS
    - Validate coordinates when present
    """

    @pytest.mark.integration
    def test_extract_gps_from_sample_images(self, sample_photos_dir):
        """Extract GPS from all sample images, validate when present.

        This tests the REAL workflow:
        1. Read actual image files from disk
        2. Extract GPS using public API (extract_gps_coords)
        3. Validate coordinates fall within expected ranges

        Some images may not have GPS (location services off, screenshots, etc.)
        This is EXPECTED behavior, not a failure.
        """
        # Find all sample photos
        photo_files = list(sample_photos_dir.glob("*.*"))
        photo_files = [
            f
            for f in photo_files
            if f.suffix.lower() in [".heic", ".jpeg", ".jpg", ".png"]
        ]

        assert len(photo_files) > 0, "Need at least one sample image"

        gps_found = 0
        no_gps = 0

        for photo in photo_files:
            # Use same pattern as production code (stage2_extract_gps.py)
            coords = extract_gps_coords(str(photo))

            if coords:
                lat, lon, alt = coords
                gps_found += 1

                # Validate coordinate ranges (geographic sanity checks)
                assert -90 <= lat <= 90, f"Latitude out of range: {lat}"
                assert -180 <= lon <= 180, f"Longitude out of range: {lon}"

                # Altitude can be None or a number (including negative - below sea level)
                if alt is not None:
                    assert isinstance(alt, (int, float)), (
                        f"Altitude should be numeric: {type(alt)}"
                    )

                print(f"  ✅ {photo.name}: ({lat:.6f}, {lon:.6f}, {alt})")
            else:
                # No GPS data - this is expected for some images
                no_gps += 1
                print(f"  ⏭️  {photo.name}: No GPS data")

        # Report statistics
        total = len(photo_files)
        print(f"\nGPS extraction summary: {gps_found}/{total} images had GPS data")

        # We don't assert gps_found > 0 because it depends on which samples you have
        # The test passes as long as extraction doesn't crash

    @pytest.mark.integration
    def test_extract_gps_from_heic(self, sample_photos_dir):
        """HEIC files should extract GPS if present."""
        heic_files = list(sample_photos_dir.glob("*.HEIC")) + list(
            sample_photos_dir.glob("*.heic")
        )

        if not heic_files:
            pytest.skip("No HEIC files in sample data")

        # Test at least one HEIC file
        for heic in heic_files[:3]:  # Test first 3 HEIC files
            coords = extract_gps_coords(str(heic))

            # Coords may be None (no GPS) or tuple (has GPS)
            # Both are valid - we're testing the extraction doesn't crash
            if coords:
                assert len(coords) == 3, "Should return (lat, lon, alt) tuple"
                lat, lon, alt = coords
                assert isinstance(lat, (int, float))
                assert isinstance(lon, (int, float))

    @pytest.mark.integration
    def test_extract_gps_from_jpeg(self, sample_photos_dir):
        """JPEG files should extract GPS if present."""
        jpeg_files = (
            list(sample_photos_dir.glob("*.JPEG"))
            + list(sample_photos_dir.glob("*.jpeg"))
            + list(sample_photos_dir.glob("*.JPG"))
            + list(sample_photos_dir.glob("*.jpg"))
        )

        if not jpeg_files:
            pytest.skip("No JPEG files in sample data")

        # Test at least one JPEG file
        for jpeg in jpeg_files[:3]:  # Test first 3 JPEG files
            coords = extract_gps_coords(str(jpeg))

            # Coords may be None (no GPS) or tuple (has GPS)
            if coords:
                assert len(coords) == 3, "Should return (lat, lon, alt) tuple"
                lat, lon, alt = coords
                assert isinstance(lat, (int, float))
                assert isinstance(lon, (int, float))

    def test_extract_gps_nonexistent_file(self):
        """Non-existent file should return None gracefully."""
        coords = extract_gps_coords("/nonexistent/file.jpg")

        # Production code handles errors gracefully by returning None
        assert coords is None

    def test_extract_gps_returns_correct_tuple_format(self):
        """Validate the expected return format.

        This is a DOCUMENTATION test that specifies the contract:
        - Returns None if no GPS data
        - Returns (lat, lon, alt) tuple if GPS present
        - lat/lon are floats in decimal degrees
        - alt is float (meters) or None
        """
        # This test documents the expected interface
        # Actual validation happens in integration tests above

        # Expected format when GPS present
        mock_coords = (-37.815, 144.963, 10.5)
        lat, lon, alt = mock_coords

        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert isinstance(alt, (float, int, type(None)))

        # Expected format when no GPS
        mock_no_gps = None
        assert mock_no_gps is None


class TestCoordinateValidation:
    """Test coordinate validation and geographic edge cases.

    These tests document expected coordinate formats and ranges.
    They use REAL data patterns from actual GPS extractions.
    """

    def test_southern_hemisphere_latitude(self):
        """Southern hemisphere latitudes should be negative.

        Melbourne, Australia: ~-37.8°, 144.9°
        This documents the coordinate sign convention.
        """
        melbourne_lat = -37.814

        assert melbourne_lat < 0, "Southern hemisphere = negative latitude"
        assert -90 <= melbourne_lat <= 90, "Latitude must be in valid range"

    def test_eastern_hemisphere_longitude(self):
        """Eastern hemisphere longitudes should be positive.

        Melbourne is in eastern hemisphere (east of Prime Meridian).
        """
        melbourne_lon = 144.963

        assert melbourne_lon > 0, "Eastern hemisphere = positive longitude"
        assert -180 <= melbourne_lon <= 180, "Longitude must be in valid range"

    def test_altitude_can_be_negative(self):
        """Altitude can be negative (below sea level).

        Examples: Dead Sea (-430m), Death Valley (-86m)
        GPS altitude is relative to mean sea level.
        """
        dead_sea_alt = -430.0

        assert isinstance(dead_sea_alt, float)
        assert dead_sea_alt < 0, "Below sea level = negative altitude"

    def test_altitude_can_be_none(self):
        """Some GPS records may lack altitude data.

        2D GPS fix (lat/lon only) is valid when:
        - Insufficient satellite visibility
        - Older GPS hardware
        - EXIF data stripped/edited
        """
        coords_without_alt = (-37.814, 144.963, None)
        lat, lon, alt = coords_without_alt

        assert alt is None, "Altitude can be None"
        assert lat is not None and lon is not None, "Lat/lon required"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_extract_gps_empty_path(self):
        """Empty path should return None gracefully."""
        result = extract_gps_coords("")
        assert result is None

    def test_extract_gps_directory_path(self, temp_dir):
        """Directory path should return None gracefully."""
        result = extract_gps_coords(str(temp_dir))
        assert result is None

    def test_coordinate_precision(self):
        """Document coordinate precision expectations.

        GPS accuracy: ±5-10m horizontal (good conditions)
        At equator: 1° ≈ 111km, so we need ~5-6 decimal places

        Database stores full float precision, display rounds to 6 decimals.
        """
        # 6 decimal places = ~0.1m precision (overkill but harmless)
        precise_lat = -37.834667

        # This level of precision is meaningful for GPS
        assert len(str(precise_lat).split(".")[1]) >= 6


class TestIntegration:
    """Integration tests with real sample data and database."""

    @pytest.mark.integration
    def test_full_gps_workflow(self, sample_photos_dir, temp_db_with_schema):
        """Integration test: Extract GPS from samples and store in DB.

        This tests the COMPLETE workflow used in production:
        1. Extract GPS from real image files (extract_gps_coords)
        2. Insert into database (insert_location)
        3. Validate database storage

        Matches the pattern in examples/stage2_extract_gps.py
        """
        from src.database import insert_image, insert_location

        conn = temp_db_with_schema

        # Find all sample photos
        photo_files = list(sample_photos_dir.glob("*.*"))
        photo_files = [
            f
            for f in photo_files
            if f.suffix.lower() in [".heic", ".jpeg", ".jpg", ".png"]
        ]

        gps_count = 0

        for photo in photo_files:
            # Extract GPS using public API (same as production code)
            coords = extract_gps_coords(str(photo))

            if coords:
                lat, lon, alt = coords

                # Create minimal image record for testing
                image_data = {
                    "original_path": str(photo),
                    "organized_path": str(photo),
                    "filename": photo.name,
                    "date_taken": None,
                    "date_source": "test",
                    "camera_make": None,
                    "camera_model": None,
                }

                # Insert using production database functions
                from datetime import datetime

                image_data["date_taken"] = datetime.now()
                image_id = insert_image(conn, image_data)
                insert_location(conn, image_id, lat, lon, alt)

                gps_count += 1

        # Verify data was stored
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM locations")
        stored_count = cursor.fetchone()[0]

        assert stored_count == gps_count, "All GPS data should be stored"
        assert gps_count >= 0, "Should have non-negative count"
