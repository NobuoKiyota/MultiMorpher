# SFX Factory Automation - Implementation Plan

## Goal Description
Automate the current manual workflow of generating, processing, and refining sound effects to produce high-volume (1000+), high-quality assets with detailed logging for future AI model training.
Establish a "Human-in-the-loop" verification system to tag high-quality outputs efficiently.

## Architecture Overview

### 1. The Orchestrator (`sfx_pipeline_manager.py`)
A master script that controls the flow of data between modules.
- **Input**: Configuration (Number of files, Target Categories [System, FX, Pad...]).
- **Process**:
    1.  **Factory**: Prodedurally generate base audio (Random/Guided parameters).
    2.  **Transformer**: Apply effect chains (Morphing, Time-stretch, etc.).
    3.  **Masker**: Add noise layers.
    4.  **Slicer**: Trim silence (using RMS threshold).
    5.  **Normalizer**: Time-stretch/Resample to exact target duration (1s, 3s, 5s, 10s).
    6.  **Logger**: Record EVERY parameter used in steps 1-5 into a Pandas DataFrame.
- **Output**: 
    - WAV files in `Output/Raw_Batch_YYYYMMDD/`
    - `generation_log.xlsx` containing all metadata.

### 2. The Reviewer (`sfx_reviewer_app.py`)
A specialized `customtkinter` GUI for rapid quality control.
- **Input**: The `generation_log.xlsx` and the folder of generated WAVs.
- **Features**:
    - **One-Click Playback**: Auto-play on navigate.
    - **Scoring**: 1-10 Hotkeys (e.g., Numpad).
    - **Sorting**: "Good" files move to `High_Score/`, "Bad" to `Low_Score/`.
    - **Update Log**: Writes the `UserScore` back to the Excel file.

### 3. The Feedback Loop
- Future capabilities enabled by this structure:
    - Analyze `generation_log.xlsx` rows with `UserScore >= 8`.
    - Extract parameter distributions (e.g., "High score pads usually have Filter Resonance < 0.3").
    - Update `Factory` random ranges based on these stats.

## Proposed Changes

### [MultiMorpher/PySerum] (Non-Destructive Additive Approach)
We will strictly ADD new files and NOT modify existing files to ensure zero risk of breaking current tools. Logic from existing GUIs will be copied into new independent Engine classes.

#### [NEW] [sfx_pipeline_manager.py](file:///z:/MultiMorpher/PySerum/sfx_pipeline_manager.py)
- Main entry point. Imports and sequences the engines below.

#### [NEW] [pysfx_slicer_engine.py](file:///z:/MultiMorpher/PySerum/pysfx_slicer_engine.py)
- Standalone logic extracted from `pysfx_slicer_gui.py`.

#### [NEW] [pysfx_normalizer_engine.py](file:///z:/MultiMorpher/PySerum/pysfx_normalizer_engine.py)
- Standalone logic extracted from `pysfx_normalizer_gui.py`.

#### [NEW] [pysfx_logger.py](file:///z:/MultiMorpher/PySerum/pysfx_logger.py)
- Helper class to handle Dictionary -> Excel row operations.

#### [NEW] [sfx_reviewer_app.py](file:///z:/MultiMorpher/PySerum/sfx_reviewer_app.py)
- QC Tool.

*(Existing files like `pysfx_factory.py`, `pysfx_transformer_engine.py` will be imported but not modified)*

## Verification Plan

### Automated Tests
- Run pipeline with `n=5`.
- Check if 5 WAV files exist.
- Check if Excel has 5 rows + Header.
- Check if Excel columns match the parameter keys.

### Manual Verification
- Open `sfx_reviewer_app.py`.
- Verify audio plays.
- Verify scoring updates the Excel file correctly.
- Verify file movement to subfolders.

