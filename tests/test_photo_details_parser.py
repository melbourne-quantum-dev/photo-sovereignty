"""Tests for iCloud Photo Details parser.

Tests cover:
- iCloud date format parsing
- CSV loading and filename lookup
- Multi-part CSV consolidation
- Error handling (missing files, malformed data)

Testing Philosophy:
    These tests validate the Photo Details integration workflow using
    real-world iCloud CSV formats and edge cases from actual exports.
"""

import csv
from datetime import datetime
from pathlib import Path

import pytest

from src.photo_details_parser import (
    consolidate_csvs,
    load_photo_details,
    parse_icloud_date,
)


class TestiCloudDateParsing:
    """Test iCloud date format parsing."""

    def test_parse_standard_icloud_date(self):
        """Parse standard iCloud format with AM/PM."""
        date_str = "Friday July 4,2025 3:46 AM GMT"
        result = parse_icloud_date(date_str)

        assert result == datetime(2025, 7, 4, 3, 46)

    def test_parse_icloud_date_pm(self):
        """Parse iCloud date with PM time."""
        date_str = "Monday December 25,2023 11:30 PM GMT"
        result = parse_icloud_date(date_str)

        assert result == datetime(2023, 12, 25, 23, 30)

    def test_parse_icloud_date_noon(self):
        """Parse iCloud date at noon."""
        date_str = "Saturday January 1,2025 12:00 PM GMT"
        result = parse_icloud_date(date_str)

        assert result == datetime(2025, 1, 1, 12, 0)

    def test_parse_icloud_date_midnight(self):
        """Parse iCloud date at midnight."""
        date_str = "Sunday June 15,2024 12:00 AM GMT"
        result = parse_icloud_date(date_str)

        assert result == datetime(2024, 6, 15, 0, 0)

    def test_parse_empty_string(self):
        """Empty string should return None."""
        assert parse_icloud_date("") is None
        assert parse_icloud_date(None) is None

    def test_parse_malformed_date(self):
        """Malformed date string should return None gracefully."""
        assert parse_icloud_date("not a date") is None
        assert parse_icloud_date("2025-07-04 15:30") is None  # Wrong format


class TestPhotoDetailsLoading:
    """Test loading Photo Details CSV files."""

    def test_load_photo_details_basic(self, temp_dir):
        """Load basic Photo Details CSV."""
        csv_path = temp_dir / "photo_details.csv"

        # Create sample CSV
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "filename": "IMG_1234.HEIC",
                    "originalCreationDate": "Friday July 4,2025 3:46 AM GMT",
                    "fileChecksum": "abc123",
                }
            )

        # Load and validate
        details = load_photo_details(csv_path)

        assert "IMG_1234.HEIC" in details
        assert details["IMG_1234.HEIC"]["date"] == datetime(2025, 7, 4, 3, 46)
        assert details["IMG_1234.HEIC"]["checksum"] == "abc123"

    def test_load_photo_details_multiple_rows(self, temp_dir):
        """Load CSV with multiple photos."""
        csv_path = temp_dir / "photo_details.csv"

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerows(
                [
                    {
                        "filename": "IMG_1001.HEIC",
                        "originalCreationDate": "Monday January 1,2025 10:00 AM GMT",
                        "fileChecksum": "hash1",
                    },
                    {
                        "filename": "IMG_1002.HEIC",
                        "originalCreationDate": "Tuesday January 2,2025 2:30 PM GMT",
                        "fileChecksum": "hash2",
                    },
                    {
                        "filename": "IMG_1003.HEIC",
                        "originalCreationDate": "Wednesday January 3,2025 11:45 PM GMT",
                        "fileChecksum": "hash3",
                    },
                ]
            )

        details = load_photo_details(csv_path)

        assert len(details) == 3
        assert details["IMG_1001.HEIC"]["date"] == datetime(2025, 1, 1, 10, 0)
        assert details["IMG_1002.HEIC"]["date"] == datetime(2025, 1, 2, 14, 30)
        assert details["IMG_1003.HEIC"]["date"] == datetime(2025, 1, 3, 23, 45)

    def test_load_photo_details_missing_date(self, temp_dir):
        """Handle rows with missing dates gracefully."""
        csv_path = temp_dir / "photo_details.csv"

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "filename": "Screenshot_1234.png",
                    "originalCreationDate": "",  # Missing date
                    "fileChecksum": "xyz789",
                }
            )

        details = load_photo_details(csv_path)

        assert "Screenshot_1234.png" in details
        assert details["Screenshot_1234.png"]["date"] is None
        assert details["Screenshot_1234.png"]["checksum"] == "xyz789"

    def test_load_photo_details_malformed_date(self, temp_dir):
        """Handle malformed dates gracefully."""
        csv_path = temp_dir / "photo_details.csv"

        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "filename": "IMG_5678.HEIC",
                    "originalCreationDate": "invalid date format",
                    "fileChecksum": "def456",
                }
            )

        details = load_photo_details(csv_path)

        assert "IMG_5678.HEIC" in details
        assert details["IMG_5678.HEIC"]["date"] is None

    def test_load_nonexistent_file(self, temp_dir):
        """Non-existent file should return empty dict."""
        csv_path = temp_dir / "nonexistent.csv"
        details = load_photo_details(csv_path)

        assert details == {}

    def test_load_empty_csv(self, temp_dir):
        """Empty CSV should return empty dict."""
        csv_path = temp_dir / "empty.csv"
        csv_path.write_text("")

        details = load_photo_details(csv_path)

        assert details == {}


