# Photo Sovereignty Pipeline

**Status**: Early development - EXIF/GPS extraction working, object detection and semantic search in progress

Local-first ML-powered photo organization that replicates cloud service search 
capabilities (iCloud, Google Photos) while maintaining complete data sovereignty.

## Current Features

✅ EXIF metadata extraction and file organization (535 images processed)
✅ GPS coordinate extraction and storage
✅ SQLite database with incremental schema evolution
✅ Privacy-preserving architecture (local processing, no cloud APIs)

## In Progress

🚧 YOLOv8 object detection (80 COCO classes)
🚧 OpenCLIP semantic embeddings (natural language search)
🚧 EasyOCR text extraction
🚧 Unified query interface

## Technical Stack

Python 3.10+, SQLite, Pillow, YOLOv8 (pending), OpenCLIP (pending), EasyOCR (pending)

## Architecture

Three-layer design: extraction (pure functions) → persistence (database.py) 
→ orchestration (CLI scripts). Built for incremental feature addition and 
idempotent processing.

[Link to ARCHITECTURE.md for details]

## Portfolio Context

This project demonstrates legal-tech relevant capabilities:
- Privacy-preserving ML architecture
- Systematic problem-solving methodology
- Clean code boundaries and incremental development
- Relevant to legal tech applications where client data sensitivity is critical

Built using AI-augmented development methodology (standard professional practice 2025).

## License

MIT