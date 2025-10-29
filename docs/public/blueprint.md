# PHOTO SOVEREIGNTY PIPELINE

**Architectural Specification & Implementation Guide**

## PROJECT OVERVIEW

**Purpose**: Local ML-powered photo organization pipeline that replicates cloud-level search capabilities (iCloud, Google Photos) while maintaining complete data sovereignty.

**Core Problem**: Apple’s privacy export provides raw photos with EXIF metadata but no searchable index. Users lose ML-powered search (object detection, semantic queries, text recognition) when leaving cloud ecosystems.

**Solution**: Build incremental processing pipeline using state-of-the-art open-source computer vision models, storing results in portable SQLite database for fast querying.

-----

## TECH STACK (FINAL)

| Component        | Tool                  | Purpose                                         |
| ---------------- | --------------------- | ----------------------------------------------- |
| Language         | Python 3.10+          | Primary implementation                          |
| EXIF Parsing     | Pillow + pillow-heif  | Extract metadata, handle HEIC                   |
| Object Detection | YOLOv8m (Ultralytics) | Fast 80-class detection (dogs, people, cars)    |
| Semantic Search  | OpenCLIP ViT-L/14     | Flexible concept queries (cactus, pasta, vibes) |
| Text Extraction  | EasyOCR               | OCR for text in images                          |
| Database         | SQLite3               | Metadata storage and queries                    |
| Vector Search    | numpy + scipy         | Cosine similarity for embeddings                |
| CLI              | argparse              | Command-line interface                          |

**Hardware Target**: RTX 3080 (12GB VRAM) or equivalent

-----

## DATABASE SCHEMA

```sql
-- Core images table
CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_path TEXT NOT NULL,
    organized_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    date_taken DATETIME NOT NULL,
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    camera_model TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- GPS coordinates
CREATE TABLE locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    altitude REAL,
    FOREIGN KEY (image_id) REFERENCES images(id)
);

-- YOLO object detection results
CREATE TABLE object_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    class_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    bbox_x INTEGER,
    bbox_y INTEGER,
    bbox_width INTEGER,
    bbox_height INTEGER,
    FOREIGN KEY (image_id) REFERENCES images(id)
);

CREATE INDEX idx_object_class ON object_tags(class_name);
CREATE INDEX idx_object_confidence ON object_tags(confidence);

-- CLIP semantic embeddings (768 dimensions for ViT-L/14)
CREATE TABLE embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    embedding BLOB NOT NULL,  -- numpy array as bytes
    model_version TEXT NOT NULL,
    FOREIGN KEY (image_id) REFERENCES images(id)
);

-- OCR text extraction
CREATE TABLE image_text (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL,
    text_content TEXT NOT NULL,
    confidence REAL NOT NULL,
    bbox_x INTEGER,
    bbox_y INTEGER,
    bbox_width INTEGER,
    bbox_height INTEGER,
    FOREIGN KEY (image_id) REFERENCES images(id)
);

CREATE VIRTUAL TABLE image_text_fts USING fts5(text_content, content=image_text);

-- Processing status tracking
CREATE TABLE processing_status (
    image_id INTEGER PRIMARY KEY,
    exif_processed BOOLEAN DEFAULT 0,
    gps_processed BOOLEAN DEFAULT 0,
    yolo_processed BOOLEAN DEFAULT 0,
    clip_processed BOOLEAN DEFAULT 0,
    ocr_processed BOOLEAN DEFAULT 0,
    FOREIGN KEY (image_id) REFERENCES images(id)
);
```

-----

## PROJECT STRUCTURE

```
photo-sovereignty/
├── README.md
├── requirements.txt
├── .gitignore
├── config.yaml                 # User-configurable settings
├── main.py                     # CLI entry point
├── src/
│   ├── __init__.py
│   ├── database.py             # SQLite operations
│   ├── exif_parser.py          # Stage 1: EXIF extraction
│   ├── gps_extractor.py        # Stage 2: GPS parsing
│   ├── object_detector.py      # Stage 3: YOLO pipeline
│   ├── semantic_embedder.py    # Stage 4: CLIP embeddings
│   ├── text_extractor.py       # Stage 5: OCR pipeline
│   └── query_engine.py         # Search interface
├── tests/
│   ├── test_exif.py
│   ├── test_gps.py
│   ├── test_yolo.py
│   ├── test_clip.py
│   └── test_ocr.py
└── examples/
    ├── sample_queries.py
    └── batch_export.py
```

-----

## COMPONENT SPECIFICATIONS

### STAGE 1: EXIF Parser (`exif_parser.py`)

