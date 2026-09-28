# AVLOKAN

### Sovereign Semantic Earth-Observation Intelligence Platform

AVLOKAN is an on-premises satellite-imagery intelligence platform for
**semantic retrieval, multi-temporal change detection, multi-sensor
verification, discovery, and analyst review**.

It combines optical and SAR Earth-observation data with multimodal
embeddings, pixel-level change verification, spatial indexing,
provenance tracking, and an analyst-oriented review workflow.

> **Smart India Hackathon 2026 · Problem Statement SIH26227 · Space
> Technology · Software**\
> **Team:** Codenostic · **Team ID:** 171288

------------------------------------------------------------------------

## Overview

Satellite imagery archives are growing faster than analysts can manually
inspect them. AVLOKAN turns that archive into a searchable and
continuously analyzable intelligence layer.

``` text
Data Acquisition
      ↓
Ingestion & Preprocessing
      ↓
Quality Control & Co-registration
      ↓
Tiling & Metadata
      ↓
Embedding Generation
      ↓
Vector Indexing
      ↓
Semantic / Image Retrieval
      ↓
Multi-Temporal Change Detection
      ↓
Multi-Sensor Verification
      ↓
Analyst Review
      ↓
Provenance & Audit
      ↓
Incremental Improvement
```

The platform is designed for **sovereign, offline, on-premises
deployment**, where imagery, queries, metadata, models, and analyst
decisions remain inside the controlled environment.

------------------------------------------------------------------------

# Key Capabilities

## 1. Semantic & Multimodal Retrieval

AVLOKAN supports both natural-language and image-based satellite imagery
search.

### Text-to-Image

Analysts can search using natural language, for example:

``` text
Newly constructed buildings and infrastructure development
```

The query is encoded into the same embedding space as indexed satellite
imagery and matched using vector similarity.

### Image-to-Image

An analyst can upload a satellite image and retrieve visually and
semantically similar scenes from the indexed archive.

### Retrieval Filters

Results can be filtered and ranked using:

-   Similarity
-   Geographic area
-   Acquisition date
-   Sensor
-   Scene metadata
-   Spatial context

The retrieval layer is powered by a FAISS vector index and multimodal
Earth-observation embeddings.

------------------------------------------------------------------------

# 2. Multi-Temporal Change Detection

AVLOKAN compares satellite observations acquired at different points in
time to identify localized changes.

``` text
T1 / Before Image
       │
       ▼
Quality & Alignment Checks
       │
       ▼
Embedding-Level Candidate Gate
       │
       ▼
BIT Pixel-Level Verification
       │
       ▼
Probability Map
       │
       ▼
Post-processing
       │
       ▼
Retained Change Candidates
```

The system produces:

-   Before imagery
-   After imagery
-   Per-pixel change probability
-   Raw model mask
-   Final retained change mask
-   Candidate regions
-   Candidate-level evidence
-   Spatial geometry
-   Processing provenance

------------------------------------------------------------------------

# 3. Change Probability Heatmap

Change probability is visualized directly over the analyzed satellite
scene.

``` text
LOW CHANGE PROBABILITY
        ↓
      Yellow
        ↓
      Orange
        ↓
        Red
        ↓
HIGH CHANGE PROBABILITY
```

The visualization allows analysts to move from broad change regions to
individual retained candidates.

------------------------------------------------------------------------

# 4. Multi-Sensor Change Verification

AVLOKAN combines optical and radar evidence to improve change
interpretation.

### Sentinel-2 Optical

Multispectral imagery provides spectral information useful for
identifying:

-   Construction
-   Land-cover changes
-   Clearance
-   Vegetation changes
-   Surface changes

### Sentinel-1 SAR

Sentinel-1 C-band SAR provides complementary radar observations and
enables monitoring under conditions where optical imagery is degraded.

The SAR pipeline works with VV and VH polarizations and produces
deterministic radar change evidence.

``` text
Sentinel-2 Optical Evidence
            │
            ├──────────────┐
            │              │
            ▼              ▼
       Optical        Sensor Agreement
       Evidence             ▲
            │              │
            │              │
Sentinel-1 SAR Evidence ───┘
            │
            ▼
      Fusion Evidence
```

------------------------------------------------------------------------

# 5. Sensor Agreement

AVLOKAN evaluates agreement between optical change evidence and SAR
evidence.

The system provides:

-   Optical evidence
-   SAR evidence
-   Sensor agreement
-   Evidence fusion
-   Data-quality contribution
-   Candidate-level evidence score

  Optical Evidence   SAR Evidence   Interpretation
  ------------------ -------------- ---------------------------------
  High               High           High sensor agreement
  High               Low            Optical-dominant evidence
  Low                High           SAR-dominant evidence
  Low                Low            No strong cross-sensor evidence

