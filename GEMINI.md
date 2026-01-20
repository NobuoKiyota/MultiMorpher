# Antigravity Development Guidelines

## 1. System Standards
- **Sample Rate:** All audio processing must default to **48000Hz** unless explicitly specified otherwise.
- **Language:** User interaction, comments, and **documentation/logs** must be in **Japanese**.
- **Environment:** Python (Windows Standalone target).

## 2. Architecture & Refactoring
- **Modularization:**
  - You have the authority to split files (modularize) when code becomes too complex or monolithic.
  - **Priority:** Stability (Error-free operation) > Cleanliness.
  - **Reporting:** When refactoring occurs, provide a report in Markdown format explaining the new structure to Gemini.
- **Libraries:**
  - **Computation:** Use `numpy` vectorization for all audio processing. Avoid Python `for` loops in audio callbacks.
  - **Real-time:** Use `pyaudio` for streaming.
  - **Offline/Analysis:** Use `librosa`, `soundfile`, `pyworld`.
  - **GUI:** Use `customtkinter`.

## 3. Version Compatibility (Lessons Learned)
- **NumPy:** Use `float` or `np.float64` instead of `np.float` (deprecated).
- **Threading:** Heavy audio processing (Morphing, Batch Gen) must run in separate threads to prevent GUI freezing.

## 4. Documentation & Logging
- **Debug Note:** Maintain a history of changes, errors, and fixes in `DEBUG_NOTE.md` (Write in **Japanese**).
- **Summarization:** When the log becomes too long, you are authorized to summarize old entries into an "Overview" section.

## 5. Target Environment & Assets (Merged Context)
- **Unity Editor:** 6000.3.2f1
- **CRIWare:** Ver.3.48.00 (built on Aug 22 2022) 11:39:42
  - ACF Format Ver.1.28.00
  - ACB Format Ver.1.40.00
  - CRI Atom: 2.24.175
  - CRI AtomEx: 2.24.4
  - CRI AtomEx Monitor: 1.18.9
- **Past Assets:** `F:\UnityCustomEditor\DebugLog_Distance`