class TestCSVConsolidation:
    """Test consolidating multiple Photo Details CSVs."""

    def test_consolidate_two_csvs(self, temp_dir):
        """Consolidate two CSV files."""
        csv1 = temp_dir / "part1.csv"
        csv2 = temp_dir / "part2.csv"
        output = temp_dir / "consolidated.csv"

        # Create first CSV
        with open(csv1, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "filename": "IMG_1001.HEIC",
                    "originalCreationDate": "Monday January 1,2025 10:00 AM GMT",
                    "fileChecksum": "hash1",
                }
            )

        # Create second CSV
        with open(csv2, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "filename": "IMG_2001.HEIC",
                    "originalCreationDate": "Tuesday January 2,2025 2:30 PM GMT",
                    "fileChecksum": "hash2",
                }
            )

        # Consolidate
        result_path = consolidate_csvs([csv1, csv2], output)

        assert result_path == output
        assert output.exists()

        # Verify consolidated content
        details = load_photo_details(output)
        assert len(details) == 2
        assert "IMG_1001.HEIC" in details
        assert "IMG_2001.HEIC" in details

    def test_consolidate_with_duplicates(self, temp_dir):
        """Duplicates should be deduplicated (last occurrence wins)."""
        csv1 = temp_dir / "part1.csv"
        csv2 = temp_dir / "part2.csv"
        output = temp_dir / "consolidated.csv"

        # First CSV with IMG_1001
        with open(csv1, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "filename": "IMG_1001.HEIC",
                    "originalCreationDate": "Monday January 1,2025 10:00 AM GMT",
                    "fileChecksum": "old_hash",
                }
            )

        # Second CSV with same IMG_1001 (newer data)
        with open(csv2, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "filename": "IMG_1001.HEIC",
                    "originalCreationDate": "Monday January 1,2025 10:00 AM GMT",
                    "fileChecksum": "new_hash",  # Updated checksum
                }
            )

        # Consolidate
        consolidate_csvs([csv1, csv2], output)

        # Verify last occurrence won
        details = load_photo_details(output)
        assert len(details) == 1
        assert details["IMG_1001.HEIC"]["checksum"] == "new_hash"

    def test_consolidate_empty_list(self, temp_dir):
        """Empty CSV list should raise ValueError."""
        output = temp_dir / "output.csv"

        with pytest.raises(ValueError, match="csv_paths cannot be empty"):
            consolidate_csvs([], output)

    def test_consolidate_none_output(self, temp_dir):
        """None output path should raise ValueError."""
        csv1 = temp_dir / "part1.csv"
        csv1.write_text("filename,date\nIMG_1.jpg,2025-01-01\n")

        with pytest.raises(ValueError, match="output_path must be specified"):
            consolidate_csvs([csv1], None)

    def test_consolidate_skip_missing_files(self, temp_dir):
        """Missing files in list should be skipped gracefully."""
        csv1 = temp_dir / "exists.csv"
        csv2 = temp_dir / "missing.csv"  # Doesn't exist
        output = temp_dir / "output.csv"

        # Create only first CSV
        with open(csv1, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "filename": "IMG_1001.HEIC",
                    "originalCreationDate": "Monday January 1,2025 10:00 AM GMT",
                    "fileChecksum": "hash1",
                }
            )

        # Consolidate (should skip missing file)
        consolidate_csvs([csv1, csv2], output)

        # Verify only first CSV's data is present
        details = load_photo_details(output)
        assert len(details) == 1
        assert "IMG_1001.HEIC" in details


class TestIntegration:
    """Integration tests for Photo Details workflow."""

    def test_full_workflow_consolidate_and_load(self, temp_dir):
        """Complete workflow: consolidate multiple CSVs then load."""
        # Create multi-part export scenario
        part1 = temp_dir / "export1" / "Photo Details.csv"
        part2 = temp_dir / "export2" / "Photo Details.csv"
        part1.parent.mkdir(parents=True)
        part2.parent.mkdir(parents=True)

        # Part 1 CSV
        with open(part1, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerows(
                [
                    {
                        "filename": "IMG_1001.HEIC",
                        "originalCreationDate": "Monday January 1,2025 10:00 AM GMT",
                        "fileChecksum": "hash1",
                    },
                    {
                        "filename": "IMG_1002.HEIC",
                        "originalCreationDate": "Tuesday January 2,2025 2:30 PM GMT",
                        "fileChecksum": "hash2",
                    },
                ]
            )

        # Part 2 CSV
        with open(part2, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["filename", "originalCreationDate", "fileChecksum"]
            )
            writer.writeheader()
            writer.writerows(
                [
                    {
                        "filename": "IMG_2001.HEIC",
                        "originalCreationDate": "Wednesday January 3,2025 11:00 AM GMT",
                        "fileChecksum": "hash3",
                    },
                    {
                        "filename": "Screenshot_1234.png",
                        "originalCreationDate": "Thursday January 4,2025 4:15 PM GMT",
                        "fileChecksum": "hash4",
                    },
                ]
            )

        # Consolidate
        output = temp_dir / "consolidated.csv"
        consolidate_csvs([part1, part2], output)

        # Load and verify
        details = load_photo_details(output)

        assert len(details) == 4
        assert details["IMG_1001.HEIC"]["date"] == datetime(2025, 1, 1, 10, 0)
        assert details["IMG_1002.HEIC"]["date"] == datetime(2025, 1, 2, 14, 30)
        assert details["IMG_2001.HEIC"]["date"] == datetime(2025, 1, 3, 11, 0)
        assert details["Screenshot_1234.png"]["date"] == datetime(2025, 1, 4, 16, 15)