The evidence layer is explicitly separated from calibrated statistical
probability.

------------------------------------------------------------------------

# 6. False-Alarm Suppression

Satellite imagery contains many sources of apparent change that are not
meaningful physical changes.

AVLOKAN incorporates quality-control and normalization stages before
producing trusted change candidates.

The processing pipeline considers:

-   Cloud
-   Cloud shadow
-   Haze
-   Snow
-   Invalid pixels
-   SAR noise
-   Insufficient usable imagery
-   Radiometric inconsistency
-   Geometric misalignment

Processing includes:

-   Reflectance normalization
-   SAR radiometric processing
-   Terrain correction
-   Co-registration checks
-   Spatial alignment
-   Quality masking

------------------------------------------------------------------------

# 7. Discovery & Similar-Site Analysis

Once an analyst identifies an area of interest, AVLOKAN can search the
archive for visually or semantically related locations.

``` text
Confirmed Site
     ↓
Generate Embedding
     ↓
Search Archive
     ↓
Similarity Ranking
     ↓
Discovery / Clustering
     ↓
Related Sites
```

The discovery layer uses embedding similarity and clustering to group
related scenes and surface similar areas for further investigation.

------------------------------------------------------------------------

# 8. Analyst Review Queue

AVLOKAN is designed around an analyst-in-the-loop workflow.

Detected candidates are presented with:

-   Before image
-   After image
-   Change visualization
-   Location
-   Acquisition dates
-   Sensor
-   Evidence
-   Provenance
-   Candidate metrics
-   Confirm / Reject controls

Analysts can validate individual findings rather than manually scanning
the entire imagery archive.

------------------------------------------------------------------------

# 9. Provenance & Audit Trail

Every analytical result is associated with its processing lineage.

The provenance layer records:

-   Analysis ID
-   Source observations
-   Acquisition timestamps
-   Sensor
-   Input raster paths
-   Coordinate reference system
-   Model checkpoint
-   Model configuration
-   Processing stages
-   Thresholds
-   Runtime measurements
-   Generated artifacts
-   Analyst decisions

Review decisions are written into an audit history so findings remain
traceable from analyst action back to source imagery and processing
configuration.

------------------------------------------------------------------------

# 10. Incremental Indexing

AVLOKAN is designed to grow without rebuilding the complete vector index
every time new imagery arrives.

``` text
New Scene
   ↓
Preprocess
   ↓
Tile
   ↓
Generate Embedding
   ↓
Append Vector
   ↓
Update Metadata
   ↓
Immediately Searchable
```

The indexing layer uses FAISS with ID-mapped vectors and supports
incremental insertion of new imagery.

------------------------------------------------------------------------

# 11. Sovereign & Offline Architecture

AVLOKAN is designed for environments where cloud access is undesirable
or unavailable.

``` text
┌───────────────────────────────────────────┐
│              AVLOKAN NODE                 │
│                                           │
│  Satellite Data                           │
│       ↓                                   │
│  Preprocessing                            │
│       ↓                                   │
│  AI / Embeddings                          │
│       ↓                                   │
│  FAISS / Metadata                         │
│       ↓                                   │
│  FastAPI                                  │
│       ↓                                   │
│  Analyst Workstation                     │
│                                           │
└───────────────────────────────────────────┘
```

Core processing is performed locally, supporting controlled networks and
air-gapped environments.

------------------------------------------------------------------------

# Architecture

``` text
                         ┌─────────────────────┐
                         │ Satellite Imagery   │
                         │ S1 / S2 / Landsat   │
                         │ / Bhuvan / EO Data  │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Acquisition &       │
                         │ Preprocessing        │
                         │ Rasterio / GDAL      │
                         │ SNAP / OpenCV        │
                         └──────────┬──────────┘
                                    │
                         ┌──────────┴──────────┐
                         ▼                     ▼
                ┌─────────────────┐   ┌─────────────────┐
                │ Optical Pipeline│   │ SAR Pipeline   │
                │ Cloud / Shadow  │   │ Calibration     │
                │ Masking         │   │ Speckle Filter │
                │ Normalization   │   │ Terrain Corr.  │
                └────────┬────────┘   └────────┬────────┘
                         │                     │
                         └──────────┬──────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ Tiling & Metadata   │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ AI / Embeddings     │
                         │ RemoteCLIP /        │
                         │ GeoRSCLIP           │
                         │ BIT Change Detector │
                         │ HDBSCAN Discovery   │
                         └──────────┬──────────┘
                                    │
                       ┌────────────┴────────────┐
                       ▼                         ▼
              ┌─────────────────┐       ┌─────────────────┐
              │ FAISS Vector    │       │ Metadata /      │
              │ Index           │       │ Provenance      │
              │ Incremental     │       │ PostgreSQL /    │
              │ Retrieval       │       │ PostGIS         │
              └────────┬────────┘       └────────┬────────┘
                       │                         │
                       └────────────┬────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │ FastAPI Backend     │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │ Analyst Workstation │
                         │ Retrieval           │
                         │ Map                  │
                         │ Change Analysis      │
                         │ Review Queue         │
                         │ Audit / Provenance   │
                         └─────────────────────┘
```