**Input**: Raw photo export (ZIP files with random filenames)
**Output**: Renamed files in date hierarchy + database entries
**Dependencies**: Pillow, pillow-heif

**File Organization Pattern**:

```
output/
├── 2023/
│   ├── 2023-08-15_143052.jpg
│   ├── 2023-08-15_143127.jpg
│   └── ...
├── 2024/
│   └── ...
```

**Filename Format**: `YYYY-MM-DD_HHMMSS.{ext}`

**Key Functions**:

- `extract_exif_date(path)` → datetime
- `extract_camera_info(path)` → dict
- `rename_and_organize(source_dir, dest_dir)` → list of processed files
- `insert_image_metadata(db, image_data)` → image_id

**Testing Criteria**:

- Process 100 sample images successfully
- Verify dates match original EXIF
- Handle missing EXIF gracefully (fallback to file mtime)
- Support HEIC, JPEG, PNG formats

-----

### STAGE 2: GPS Extractor (`gps_extractor.py`)

**Input**: Image file paths from database
**Output**: Coordinates in locations table
**Dependencies**: Pillow

**Key Functions**:

- `extract_gps_coords(path)` → (lat, lon, alt) or None
- `convert_to_degrees(dms_tuple)` → float
- `batch_extract_gps(image_ids)` → dict mapping image_id to coords
- `insert_locations(db, location_data)` → success count

**Testing Criteria**:

- Extract GPS from 50 test images with known locations
- Verify coordinates accurate to 0.0001° (~10m)
- Handle images without GPS gracefully
- Process 10,000 images in <5 minutes

-----

### STAGE 3: Object Detector (`object_detector.py`)

**Input**: Image file paths from database
**Output**: Object tags in object_tags table
**Dependencies**: ultralytics (YOLOv8)

**Model**: YOLOv8m (medium variant)
**Classes**: 80 COCO classes (person, dog, cat, car, etc.)

**Key Functions**:

- `load_yolo_model(device='cuda')` → model
- `detect_objects(model, image_path, conf_threshold=0.5)` → list of detections
- `batch_detect(model, image_ids, batch_size=32)` → dict of results
- `insert_object_tags(db, tag_data)` → success count

**Processing Strategy**:

- Batch size: 32 images
- Confidence threshold: 0.5 (adjustable)
- GPU optimization: FP16 inference
- Expected throughput: 100-150 images/second on RTX 3080

**Testing Criteria**:

- Detect dogs in 20 sample dog photos (>95% accuracy)
- Process 1,000 images without crashes
- GPU memory usage <10GB
- Verify bounding boxes valid

-----

### STAGE 4: Semantic Embedder (`semantic_embedder.py`)

**Input**: Image file paths from database
**Output**: 768-dim vectors in embeddings table
**Dependencies**: open_clip, torch

**Model**: OpenCLIP ViT-L/14 (laion2b_s32b_b82k)
**Embedding Dimension**: 768

**Key Functions**:

- `load_clip_model(device='cuda')` → (model, preprocess)
- `generate_embedding(model, image_path)` → numpy array (768,)
- `batch_embed(model, image_ids, batch_size=64)` → dict of embeddings
- `insert_embeddings(db, embedding_data)` → success count
- `search_by_text(db, text_query, top_k=20)` → list of (image_id, similarity)

**Processing Strategy**:

- Batch size: 64 images
- Store as numpy array → bytes → BLOB
- Expected throughput: 20-30 images/second on RTX 3080

**Testing Criteria**:

- Generate embeddings for 100 test images
- Query “dog” returns images with dogs in top 10
- Query “cactus” returns cactus photos
- Cosine similarity calculations correct

-----

### STAGE 5: Text Extractor (`text_extractor.py`)

**Input**: Image file paths from database
**Output**: OCR text in image_text table + FTS index
**Dependencies**: easyocr

**Model**: EasyOCR English reader

**Key Functions**:

- `load_ocr_reader(languages=['en'])` → reader
- `extract_text(reader, image_path, conf_threshold=0.5)` → list of text detections
- `batch_ocr(reader, image_ids)` → dict of text results
- `insert_text_data(db, text_data)` → success count

**Processing Strategy**:

- Single image processing (EasyOCR doesn’t batch well)
- Skip images with YOLO tag “text” missing (optimization)
- Confidence threshold: 0.5

**Testing Criteria**:

- Extract “Bruno” from book cover photo
- Extract visible text from 20 test images
- Full-text search returns correct images
- Process 1,000 images in <30 minutes

-----

### STAGE 6: Query Engine (`query_engine.py`)

**Input**: User queries (text, filters, combinations)
**Output**: Ranked list of image paths

**Query Types**:

1. **Object Query**: `--object dog` → SQL filter on object_tags
2. **Semantic Query**: `--search "cactus collection"` → CLIP similarity
3. **Text Query**: `--text "bruno"` → FTS on image_text
4. **Location Query**: `--location "melbourne" --radius 10km` → GPS filter
5. **Date Query**: `--date-from 2023-08-01 --date-to 2023-08-31`
6. **Combined Query**: `--object dog --location glenlyon` → Multi-filter

**Key Functions**:

- `query_by_objects(db, class_names, min_confidence=0.5)`
- `query_by_semantics(db, text, top_k=20)`
- `query_by_text(db, text_search)`
- `query_by_location(db, lat, lon, radius_km)`
- `query_by_date_range(db, start_date, end_date)`
- `combine_queries(db, filters)` → unified results

**Testing Criteria**:

- Each query type returns expected results
- Combined queries work correctly
- Results ranked by relevance
- Query performance <1 second for 50k image database

-----

## IMPLEMENTATION TIMELINE

### Week 1: Foundation & EXIF

**Goal**: Rename and organize photos with database tracking

**Tasks**:

1. Set up project structure
2. Create SQLite schema
3. Implement `exif_parser.py`
4. Implement `database.py` core functions
5. Write tests for EXIF extraction
6. Process 1,000 sample images

**Deliverable**: Organized photo archive with dates in database

**Validation**: Manual spot-check 50 renamed files match original dates

-----

### Week 2: GPS Extraction

**Goal**: Add location data to database

**Tasks**:

1. Implement `gps_extractor.py`
2. Add location insertion to database module
3. Write GPS extraction tests
4. Process all organized photos for GPS
5. Verify coordinates on map (sample check)

**Deliverable**: Location data for all photos with GPS

**Validation**: Query “photos within 5km of [known location]” returns correct subset

-----

### Week 3: Object Detection

**Goal**: Tag all photos with YOLO detections

**Tasks**:

1. Install ultralytics, download YOLOv8m
2. Implement `object_detector.py`
3. Optimize batch processing for GPU
4. Write object detection tests
5. Process full archive (expect 4-6 hours for 50k images)
6. Analyze tag distribution (how many dogs/people/cars?)

**Deliverable**: Object tags for all images

**Validation**: Query “all photos with dogs” returns expected results

-----

### Week 4: Semantic Embeddings

**Goal**: Enable natural language search

**Tasks**:

1. Install open_clip, download ViT-L/14 model
2. Implement `semantic_embedder.py`
3. Optimize batch processing
4. Write embedding generation tests
5. Process full archive (expect 8-10 hours for 50k images)
6. Test similarity search on sample queries

**Deliverable**: CLIP embeddings for all images

**Validation**: Query “cactus” and “pasta” return relevant photos

-----

### Week 5: Text Extraction

**Goal**: Enable text-based search

**Tasks**:

1. Install easyocr
2. Implement `text_extractor.py`
3. Set up FTS5 full-text search
4. Write OCR tests
5. Process subset of images (photos with visible text)
6. Optimize: only OCR images YOLO tagged with “book”, “sign”, etc.

**Deliverable**: Text index for searchable images

**Validation**: Query “bruno” returns book cover photo

-----

### Week 6: Query Interface & CLI

**Goal**: Unified search interface

**Tasks**:

1. Implement `query_engine.py`
2. Build CLI with argparse
3. Add combined query logic
4. Write query tests
5. Create example queries documentation
6. Performance optimization (indexing, caching)

**Deliverable**: Working CLI for all query types

**Validation**: Run 10 diverse queries, verify results make sense

-----

### Week 7: Polish & Documentation

**Goal**: Portfolio-ready project

**Tasks**:

1. Comprehensive README with architecture diagrams
2. Usage examples and screenshots
3. Performance benchmarks document
4. Add error handling and logging
5. Code cleanup and comments
6. GitHub repository setup

**Deliverable**: Public GitHub project

-----

## CLI INTERFACE DESIGN

```bash
# Initialize database from photo export
python main.py init --source /path/to/apple_export/ --output /path/to/organized/

# Process specific stages
python main.py process --stage exif --input /path/to/photos/
python main.py process --stage gps
python main.py process --stage yolo --device cuda
python main.py process --stage clip --batch-size 64
python main.py process --stage ocr

# Run all stages (full pipeline)
python main.py process --all

# Query interface
python main.py search --object dog
python main.py search --semantic "cactus collection"
python main.py search --text "bruno"
python main.py search --location "melbourne" --radius 10km
python main.py search --date-from 2023-08-01 --date-to 2023-08-31

# Combined queries
python main.py search --object dog --location glenlyon
python main.py search --semantic "happy dogs at beach" --date-from 2024-01-01

# Export results
python main.py search --object dog --export results.json
python main.py search --semantic "pasta" --export pasta_photos.csv --copy-to /output/
```

