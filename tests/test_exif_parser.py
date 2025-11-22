"""Tests for EXIF extraction and file organization.

Tests cover:
- EXIF date extraction hierarchy
- Camera metadata extraction
- File organization into year directories
- Handling various file formats (HEIC, JPEG, PNG)
- Fallback date extraction (filesystem, filename)

Testing Philosophy:
    These tests use the public API (extract_exif_date, extract_camera_info,
    rename_and_organize) with REAL image files. This approach:

    1. Tests actual production workflow (not synthetic test data)
    2. Validates behavior with real EXIF data from various cameras
    3. More resilient to implementation changes
    4. Matches how the code is used in examples/stage1_process_photos.py

    The generate_organized_path() function returns Path objects (not strings),
    so tests use str() conversion or Path methods for assertions.

Version: v0.1.0
"""

from datetime import datetime
from pathlib import Path

import pytest

from src.exif_parser import extract_camera_info, extract_exif_date
from src.organize import generate_organized_path, rename_and_organize


class TestExifDateExtraction:
    """Test EXIF date extraction with real image files."""

    @pytest.mark.integration
    def test_extract_date_from_sample_images(self, sample_photos_dir):
        """Extract dates from all sample images, validate when present.

        Tests the REAL workflow:
        1. Read actual image files from disk
        2. Extract date using public API (extract_exif_date)
        3. Validate date is datetime object when present

        Some images may not have EXIF dates (fallback to filesystem).
        """
        photo_files = list(sample_photos_dir.glob("*.*"))
        photo_files = [
            f
            for f in photo_files
            if f.suffix.lower() in [".heic", ".jpeg", ".jpg", ".png"]
        ]

        assert len(photo_files) > 0, "Need at least one sample image"

        for photo in photo_files:
            date_info = extract_exif_date(str(photo))

            if date_info:
                date, source = date_info
                assert isinstance(date, datetime), "Date should be datetime object"
                # All possible date sources from extract_exif_date()
                valid_sources = [
                    "exif",
                    "exif_datetime_original",
                    "exif_datetime_digitized",
                    "exif_datetime_camera",
                    "exif_datetime_unknown",
                    "filesystem",
                    "filename",
                ]
                assert source in valid_sources, f"Unknown source: {source}"
                print(f"  ✅ {photo.name}: {date} (source: {source})")
            else:
                print(f"  ⏭️  {photo.name}: No date extracted")

    @pytest.mark.integration
    def test_extract_date_from_heic(self, sample_photos_dir):
        """HEIC files typically have EXIF date metadata."""
        heic_files = list(sample_photos_dir.glob("*.HEIC")) + list(
            sample_photos_dir.glob("*.heic")
        )

        if not heic_files:
            pytest.skip("No HEIC files in sample data")

        for heic in heic_files[:3]:
            date_info = extract_exif_date(str(heic))

            # Should return date info (HEIC files typically have EXIF)
            if date_info:
                date, source = date_info
                assert isinstance(date, datetime)

    @pytest.mark.integration
    def test_extract_date_from_jpeg(self, sample_photos_dir):
        """JPEG files may have EXIF date metadata."""
        jpeg_files = (
            list(sample_photos_dir.glob("*.JPEG"))
            + list(sample_photos_dir.glob("*.jpeg"))
            + list(sample_photos_dir.glob("*.JPG"))
            + list(sample_photos_dir.glob("*.jpg"))
        )

        if not jpeg_files:
            pytest.skip("No JPEG files in sample data")

        for jpeg in jpeg_files[:3]:
            date_info = extract_exif_date(str(jpeg))

            # May or may not have date depending on source
            if date_info:
                date, source = date_info
                assert isinstance(date, datetime)


class TestCameraExtraction:
    """Test camera metadata extraction."""

    @pytest.mark.integration
    def test_extract_camera_from_sample_images(self, sample_photos_dir):
        """Extract camera info from sample images."""
        photo_files = list(sample_photos_dir.glob("*.*"))
        photo_files = [
            f for f in photo_files if f.suffix.lower() in [".heic", ".jpeg", ".jpg"]
        ]

        for photo in photo_files[:5]:  # Test first 5 images
            camera_info = extract_camera_info(str(photo))

            if camera_info:
                make, model = camera_info
                # Strings or None
                assert make is None or isinstance(make, str)
                assert model is None or isinstance(model, str)
                print(f"  ✅ {photo.name}: {make} {model}")
            else:
                print(f"  ⏭️  {photo.name}: No camera info")


