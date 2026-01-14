# MultiMorpher - User Manual

## 🦁 Introduction
Welcome to **MultiMorpher**!
This application is a powerful tool designed to "morph" (blend) multiple voices or sound effects and process them through an advanced effects chain. Create unknown monster voices, creatures, or unique sound design assets with ease.

## 🖥 Interface & Features

### 1. EXPLORER (Top Left)
The file browser.
- **List**: Shows folders and audio files (.wav, .mp3, etc).
- **Pin Current**: Save the current directory to favorites.
- **Favorites List**: Click 'x' to remove a pin.
- **Load Menu**: Right-click a file to load it into slot A, B, C, or D.

### 2. SOURCES & CONTROLS (Bottom Left)
Controls for synthesis and main actions.

#### Source Loading
- **Load A (Master)**: The primary sound. Determines the duration basis for pitch curves.
- **Load B, C, D**: Secondary sounds to blend in.
- *Tips: You can also Drag & Drop files onto the buttons.*

#### MORPH PAD
- Drag the handle on the X-Y pad to blend the 4 voices (A, B, C, D).
- **MOTION**: Automate the handle movement.
    - `Static`: No movement.
    - `RandomPoint`: Pick a random spot each time.
    - `Circle/Eight`: Move in shapes.
    - `Scan`: Linear scan.
    - `RandomMovement`: Wanders randomly.
- **Speed (Hz)**: Speed of the automation.

#### Main Actions
- **Auto Apply**: If checked, clicking MORPH automatically runs APPLY FX too.
- **1. MORPH** `[Key: 1]`: Synthesizes the base audio from sources.
- **2. APPLY FX** `[Key: 2]`: Applies effects (Pitch, Formant, Reverb, etc) to the morphed audio.
- **0. CHAOS** `[Key: 0]`: Randomizes ALL parameters and positions. Great for inspiration!
- **4. SNAPSHOT** `[Key: 4]`: Instantly saves the current sound to "Snapshots" folder.
- **PLAY** `[Key: Space]`: Preview Play/Stop.
- **SAVE WAV**: Save with a custom filename.

### 3. EDITOR (Center)
Accordion menu for fine-tuning sound.

#### PITCH CURVE
- Draw the pitch envelope over time.
- **Right-Click**: Delete point.
- **Left-Click**: Add/Move point.
- **Range ±**: Adjust the vertical range (semitones). Default is 6. Set to 12 or 24 for extreme shifts.

#### CORE EFFECTS
- **Formant**: Throat size/Timbre. Low = Giant/Male, High = Child/Female.
- **Breath**: Adds noise/breathiness.
- **Speed**: Overall playback speed.
- **Volume**: Output level.

#### MODULATION & TONE
- **Growl**: Adds a rough, rattling texture (Amplitude Modulation).
- **Tone**: Brightness/Tilt filter.
- **Ring Mix/Freq**: Robotic/Metallic sound (Ring Modulator).

#### SPACE & TIME
- **Spacer**: Stereo width enhancement.
- **Reverb**: Room ambience.
- **Delay**: Echo (Time, Feedback, Mix).

#### LO-FI / DIST
- **Distortion**: Overdrive/Clipping.
- **Bit Depth / SR Divider**: Digital degradation (Bitcrushing).

### 4. BATCH FACTORY (Right)
Automatically generate variations. Useful for game assets (e.g., "I need 100 variations of this monster attack").

1. **Min - Max**: Set the random range for each parameter.
2. **Output Directory**: Choose where to save files.
3. **Run Batch**: Generate the specified number of files.

---

## ⌨️ Shortcuts
| Key | Action |
| :--- | :--- |
| **G** | Morph (Generate) |
| **H** | Apply FX (Effects) |
| **?** | Chaos (Randomize) |
| **S** | Snapshot (Quick Save) |
| **Ctrl+S** | Save WAV |
| **Space** | Play / Stop |
