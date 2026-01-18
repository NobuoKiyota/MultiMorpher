import os
import shutil
import glob
import pandas as pd
import numpy as np
import librosa
import soundfile as sf
import datetime
import winsound
import pickle
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

class TaggerEngine:
    def __init__(self, drive_path, input_path):
        self.drive_path = drive_path
        self.input_path = input_path
        self.todo_list = []
        self.current_idx = 0
        self.current_file = None
        self.current_features = None # [dur, cent, contrast]
        self.index_file = os.path.join(self.drive_path, "QuartzTagIndex.xlsx")
        self.model_file = os.path.join(self.drive_path, "quartz_model.pkl")
        self.cls = None
        self.le = None
        self.load_model()

    def load_model(self):
        if os.path.exists(self.model_file):
            try:
                with open(self.model_file, 'rb') as f:
                    data = pickle.load(f)
                    self.cls = data['cls']
                    self.le = data['le']
            except: pass
        
    def scan_input(self):
        """Scan input folder for unprocessed wavs"""
        print(f"[{datetime.datetime.now()}] Start Scanning: {self.input_path}")
        if not os.path.exists(self.input_path): return []
        
        # 1. Glob
        t0 = datetime.datetime.now()
        files = glob.glob(os.path.join(self.input_path, "*.wav"))
        files += glob.glob(os.path.join(self.input_path, "*.mp3"))
        t1 = datetime.datetime.now()
        print(f"[{t1}] Glob found {len(files)} files. (Took {t1-t0})")
        
        # 2. Excel Load
        processed_files = set()
        if os.path.exists(self.index_file):
            print(f"[{datetime.datetime.now()}] Index found. Reading: {self.index_file}")
            try:
                t2 = datetime.datetime.now()
                df = pd.read_excel(self.index_file, usecols=["Original_File"], engine='openpyxl')
                t3 = datetime.datetime.now()
                print(f"[{t3}] Excel Read Complete. (Took {t3-t2})")
                
                if "Original_File" in df.columns:
                     processed_files = set(df["Original_File"].astype(str))
            except Exception as e:
                print(f"Excel Read Error: {e}")
        else:
            print("No Index file (First run or deleted).")
            
        # 3. Filter
        self.todo_list = [f for f in files if os.path.basename(f) not in processed_files]
        self.todo_list.sort()
        self.current_idx = 0
        print(f"[{datetime.datetime.now()}] Scan Done. Ready: {len(self.todo_list)} files.")
        return self.todo_list

    def get_current_file(self):
        if not self.todo_list or self.current_idx >= len(self.todo_list):
            return None
        return self.todo_list[self.current_idx]

    def analyze_current(self):
        """Analyze current file and return AI tags"""
        fpath = self.get_current_file()
        if not fpath: return None
        
        try:
            # 1. Analyze
            y, sr = librosa.load(fpath, sr=22050, duration=10.0) # limit duration for speed
            
            # Feature Extraction
            dur = librosa.get_duration(y=y, sr=sr)
            cent = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
            contrast = np.mean(librosa.feature.spectral_contrast(y=y, sr=sr))
            
            self.current_features = [dur, cent, contrast]
            
            # Simple Heuristics
            tags = self._heuristic_tags(dur, cent, contrast)
            
            # ML Prediction
            if self.cls and self.le:
                try:
                    vf = np.array([self.current_features])
                    probs = self.cls.predict_proba(vf)[0]
                    top_idx = np.argmax(probs)
                    conf = probs[top_idx]
                    label = self.le.inverse_transform([top_idx])[0]
                    tags.insert(0, (f"AI:{label}", conf))
                except: pass

            return tags
        except Exception as e:
            print(f"Analysis Error: {e}")
            return [("Error", 0.0)]

    def _heuristic_tags(self, dur, cent, contrast):
        tags = []
        # Duration
        if dur < 0.2: tags.append(("Click/Shot", 0.9))
        elif dur > 3.0: tags.append(("Ambience/Loop", 0.8))
        else: tags.append(("OneShot", 0.7))
        
        # Spectrum
        if cent > 3000: tags.append(("HighFreq", 0.6))
        elif cent < 500: tags.append(("LowEnd", 0.6))
        
        # Tonal
        if contrast > 25: tags.append(("Tonal", 0.7))
        else: tags.append(("Noisy", 0.7))
        
        if not tags: tags.append(("General", 0.5))
        return tags[:2] # Top 2

    def save_and_next(self, user_tag, user_comment):
        """Save to Drive and advance"""
        fpath = self.get_current_file()
        if not fpath: return False
        
        fname = os.path.basename(fpath)
        
        # Ensure features
        if not self.current_features:
            self.analyze_current()
            
        # 1. Copy file to Drive (Archive)
        archive_dir = os.path.join(self.drive_path, "AudioArchive")
        os.makedirs(archive_dir, exist_ok=True)
        try:
            shutil.copy2(fpath, os.path.join(archive_dir, fname))
        except: pass # Ignore copy error if exists
        
        # 2. Update Index (Add Row)
        new_row = {
            "Original_File": fname,
            "Date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "User_Tag": user_tag,
            "User_Comment": user_comment
        }
        
        # Add Features
        if self.current_features:
            new_row["Duration"] = self.current_features[0]
            new_row["Centroid"] = self.current_features[1]
            new_row["Contrast"] = self.current_features[2]
        
        self._append_to_excel(new_row)
        
        # 3. Advance
        self.current_idx += 1
        return True

    def train_model(self):
        if not os.path.exists(self.index_file): return "No Data"
        try:
            df = pd.read_excel(self.index_file, engine='openpyxl')
            
            # Check Backfill
            if "Duration" not in df.columns or df["Duration"].isnull().any():
                print("Backfilling features for training...")
                df = self._backfill_features(df)
                
            # Prepare Data
            df = df[df["User_Tag"].notna()]
            df = df[df["User_Tag"].astype(str).str.strip() != ""]
            
            if len(df) < 5: return f"Need more data ({len(df)}/5 samples)"
            
            X = df[["Duration", "Centroid", "Contrast"]].values
            y = df["User_Tag"].astype(str).values
            
            le = LabelEncoder()
            y_enc = le.fit_transform(y)
            
            cls = RandomForestClassifier(n_estimators=50, max_depth=5)
            cls.fit(X, y_enc)
            
            # Save
            with open(self.model_file, 'wb') as f:
                pickle.dump({'cls': cls, 'le': le}, f)
                
            self.cls = cls
            self.le = le
            return f"Training Complete! ({len(df)} samples)"
        except Exception as e:
            return f"Train Error: {e}"

    def _backfill_features(self, df):
        archive_dir = os.path.join(self.drive_path, "AudioArchive")
        updated = False
        
        # Init Columns if missing
        for col in ["Duration", "Centroid", "Contrast"]:
            if col not in df.columns: df[col] = 0.0
            
        for i, row in df.iterrows():
            raw_dur = row.get("Duration", 0)
            if pd.isna(raw_dur) or raw_dur == 0:
                fname = row["Original_File"]
                fpath = os.path.join(archive_dir, fname)
                if os.path.exists(fpath):
                    try:
                        y, sr = librosa.load(fpath, sr=22050, duration=5.0)
                        df.at[i, "Duration"] = librosa.get_duration(y=y, sr=sr)
                        df.at[i, "Centroid"] = np.mean(librosa.feature.spectral_centroid(y=y, sr=sr))
                        df.at[i, "Contrast"] = np.mean(librosa.feature.spectral_contrast(y=y, sr=sr))
                        updated = True
                    except: pass
                    
        if updated:
             with pd.ExcelWriter(self.index_file, engine='openpyxl') as writer:
                 df.to_excel(writer, index=False)
        return df

    def prev_file(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            return True
        return False

    def _append_to_excel(self, row):
        if os.path.exists(self.index_file):
            df = pd.read_excel(self.index_file, engine='openpyxl')
            # Check if file exists in Index
            # Make sure to compare as string
            fname = row["Original_File"]
            mask = df["Original_File"].astype(str) == str(fname)
            
            if mask.any():
                # Update existing row
                idx = df[mask].index[0]
                for k, v in row.items():
                    df.at[idx, k] = v
            else:
                # Append
                df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        else:
            df = pd.DataFrame([row])
            
        with pd.ExcelWriter(self.index_file, engine='openpyxl') as writer:
             df.to_excel(writer, index=False)

    def play_current(self):
        fpath = self.get_current_file()
        if fpath:
            winsound.PlaySound(fpath, winsound.SND_FILENAME | winsound.SND_ASYNC)

    def simple_translate(self, jp_text):
        """Simple dict-based translator (Placeholder for API)"""
        dic = {
            "爆発": "Explosion", "ビーム": "Beam", "クリック": "Click",
            "ボタン": "Button", "UI": "UI", "決定": "Decision",
            "キャンセル": "Cancel", "環境音": "Ambience", "風": "Wind",
            "水": "Water", "金属": "Metallic", "打撃": "Hit"
        }
        # Very naive replace
        out = jp_text
        for k, v in dic.items():
            if k in out:
                out = out.replace(k, v)
        return out
