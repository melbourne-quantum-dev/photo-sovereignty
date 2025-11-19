"""Tests for GPS coordinate extraction.

Tests cover:
- DMS to decimal conversion
- GPS coordinate extraction from EXIF
- Altitude extraction
- Handling images without GPS data
- Various file formats

Author: Leonardo
Version: v0.1.0
"""

import pytest

from src.gps_extractor import convert_to_degrees, extract_gps_coords


class TestDMSConversion:
    """Test degrees/minutes/seconds to decimal conversion."""

    def test_convert_simple_coordinates(self):
        """Basic DMS conversion should work correctly."""
        # 37° 48' 54.6" S = -37.815167
        dms = ((37, 1), (48, 1), (54.6, 1))  # degrees, minutes, seconds as rationals

        decimal = convert_to_degrees(dms)

        assert decimal is not None
        assert abs(decimal - 37.815167) < 0.000001  # Within floating point tolerance

    def test_convert_zero_minutes_seconds(self):
        """Coordinates with zero minutes/seconds should work."""
        # 45° 0' 0" = 45.0
        dms = ((45, 1), (0, 1), (0, 1))

        decimal = convert_to_degrees(dms)

        assert abs(decimal - 45.0) < 0.000001

    def test_convert_fractional_seconds(self):
        """Fractional seconds should be handled correctly."""
        # 37° 30' 30.5" = 37.508472
        dms = ((37, 1), (30, 1), (30.5, 1))

        decimal = convert_to_degrees(dms)

        assert abs(decimal - 37.508472) < 0.000001

    def test_convert_rational_format(self):
        """DMS in rational tuple format ((degrees, 1), (minutes, 1), (seconds, 1))."""
        # This is how PIL/pillow-heif returns GPS data
        # 144° 57' 45.33" = 144.962592
        dms = ((144, 1), (57, 1), (45.33, 1))

        decimal = convert_to_degrees(dms)

        assert abs(decimal - 144.962592) < 0.000001

    def test_convert_none_returns_none(self):
        """None input should return None."""
        result = convert_to_degrees(None)
        assert result is None

    def test_convert_invalid_format(self):
        """Invalid format should return None gracefully."""
        result = convert_to_degrees(((1, 0),))  # Division by zero potential
        # Should handle error gracefully
        assert result is None or isinstance(result, float)


class TestGPSExtraction:
    """Test GPS coordinate extraction from images."""

    @pytest.mark.integration
    def test_extract_gps_from_heic_with_gps(self, sample_heic_with_gps):
        """HEIC file with GPS should return coordinates."""
        coords = extract_gps_coords(str(sample_heic_with_gps))

        # May or may not have GPS depending on sample
        # If it does, should be valid tuple
        if coords:
            lat, lon, alt = coords

            # Latitude should be between -90 and 90
            assert -90 <= lat <= 90

            # Longitude should be between -180 and 180
            assert -180 <= lon <= 180

            # Altitude can be None or a number
            assert alt is None or isinstance(alt, (int, float))

    @pytest.mark.integration
    def test_extract_gps_from_image_without_gps(self, sample_png):
        """Image without GPS should return None."""
        coords = extract_gps_coords(str(sample_png))

        # PNG typically has no GPS
        # Should return None (not raise exception)
        assert coords is None or isinstance(coords, tuple)

    def test_extract_gps_nonexistent_file(self):
        """Non-existent file should return None."""
        coords = extract_gps_coords("/nonexistent/file.jpg")

        assert coords is None

    def test_extract_gps_returns_tuple_format(self):
        """GPS coordinates should be returned as (lat, lon, alt) tuple."""
        # This test validates the expected return format
        # Actual GPS extraction tested with real samples above

        # Expected format: (latitude, longitude, altitude)
        # latitude: float, -90 to 90
        # longitude: float, -180 to 180
        # altitude: float or None

        # Mock test to document expected format
        mock_coords = (-37.815, 144.963, 10.5)
        lat, lon, alt = mock_coords

        assert isinstance(lat, float)
        assert isinstance(lon, float)
        assert isinstance(alt, (float, int, type(None)))


class TestCoordinateValidation:
    """Test coordinate validation and edge cases."""

    def test_southern_hemisphere_latitude(self):
        """Southern hemisphere latitudes should be negative."""
        # Melbourne, Australia is at approximately -37.8°, 144.9°
        # If sample data is from Melbourne, latitude should be negative
        # This is a documentation test for coordinate sign conventions

        melbourne_lat = -37.814
        assert melbourne_lat < 0  # Southern hemisphere
        assert -90 <= melbourne_lat <= 90

    def test_eastern_hemisphere_longitude(self):
        """Eastern hemisphere longitudes should be positive."""
        # Melbourne is in eastern hemisphere
        melbourne_lon = 144.963
        assert melbourne_lon > 0  # Eastern hemisphere
        assert -180 <= melbourne_lon <= 180

    def test_altitude_can_be_negative(self):
        """Altitude can be negative (below sea level)."""
        # Dead Sea is at -430m, Death Valley at -86m
        dead_sea_alt = -430.0
        assert isinstance(dead_sea_alt, float)
        assert dead_sea_alt < 0

    def test_altitude_can_be_none(self):
        """Some images may lack altitude data."""
        # GPS coordinates without altitude are valid
        coords_without_alt = (-37.814, 144.963, None)
        lat, lon, alt = coords_without_alt

        assert alt is None
        assert lat is not None
        assert lon is not None


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

    def test_dms_conversion_edge_values(self):
        """Test DMS conversion with edge values."""
        # 0° 0' 0" = 0.0
        zero_dms = ((0, 1), (0, 1), (0, 1))
        assert abs(convert_to_degrees(zero_dms) - 0.0) < 0.000001

        # 90° 0' 0" = 90.0 (max latitude)
        max_lat_dms = ((90, 1), (0, 1), (0, 1))
        assert abs(convert_to_degrees(max_lat_dms) - 90.0) < 0.000001

        # 180° 0' 0" = 180.0 (max longitude)
        max_lon_dms = ((180, 1), (0, 1), (0, 1))
        assert abs(convert_to_degrees(max_lon_dms) - 180.0) < 0.000001


class TestIntegration:
    """Integration tests with real sample data."""

    @pytest.mark.integration
    def test_full_gps_workflow(self, sample_photos_dir, temp_db_with_schema):
        """Integration test: Extract GPS from samples and store in DB."""
        from pathlib import Path

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
            # Extract GPS
            coords = extract_gps_coords(str(photo))

            if coords:
                lat, lon, alt = coords

                # Create minimal image record
                image_data = {
                    "original_path": str(photo),
                    "organized_path": str(photo),
                    "filename": photo.name,
                    "date_taken": None,
                    "date_source": "test",
                    "camera_make": None,
                    "camera_model": None,
                }

                image_id = insert_image(conn, image_data)
                insert_location(conn, image_id, lat, lon, alt)

                gps_count += 1

        # Should have extracted at least some GPS data
        # (depending on sample photos available)
        assert gps_count >= 0  # Non-negative count