class TestFilenameGeneration:
    """Test organized filename generation.

    Note: generate_organized_path() returns Path objects, not strings.
    Tests use str() conversion or Path methods for validation.
    """

    def test_generate_path_returns_path_object(self):
        """Function should return Path object."""
        date = datetime(2025, 5, 22, 14, 30, 22)
        result = generate_organized_path(date, "exif", "IMG_1234.HEIC")

        assert isinstance(result, Path), "Should return Path object"

    def test_generate_path_with_date(self):
        """Filename should be YYYY-MM-DD_HHMMSS.ext."""
        date = datetime(2025, 5, 22, 14, 30, 22)
        original_filename = "IMG_1234.HEIC"

        organized_path = generate_organized_path(date, "exif", original_filename)
        path_str = str(organized_path)

        # Should be: YYYY/YYYY-MM-DD_HHMMSS.ext
        assert "2025/" in path_str
        assert "2025-05-22_143022" in path_str
        # Extension should be lowercase
        assert path_str.endswith(".heic")

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
            assert str(path).endswith(expected_ext)

    def test_generate_path_year_directory(self):
        """Path should include year directory."""
        date = datetime(2025, 5, 22, 14, 30, 22)
        path = generate_organized_path(date, "exif", "test.jpg")

        # Should start with year/
        assert str(path).startswith("2025/")

    def test_generate_path_different_years(self):
        """Different years should generate different directories."""
        original = "test.jpg"

        path_2023 = generate_organized_path(datetime(2023, 1, 1), "exif", original)
        path_2024 = generate_organized_path(datetime(2024, 1, 1), "exif", original)
        path_2025 = generate_organized_path(datetime(2025, 1, 1), "exif", original)

        assert str(path_2023).startswith("2023/")
        assert str(path_2024).startswith("2024/")
        assert str(path_2025).startswith("2025/")

    def test_generate_path_midnight(self):
        """Midnight timestamp should be formatted correctly."""
        date = datetime(2025, 1, 1, 0, 0, 0)
        path = generate_organized_path(date, "exif", "test.jpg")

        assert "2025-01-01_000000" in str(path)

    def test_generate_path_last_second_of_day(self):
        """Last second of day should be formatted correctly."""
        date = datetime(2025, 12, 31, 23, 59, 59)
        path = generate_organized_path(date, "exif", "test.jpg")

        assert "2025-12-31_235959" in str(path)


class TestFileOrganization:
    """Test full file organization workflow."""

    @pytest.mark.integration
    def test_rename_and_organize_integration(self, sample_photos_dir, temp_dir):
        """Integration test: organize sample photos into temp directory.

        This tests the COMPLETE workflow used in production:
        1. Read images from source directory
        2. Extract EXIF metadata
        3. Generate organized filenames
        4. Copy to organized directory structure

        Matches examples/stage1_process_photos.py
        """
        output_dir = temp_dir / "organized"

        # Run organization (same as production code)
        results = rename_and_organize(str(sample_photos_dir), str(output_dir))

        # Should return list of processed images
        assert isinstance(results, list)

        # Each result should have required keys
        for result in results:
            assert "original_path" in result
            assert "organized_path" in result or not result["processed"]
            assert "filename" in result
            assert "date_taken" in result or not result["processed"]
            assert "date_source" in result or not result["processed"]
            assert "camera_make" in result or not result["processed"]
            assert "camera_model" in result or not result["processed"]
            assert "file_type" in result
            assert "processed" in result

            # Only print processed images
            if result["processed"]:
                print(f"  ✅ {result['filename']}")

    @pytest.mark.integration
    def test_organized_files_exist(self, sample_photos_dir, temp_dir):
        """Organized files should actually exist on filesystem."""
        output_dir = temp_dir / "organized"
        results = rename_and_organize(str(sample_photos_dir), str(output_dir))

        # Check that organized files exist (only for processed images)
        for result in results:
            if result["processed"] and result["file_type"] == "image":
                organized_file = Path(result["organized_path"])
                assert organized_file.exists(), f"File should exist: {organized_file}"

    @pytest.mark.integration
    def test_year_directories_created(self, sample_photos_dir, temp_dir):
        """Year subdirectories should be created."""
        output_dir = temp_dir / "organized"
        results = rename_and_organize(str(sample_photos_dir), str(output_dir))

        if len(results) > 0:
            # At least one year directory should exist
            year_dirs = list(output_dir.glob("[0-9][0-9][0-9][0-9]"))
            assert len(year_dirs) > 0, "At least one year directory should be created"