------------------------------------------------------------------------

# Technology Stack

## AI / Computer Vision

-   PyTorch
-   RemoteCLIP
-   GeoRSCLIP
-   Bitemporal Image Transformer (BIT)
-   HDBSCAN
-   OpenCV

## Geospatial

-   Rasterio
-   GDAL
-   ESA SNAP
-   GeoTIFF
-   Sentinel-1
-   Sentinel-2
-   Landsat Collection 2

## Retrieval & Storage

-   FAISS
-   PostgreSQL
-   PostGIS
-   Vector embeddings
-   Spatial metadata
-   Provenance records

## Backend

-   Python
-   FastAPI
-   REST APIs
-   Docker / Docker Compose

## Frontend

-   JavaScript / TypeScript
-   MapLibre GL JS
-   OpenFreeMap-compatible styling
-   Interactive geospatial visualization
-   Analyst review workflows

------------------------------------------------------------------------

# Data Sources

  Source                 Role
  ---------------------- ------------------------------------
  Sentinel-2             Multispectral optical imagery
  Sentinel-1             All-weather SAR imagery
  Landsat Collection 2   Long-term optical archive
  Bhuvan / ISRO          Indian Earth-observation ecosystem
  Licensed EO sources    Extensible ingestion layer

The system preserves acquisition metadata and geospatial referencing
throughout the processing pipeline.

------------------------------------------------------------------------

# Models

## RemoteCLIP / GeoRSCLIP

Used for multimodal Earth-observation embeddings:

-   Text-to-image retrieval
-   Image-to-image retrieval
-   Similar-scene discovery
-   Archive indexing

## BIT

The Bitemporal Image Transformer is used for pixel-level change
verification and produces per-pixel change probabilities.

## HDBSCAN

Used for similarity-based discovery and grouping of related imagery and
candidate sites.

------------------------------------------------------------------------

# Change Detection Workflow

``` text
             T1                         T2
              │                         │
              ▼                         ▼
        Quality Check             Quality Check
              │                         │
              └──────────┬──────────────┘
                         ▼
                  Co-registration
                         │
                         ▼
                Embedding Gate
                         │
                         ▼
                 Candidate Regions
                         │
                         ▼
                BIT Pixel Verifier
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        Optical Result         SAR Verification
              │                     │
              └──────────┬──────────┘
                         ▼
                 Sensor Agreement
                         │
                         ▼
                  Evidence Fusion
                         │
                         ▼
                 Analyst Review
                         │
                         ▼
                  Audit / Record
```

------------------------------------------------------------------------

# Repository Structure

``` text
AVLOKAN/
│
├── configs/
├── data/
│   ├── raw/
│   ├── processed/
│   ├── demo/
│   └── map/
│
├── docs/
├── frontend/
│   ├── css/
│   ├── js/
│   ├── assets/
│   └── vendor/
│
├── models/
├── pipeline/
│   ├── acquisition/
│   ├── preprocessing/
│   ├── retrieval/
│   ├── change_detection/
│   ├── indexing/
│   └── api/
│
├── tests/
├── scripts/
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
└── README.md
```

------------------------------------------------------------------------

# Installation

## Requirements

Recommended environment:

-   Python 3.11+
-   Node.js
-   Git
-   GDAL
-   Docker / Docker Compose
-   NVIDIA GPU with CUDA support for accelerated inference

## Clone

``` bash
git clone https://github.com/<your-organization>/AVLOKAN.git
cd AVLOKAN
```

## Python Environment

### Windows

``` powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Linux

``` bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

------------------------------------------------------------------------

# Start the Backend

``` bash
python -m uvicorn pipeline.api.app:app --host 127.0.0.1 --port 8000
```

API:

``` text
http://127.0.0.1:8000
```

Interactive documentation:

``` text
http://127.0.0.1:8000/docs
```