-----

## TESTING STRATEGY

**Unit Tests**: Each module independently
**Integration Tests**: Database operations with real files
**Performance Tests**: Benchmark on 1k, 10k, 50k images
**Accuracy Tests**: Manual verification of ML outputs

**Test Dataset Structure**:

```
tests/fixtures/
├── sample_photos/
│   ├── has_dog.jpg          # Known dog photo
│   ├── has_cactus.jpg       # Known cactus photo
│   ├── book_cover.jpg       # Text: "Bruno"
│   ├── with_gps.jpg         # Known coordinates
│   └── no_metadata.jpg      # Edge case
```

-----

## PERFORMANCE TARGETS

|Metric         |Target            |Hardware    |
|---------------|------------------|------------|
|EXIF extraction|500 images/sec    |CPU         |
|GPS extraction |500 images/sec    |CPU         |
|YOLO detection |100-150 images/sec|RTX 3080    |
|CLIP embedding |20-30 images/sec  |RTX 3080    |
|OCR extraction |2-3 images/sec    |RTX 3080    |
|Query latency  |<1 sec            |50k image DB|
|Database size  |~200MB            |50k images  |

**Total Processing Time (50k images)**:

- EXIF: 2 minutes
- GPS: 2 minutes
- YOLO: 6 hours
- CLIP: 10 hours
- OCR: 6 hours (selective)
- **Total: ~22 hours** (run overnight)

-----

## PORTFOLIO POSITIONING

**Title**: “Photo Sovereignty: Local-First Computer Vision Pipeline”

**Key Highlights**:

- Replaces iCloud/Google Photos ML features with local processing
- Privacy-preserving: all data stays on user hardware
- State-of-the-art CV models: YOLOv8, OpenCLIP, EasyOCR
- Portable SQLite database (no server required)
- GPU-optimized batch processing
- Natural language semantic search

**Technical Depth**:

- Deep learning inference optimization
- Database schema design for multi-modal search
- Vector similarity search implementation
- ETL pipeline for large-scale image processing
- CLI interface design

**Use Case Differentiation**:

- Not a photo viewer (Immich, PhotoPrism do this)
- Not cloud backup (Nextcloud does this)
- **Focused problem**: “I want ML search without cloud lock-in”

-----

## DEPENDENCIES (`requirements.txt`)

```
# Core
Pillow>=10.0.0
pillow-heif>=0.13.0
numpy>=1.24.0
scipy>=1.11.0

# Computer Vision
ultralytics>=8.0.0
open-clip-torch>=2.20.0
easyocr>=1.7.0

# Utilities
PyYAML>=6.0
tqdm>=4.65.0
```

-----

## CONFIG FILE EXAMPLE (`config.yaml`)

```yaml
# Hardware
device: cuda  # cuda, cpu, mps
gpu_memory_limit: 10  # GB

# Processing
batch_sizes:
  yolo: 32
  clip: 64
  ocr: 1

confidence_thresholds:
  yolo: 0.5
  ocr: 0.5

# Models
models:
  yolo: yolov8m.pt
  clip: ViT-L-14
  clip_pretrained: laion2b_s32b_b82k
  ocr_languages: [en]

# Database
database_path: ./photo_archive.db

# File organization
output_structure: YYYY/YYYY-MM-DD_HHMMSS.ext
supported_formats: [.jpg, .jpeg, .heic, .png, .mov, .mp4]
```

-----

## CRITICAL SUCCESS FACTORS

1. **Incremental validation**: Test each stage on small subset before full processing
2. **Checkpoint resume**: If processing crashes, resume from last checkpoint
3. **Error logging**: Track which images fail at each stage and why
4. **Performance monitoring**: Log processing times to identify bottlenecks
5. **Explainability**: Store confidence scores and model versions for debugging

-----

## FUTURE ENHANCEMENTS (Post-v1.0)

- **Face recognition**: Add face detection and clustering
- **Duplicate detection**: Perceptual hashing to find similar images
- **Web UI**: Flask/FastAPI interface for non-technical users
- **Incremental processing**: Efficiently handle new photos without reprocessing archive
- **Cloud backup**: Optional encrypted backup to S3/Backblaze
- **Mobile companion**: Export subset for phone access

-----

**END OF SPECIFICATION**

*This document serves as architectural reference for implementation. Each component is independently testable. Follow the week-by-week timeline for systematic progress. The project is complete when all query types return accurate results on your full photo archive.*