class TestFilenamePreservation:
    """Test filename preservation strategies."""

    def test_descriptive_name_detection(self):
        """_is_descriptive_name should identify camera vs descriptive names."""
        from src.organize import _is_descriptive_name

        # Camera-generated names (should return False)
        assert not _is_descriptive_name("IMG_1234")
        assert not _is_descriptive_name("DSC01234")
        assert not _is_descriptive_name("DSCN5678")
        assert not _is_descriptive_name("20231215_143022")
        assert not _is_descriptive_name("2023-12-15_143022")
        assert not _is_descriptive_name("PXL_20231215_143022")
        assert not _is_descriptive_name("Screenshot_20231215")

        # iCloud UUID exports (should return False - auto-generated)
        assert not _is_descriptive_name("0DD028F1-1DCF-48D8-B6D4-D7861D2407F5")
        assert not _is_descriptive_name("0fe5236c-65a4-4c6d-bf41-b262781290c1")
        assert not _is_descriptive_name("9a87b2f5-d315-45bd-afa7-d115da25ab2f")

        # Pure timestamp screenshots (should return False - no context)
        assert not _is_descriptive_name("Screenshot 2025-07-06 121830")
        assert not _is_descriptive_name("Screenshot 2025-06-30 045143")
        assert not _is_descriptive_name("Screenshot 2025-07-09 at 15-34-31")

        # Pure date+time only (should return False - no description)
        assert not _is_descriptive_name("2025-09-02 200936")

        # Descriptive names (should return True)
        assert _is_descriptive_name("piazza-dei-signori")
        assert _is_descriptive_name("wedding-reception")
        assert _is_descriptive_name("birthday-party-2023")  # partial date in context
        assert _is_descriptive_name("vacation_beach")
        assert _is_descriptive_name("daisy_cow")
        assert _is_descriptive_name("dris")
        assert _is_descriptive_name("england-london-bridge")

        # Screenshots with descriptions (should return True - has context!)
        assert _is_descriptive_name("2025-09-02 200936 game build settings")
        assert _is_descriptive_name(
            "Screenshot 2025-03-29 at 18-38-44 Research Article on Machine Learning"
        )
        assert _is_descriptive_name(
            "Screenshot 2025-05-02 at 18-35-52 Music Playlist Summer Mix"
        )

    def test_preserve_descriptive_only(self):
        """Default behavior: preserve descriptive names, strip camera names."""
        from datetime import datetime

        date = datetime(2023, 6, 15, 14, 30, 22)

        # Camera name should be stripped
        camera_path = generate_organized_path(
            date, "exif_original", "IMG_1234.jpg", preserve_filenames="descriptive_only"
        )
        assert "IMG_1234" not in str(camera_path)
        assert "2023-06-15_143022.jpg" in str(camera_path)

        # Descriptive name should be preserved
        descriptive_path = generate_organized_path(
            date,
            "exif_original",
            "wedding-reception.jpg",
            preserve_filenames="descriptive_only",
        )
        assert "wedding-reception" in str(descriptive_path)
        assert "2023-06-15_143022_wedding-reception.jpg" in str(descriptive_path)

    def test_preserve_always(self):
        """preserve_filenames=True should always preserve names."""
        from datetime import datetime

        date = datetime(2023, 6, 15, 14, 30, 22)

        # Even camera names should be preserved
        path = generate_organized_path(
            date, "exif_original", "IMG_1234.jpg", preserve_filenames=True
        )
        assert "IMG_1234" in str(path)
        assert "2023-06-15_143022_IMG_1234.jpg" in str(path)

    def test_preserve_never(self):
        """preserve_filenames=False should never preserve names."""
        from datetime import datetime

        date = datetime(2023, 6, 15, 14, 30, 22)

        # Even descriptive names should be stripped
        path = generate_organized_path(
            date,
            "exif_original",
            "wedding-reception.jpg",
            preserve_filenames=False,
        )
        assert "wedding-reception" not in str(path)
        assert "2023-06-15_143022.jpg" in str(path)


class TestFilesystemDatesDirectory:
    """Test filesystem_dates directory for unreliable dates."""

    def test_filesystem_date_goes_to_filesystem_dates(self):
        """Images with filesystem dates should go to filesystem_dates/."""
        from datetime import datetime

        date = datetime(2025, 11, 23, 9, 58, 2)

        path = generate_organized_path(
            date,
            "filesystem",
            "piazza-dei-signori.jpg",
            preserve_filenames="descriptive_only",
        )

        assert "filesystem_dates" in str(path)
        assert "2025" not in str(path).split("/")[0]  # Should NOT be in year directory
        assert "piazza-dei-signori" in str(path)

    def test_exif_date_goes_to_year_directory(self):
        """Images with EXIF dates should go to YYYY/ directory."""
        from datetime import datetime

        date = datetime(2023, 6, 15, 14, 30, 22)

        path = generate_organized_path(
            date, "exif_original", "photo.jpg", preserve_filenames="descriptive_only"
        )

        assert str(path).startswith("2023/")
        assert "filesystem_dates" not in str(path)

    def test_unsorted_directory_for_no_date(self):
        """Images with no date should go to unsorted/."""
        path = generate_organized_path(None, None, "corrupted.jpg")

        assert "unsorted" in str(path)
        assert "corrupted.jpg" in str(path)