------------------------------------------------------------------------

# Start the Frontend

Serve the frontend using a local static server:

``` bash
cd frontend
python -m http.server 5500
```

Open:

``` text
http://127.0.0.1:5500
```

------------------------------------------------------------------------

# API

Representative endpoints:

``` text
GET  /api/health
GET  /api/dashboard

POST /api/search/text
POST /api/search/image

GET  /api/scenes/search

GET  /api/change-analyses
POST /api/change-analyses
GET  /api/change-analyses/{id}

GET  /api/change-analyses/{id}/sar-fallback
GET  /api/change-analyses/{id}/sensor-agreement

GET  /api/audit
POST /api/review

GET  /api/indexing/status
POST /api/indexing/incremental-ingest
```

------------------------------------------------------------------------

# Evaluation

AVLOKAN includes evaluation workflows for:

-   Precision
-   Recall
-   F1 score
-   IoU
-   PR-AUC
-   Retrieval latency
-   Inference latency
-   Indexing latency
-   Storage footprint
-   Processing time
-   Incremental indexing behavior

The change-detection evaluation uses held-out remote-sensing data and
threshold analysis to balance false alarms against missed changes.

------------------------------------------------------------------------

# Provenance

Models and datasets are tracked with source information and processing
lineage.

Research references include:

1.  Liu et al. (2024) --- **RemoteCLIP**, IEEE TGRS
2.  Chen et al. (2024) --- **Remote Sensing Image Change Detection with
    Transformers**, IEEE TGRS
3.  Das et al. (2023) --- **Multi-Change Detection**, ISPRS
4.  Zhan & Kovacs (2021) --- **Self-Supervised Change Detection**, arXiv

Reference datasets include:

-   OGCD
-   Sentinel-1
-   Sentinel-2
-   Landsat Collection 2
-   WHU-CD / BIChange

------------------------------------------------------------------------

# Use Cases

## Border & Infrastructure Monitoring

Identify newly constructed infrastructure, structural changes, cleared
areas, roads, and other relevant changes over time.

## Disaster Response

Compare pre-event and post-event imagery to identify affected areas.

## Environmental Monitoring

Track changes in:

-   Water bodies
-   Vegetation
-   Land cover
-   Construction
-   Surface disturbance

## Infrastructure Planning

Search imagery archives for similar development patterns and monitor
changes around infrastructure.

## Intelligence Analysis

Prioritize semantically relevant scenes and candidate changes so
analysts can focus on verification instead of exhaustive manual
scanning.

------------------------------------------------------------------------

# Analyst Workflow

``` text
1. Search
   ↓
2. Discover relevant imagery
   ↓
3. Select observations
   ↓
4. Compare temporal imagery
   ↓
5. Inspect change heatmap
   ↓
6. Verify with complementary sensor evidence
   ↓
7. Review candidates
   ↓
8. Confirm / Reject
   ↓
9. Preserve provenance
   ↓
10. Audit the decision
```

The analyst remains in control of the final decision.

------------------------------------------------------------------------

# Why AVLOKAN?

### Multimodal Search

Search satellite archives using language or imagery.

### Multi-Temporal Intelligence

Move from individual scenes to temporal change analysis.

### Multi-Sensor Verification

Combine optical and SAR observations for complementary evidence.

### Analyst-Centered Workflow

Every candidate can be inspected through imagery, evidence, processing
history, and provenance.

### Incremental Architecture

New imagery can be incorporated without rebuilding the entire archive.

### Sovereign Deployment

Designed for local, on-premises and offline environments.

------------------------------------------------------------------------

# Project Information

**Project:** AVLOKAN\
**Team:** Codenostic\
**Smart India Hackathon:** 2026\
**Problem Statement:** SIH26227\
**Theme:** Space Technology\
**Category:** Software\
**Team ID:** 171288

------------------------------------------------------------------------

# License

Add the project's selected license here.

Model weights, datasets, satellite imagery, and third-party components
remain subject to their respective licenses and usage terms.

------------------------------------------------------------------------

# Acknowledgements

AVLOKAN builds on open research and geospatial technologies including:

-   ESA Sentinel missions
-   ISRO / Bhuvan ecosystem
-   Landsat
-   RemoteCLIP
-   GeoRSCLIP
-   BIT
-   FAISS
-   PyTorch
-   Rasterio
-   GDAL
-   ESA SNAP
-   OpenCV
-   FastAPI
-   PostgreSQL / PostGIS
-   MapLibre

------------------------------------------------------------------------

## AVLOKAN

**Search the Earth. Detect change. Verify evidence. Preserve
provenance.**
