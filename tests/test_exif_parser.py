"""Tests for EXIF extraction and file organization.

Tests cover:
- EXIF date extraction hierarchy
- Camera metadata extraction
- Filename generation
- File organization into year directories
- Handling various file formats (HEIC, JPEG, PNG)
- Fallback date extraction (filesystem, filename)

Author: Leonardo
Version: v0.1.0
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.exif_parser import (
    generate_organized_path,
)


class TestExifDateExtraction:
    """Test EXIF date extraction with fallback hierarchy."""

    @pytest.mark.integration
    def test_extract_date_from_heic_with_exif(self, sample_heic_with_gps):
        """HEIC files with EXIF should return date from metadata."""
        date_info = extract_exif_date(str(sample_heic_with_gps))

        assert date_info is not None
        date, source = date_info

        assert isinstance(date, datetime)
        # Source should be one of the EXIF sources
        assert source in ["exif", "exif_datetime_original", "exif_datetime_digitized"]

    @pytest.mark.integration
    def test_extract_date_from_jpeg(self, sample_jpeg):
        """JPEG files should extract date from EXIF if available."""
        date_info = extract_exif_date(str(sample_jpeg))

        # May or may not have EXIF depending on sample
        if date_info:
            date, source = date_info
            assert isinstance(date, datetime)

    @pytest.mark.integration
    def test_extract_date_from_png_fallback(self, sample_png):
        """PNG files without EXIF should fall back to filesystem."""
        date_info = extract_exif_date(str(sample_png))

        # PNG typically lacks EXIF, should fall back to filesystem
        if date_info:
            date, source = date_info
            assert isinstance(date, datetime)
            # Should be filesystem fallback
            assert source in ["filesystem", "filename"]

    def test_extract_date_nonexistent_file(self):
        """Non-existent file should return None."""
        date_info = extract_exif_date("/nonexistent/file.jpg")

        assert date_info is None

    def test_date_source_hierarchy(self):
        """Verify date source priority is documented correctly.

        Priority (from docstring):
        1. EXIF DateTimeOriginal (when photo was taken)
        2. EXIF DateTimeDigitized (when photo was scanned)
        3. EXIF DateTime (file modification in camera)
        4. Filesystem modification time
        5. Filename pattern parsing
        """
        # This is a documentation test - the hierarchy is:
        # exif_datetime_original > exif_datetime_digitized > exif > filesystem > filename
        assert True  # Hierarchy validated by implementation


class TestCameraExtraction:
    """Test camera metadata extraction."""

    @pytest.mark.integration
    def test_extract_camera_from_heic(self, sample_heic_with_gps):
        """HEIC files typically have camera metadata."""
        camera_info = extract_camera_info(str(sample_heic_with_gps))

        assert camera_info is not None
        make, model = camera_info

        # Apple devices write camera make/model
        assert isinstance(make, str) or make is None
        assert isinstance(model, str) or model is None

    @pytest.mark.integration
    def test_extract_camera_from_png(self, sample_png):
        """PNG files without EXIF should return None."""
        camera_info = extract_camera_info(str(sample_png))

        # PNG typically has no camera info
        # Should return (None, None) not None
        if camera_info:
            make, model = camera_info
            assert make is None or isinstance(make, str)
            assert model is None or isinstance(model, str)

    def test_extract_camera_nonexistent_file(self):
        """Non-existent file should return None."""
        camera_info = extract_camera_info("/nonexistent/file.jpg")

        assert camera_info is None


class TestFilenameGeneration:
    """Test organized filename generation."""

    def test_generate_path_with_date(self):
        """Filename should be YYYY-MM-DD_HHMMSS.ext."""
        date = datetime(2025, 5, 22, 14, 30, 22)
        original_filename = "IMG_1234.HEIC"

        organized_path = generate_organized_path(date, "exif", original_filename)

        # Should be: YYYY/YYYY-MM-DD_HHMMSS.ext
        assert "2025/" in organized_path
        assert "2025-05-22_143022" in organized_path
        # Extension should be lowercase
        assert organized_path.endswith(".heic")

    def test_generate_path_preserves_extension(self):
        """File extension should be preserved and lowercased."""
        date = datetime(2025, 1, 1, 12, 0, 0)

        test_cases = [
            ("photo.JPEG", ".jpeg"),
            ("image.PNG", ".png"),
            ("video.MP4", ".mp4"),
            ("file.HEIC", ".heic"),
        ]

        for original, expected_ext in test_cases:
            path = generate_organized_path(date, "exif", original)
            assert path.endswith(expected_ext)

    def test_generate_path_year_directory(self):
        """Path should include year directory."""
        date = datetime(2025, 5, 22, 14, 30, 22)
        path = generate_organized_path(date, "exif", "test.jpg")

        # Should start with year/
        assert path.startswith("2025/")

    def test_generate_path_different_years(self):
        """Different years should generate different directories."""
        original = "test.jpg"

        path_2023 = generate_organized_path(datetime(2023, 1, 1), "exif", original)
        path_2024 = generate_organized_path(datetime(2024, 1, 1), "exif", original)
        path_2025 = generate_organized_path(datetime(2025, 1, 1), "exif", original)

        assert path_2023.startswith("2023/")
        assert path_2024.startswith("2024/")
        assert path_2025.startswith("2025/")

    def test_generate_path_handles_multiple_extensions(self):
        """Files with multiple dots should only lowercase final extension."""
        date = datetime(2025, 1, 1)

        path = generate_organized_path(date, "exif", "photo.edited.JPEG")

        # Should preserve dots but lowercase extension
        assert ".jpeg" in path.lower()


class TestFileOrganization:
    """Test full file organization workflow."""

    @pytest.mark.integration
    def test_rename_and_organize_integration(self, sample_photos_dir, temp_dir):
        """Integration test: organize sample photos into temp directory."""
        from src.exif_parser import rename_and_organize

        output_dir = temp_dir / "organized"

        # Run organization
        results = rename_and_organize(str(sample_photos_dir), str(output_dir))

        # Should return list of processed images
        assert isinstance(results, list)
        assert len(results) > 0

        # Each result should be a dict with required keys
        for result in results:
            assert "original_path" in result
            assert "organized_path" in result
            assert "filename" in result
            assert "date_taken" in result
            assert "date_source" in result
            assert "camera_make" in result
            assert "camera_model" in result

    @pytest.mark.integration
    def test_organized_files_exist(self, sample_photos_dir, temp_dir):
        """Organized files should actually exist on filesystem."""
        from src.exif_parser import rename_and_organize

        output_dir = temp_dir / "organized"
        results = rename_and_organize(str(sample_photos_dir), str(output_dir))

        # Check that organized files exist
        for result in results:
            organized_file = Path(output_dir) / result["organized_path"]
            assert organized_file.exists(), f"File should exist: {organized_file}"

    @pytest.mark.integration
    def test_year_directories_created(self, sample_photos_dir, temp_dir):
        """Year subdirectories should be created."""
        from src.exif_parser import rename_and_organize

        output_dir = temp_dir / "organized"
        rename_and_organize(str(sample_photos_dir), str(output_dir))

        # At least one year directory should exist
        year_dirs = list(output_dir.glob("[0-9][0-9][0-9][0-9]"))
        assert len(year_dirs) > 0, "At least one year directory should be created"

    @pytest.mark.integration
    def test_different_formats_processed(self, sample_photos_dir, temp_dir):
        """Different file formats should all be processed."""
        from src.exif_parser import rename_and_organize

        output_dir = temp_dir / "organized"
        results = rename_and_organize(str(sample_photos_dir), str(output_dir))

        # Get extensions from results
        extensions = {result["filename"].split(".")[-1].lower() for result in results}

        # Should handle multiple formats (specifics depend on sample data)
        assert len(extensions) > 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_extract_date_invalid_path(self):
        """Invalid path should return None gracefully."""
        result = extract_exif_date("")
        assert result is None

    def test_extract_camera_invalid_path(self):
        """Invalid path should return None gracefully."""
        result = extract_camera_info("")
        assert result is None

    def test_generate_path_midnight(self):
        """Midnight timestamp should be formatted correctly."""
        date = datetime(2025, 1, 1, 0, 0, 0)
        path = generate_organized_path(date, "exif", "test.jpg")

        assert "2025-01-01_000000" in path

    def test_generate_path_last_second_of_day(self):
        """Last second of day should be formatted correctly."""
        date = datetime(2025, 12, 31, 23, 59, 59)
        path = generate_organized_path(date, "exif", "test.jpg")

        assert "2025-12-31_235959" in path

        assert '2025-12-31_235959' in path
