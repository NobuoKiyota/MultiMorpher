import os
import shutil
import glob
import pandas as pd
import numpy as np
import librosa
import soundfile as sf
import datetime

# Configuration
SAMPLE_RATE = 22050 # Faster scanning
TRIM_DB = 25 # Threshold for silence trimming

class LearningLoopEngine:
    def __init__(self, logger=None):
        self.logger = logger or print
        
    def log(self, msg):
        self.logger(msg)

    def scan_level0(self, input_dir):
        """
        Level 0 Scan:
        1. Find all wavs in input_dir
        2. Analyze features
        3. Simple Heuristic Tagging
        4. Trim & Export to Scanned-Level0
        5. Generate Excel
        """
        self.log(f"Starting Level 0 Scan for: {input_dir}")
        
        parent_dir = os.path.dirname(input_dir)
        output_dir = os.path.join(parent_dir, "Scanned-Level0")
        os.makedirs(output_dir, exist_ok=True)
        
        wav_files = glob.glob(os.path.join(input_dir, "**", "*.wav"), recursive=True)
        wav_files += glob.glob(os.path.join(input_dir, "**", "*.mp3"), recursive=True)
        
        self.log(f"Found {len(wav_files)} audio files.")
        
        excel_data = []
        
        for i, fpath in enumerate(wav_files):
            try:
                fname = os.path.basename(fpath)
                
                # 1. Analyze
                y, sr = librosa.load(fpath, sr=SAMPLE_RATE)
                
                # Feature Extraction (Simple)
                dur = librosa.get_duration(y=y, sr=sr)
                cent = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
                contrast = np.mean(librosa.feature.spectral_contrast(y=y, sr=sr))
                
                # 2. Heuristic Tagging (Mock for Level 0)
                # In real implementation, this uses the existing rules or a model
                tags = self._heuristic_tags(dur, cent, contrast)
                primary_tag = tags[0][0] if tags else "Unknown"
                
                # 3. Process (Trim)
                y_trim, _ = librosa.effects.trim(y, top_db=TRIM_DB)
                dur_ms = int(len(y_trim) / sr * 1000) # Trimmed Duration
                
                # Rename: Sequential Numbering (Tag is unreliable at Level0)
                # Format: 0001_OriginalName.wav
                base_name = os.path.splitext(fname)[0]
                new_fname = f"{i+1:04d}_{base_name}.wav"
                     
                out_path = os.path.join(output_dir, new_fname)
                
                # Export
                sf.write(out_path, y_trim, sr)
                
                # 4. Record Data
                row = {
                    "Original_File": fname,
                    "Processed_File": new_fname,
                    "Duration_ms": dur_ms,
                    # Auto Tags (Reference)
                    "Auto_Tag1": tags[0][0] if len(tags) > 0 else "",
                    "Auto_Score1": tags[0][1] if len(tags) > 0 else 0.0,
                    "Auto_Tag2": tags[1][0] if len(tags) > 1 else "",
                    "Auto_Score2": tags[1][1] if len(tags) > 1 else 0.0,
                    "Auto_Tag3": tags[2][0] if len(tags) > 2 else "",
                    "Auto_Score3": tags[2][1] if len(tags) > 2 else 0.0,
                    # User Inputs
                    "User_Tag_Correct": "",    # User defines true tag
                    "User_Tag_Score": "",      # User confidence (1-5 or 0.0-1.0)
                    "Score_Comment": "",       # Notes
                    "Length_Rating_1-5": ""    # 1:TooShort ... 5:TooLong
                }
                excel_data.append(row)
                
                if i % 10 == 0:
                    self.log(f"Processed {i}/{len(wav_files)}: {new_fname}")
                    
            except Exception as e:
                self.log(f"  Error processing {fpath}: {e}")

        # 5. Generate Excel
        if excel_data:
            df = pd.DataFrame(excel_data)
            xl_path = os.path.join(output_dir, "Level0_Report.xlsx")
            
            # Simple Excel Write
            with pd.ExcelWriter(xl_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name="Level0")
                # Auto-width attempt
                sheet = writer.sheets['Level0']
                for idx, col in enumerate(df.columns):
                    max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    try:
                        sheet.column_dimensions[chr(65 + idx)].width = min(max_len, 50)
                    except: pass # Ignore if column letter out of range for simple char logic
                    
            self.log(f"Level 0 Scan Complete. Report: {xl_path}")
            return xl_path, output_dir
        else:
            self.log("No data generated.")
            return None, None

    def _heuristic_tags(self, dur, cent, contrast):
        """
        Expanded logic to assign tags based on audio features.
        """
        tags = []
        
        # 1. Feature Analysis
        is_short = dur < 0.2
        is_long = dur > 2.0
        is_high = cent > 3000
        is_low = cent < 800
        is_noisy = contrast < 15
        is_tonal = contrast > 25
        
        # 2. Heuristic Rules
        if is_short and is_high: tags.append(("Click", 0.9))
        if is_short and is_low: tags.append(("Kick", 0.8))
        if is_short and is_noisy: tags.append(("Hit", 0.7))
        
        if not is_short and not is_long and is_high and is_tonal: tags.append(("Bell", 0.8))
        if not is_short and not is_long and is_high and is_noisy: tags.append(("Beam", 0.75))
        
        if is_long and is_tonal: tags.append(("Drone", 0.8))
        if is_long and is_noisy: tags.append(("Ambience", 0.8))
        
        if is_tonal: tags.append(("Musical", 0.6))
        if is_noisy: tags.append(("Noise", 0.6))
        
        if cent > 4000: tags.append(("Metallic", 0.65))
        if cent < 500: tags.append(("Rumble", 0.7))
        
        # 3. Fallbacks
        if not tags: tags.append(("General", 0.5))
        if len(tags) < 3: tags.append(("Unknown", 0.1))
        
        # Sort
        tags.sort(key=lambda x: x[1], reverse=True)
        return tags[:3]

    def train_level1(self, excel_path):
        """
        Mockup for Level 1 training.
        Would parse the Excel, looking for 'User_Comment' or corrected tags,
        and update internal weights/rules.
        """
        self.log(f"Learning from: {excel_path}...")
        df = pd.read_excel(excel_path)
        # TODO: Implement learning logic
        self.log(f"Loaded {len(df)} feedback entries.")
        self.log("Weights updated (Mock). Ready for Level 1 Scan.")
