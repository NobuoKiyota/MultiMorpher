
import os
import pandas as pd
import numpy as np
import librosa
import soundfile as sf
import json
import shutil
from datetime import datetime
import warnings

# Configuration
CANDIDATES_DIR = os.path.join(os.path.dirname(__file__), "Candidates")
SCANS_DIR = os.path.join(os.path.dirname(__file__), "Scans")
PROMPTS_FILE = os.path.join(os.path.dirname(__file__), "ui_prompts.json")

def ensure_dir(d):
    if not os.path.exists(d): os.makedirs(d)

# --- 1. Fuzzy Scanner (Level 0) ---
def generate_hypothesis(root_dir, level=0, logger=print):
    logger(f"Start Learning Scan (Level {level}) in {root_dir}")
    ensure_dir(CANDIDATES_DIR)
    ensure_dir(SCANS_DIR)
    
    current_cand_dir = os.path.join(CANDIDATES_DIR, f"Level{level}")
    ensure_dir(current_cand_dir)
    
    # Fuzzy definitions
    fuzzy_defs = [
        {"cat": "Cursor", "cond": lambda y, sr, dur: dur < 0.15 and is_transient(y)},
        {"cat": "Decision", "cond": lambda y, sr, dur: 0.15 <= dur <= 0.6 and is_tonal(y, sr)},
        {"cat": "Cancel", "cond": lambda y, sr, dur: 0.1 <= dur <= 0.4 and is_falling(y, sr)}
    ]
    
    records = []
    
    for root, dirs, files in os.walk(root_dir):
        if "Candidates" in root or "Output" in root: continue
        
        for f in files:
            if not f.lower().endswith(('.wav', '.aiff', '.flac')): continue
            path = os.path.join(root, f)
            
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    y, sr = librosa.load(path, sr=48000)
            except: continue
                
            dur = librosa.get_duration(y=y, sr=sr)
            if dur > 1.0: continue # Skip long files for UI sounds
            
            # Evaluate
            matched_cats = []
            for definition in fuzzy_defs:
                if definition['cond'](y, sr, dur):
                    matched_cats.append(definition['cat'])
            
            if not matched_cats:
                # If fits generic UI length, add as "Unclassified"
                if 0.05 < dur < 0.5:
                     matched_cats.append("Unclassified")
            
            for cat in matched_cats:
                # Save Candidate
                out_name = f"{cat}_{f}"
                out_path = os.path.join(current_cand_dir, out_name)
                sf.write(out_path, y, sr)
                
                records.append({
                    "FileName": out_name,
                    "OriginalFile": f,
                    "AI_Score": 0.5, # Fuzzy score
                    "Reason": f"Matched broad {cat} rules",
                    "User_Score": "",
                    "User_Category": "", # To be filled if correction needed
                    "User_Comment": "",
                    "Detected_Category": cat,
                    "FilePath": out_path
                })
                
    # Save Excel
    df = pd.DataFrame(records)
    xl_path = os.path.join(SCANS_DIR, f"learned_level{level}.xlsx")
    df.to_excel(xl_path, index=False)
    logger(f"Generated Hypothesis: {xl_path} ({len(df)} candidates)")
    return xl_path

# --- Helpers ---
def is_transient(y):
    # High onset strength?
    return np.max(np.abs(y)) > 0.1 # Very simple check
def is_tonal(y, sr):
    # Check if spectrum is peaky
    flatness = librosa.feature.spectral_flatness(y=y)
    return np.mean(flatness) < 0.2
def is_falling(y, sr):
    cent = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    if len(cent) < 5: return False
    return np.mean(cent[-5:]) < np.mean(cent[:5]) * 0.9

# --- 2. Feedback Analysis (Level 1+) ---
def analyze_audio_features(file_path):
    try:
        y, sr = librosa.load(file_path, sr=48000)
    except: return None
    
    dur_ms = librosa.get_duration(y=y, sr=sr) * 1000
    
    # Peak Freq
    S = np.abs(librosa.stft(y))
    freqs = librosa.fft_frequencies(sr=sr)
    mean_spec = np.mean(S, axis=1)
    peak_freq = freqs[np.argmax(mean_spec)]
    
    return {"dur": dur_ms, "freq": peak_freq}

def learn_from_feedback(excel_path, logger=print):
    logger(f"Learning from: {excel_path}")
    
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        logger(f"Error reading Excel: {e}")
        return

    # Load existing prompts
    if os.path.exists(PROMPTS_FILE):
        with open(PROMPTS_FILE, 'r') as f:
            prompts = json.load(f)
    else:
        prompts = []

    # Map existing prompts by category for easy update
    prompt_map = {p['category'].lower(): p for p in prompts}
    
    # Group by (Corrected) Category
    # If User_Category is present, use it. Else use Detected_Category.
    df['Final_Category'] = df['User_Category'].fillna(df['Detected_Category'])
    df['Final_Category'] = df['Final_Category'].apply(lambda x: x.strip() if isinstance(x, str) else "")
    # Fallback to detected if empty after strip
    for idx, row in df.iterrows():
         if not row['Final_Category']:
             df.at[idx, 'Final_Category'] = row['Detected_Category']

    # Filter High Scores (>=4)
    # Convert score to numeric, coerce errors
    df['User_Score'] = pd.to_numeric(df['User_Score'], errors='coerce')
    high_score_df = df[df['User_Score'] >= 4]
    
    if len(high_score_df) == 0:
        logger("No high-rated samples (Score>=4) found. No updates made.")
        return

    # Analyze per category
    for cat, group in high_score_df.groupby('Final_Category'):
        if not cat: continue
        
        durations = []
        freqs = []
        
        logger(f"Analyzing {len(group)} samples for category '{cat}'...")
        
        for _, row in group.iterrows():
            fpath = row['FilePath']
            if not os.path.exists(fpath):
                # Try relative to excel?
                base = os.path.dirname(excel_path)
                fpath = os.path.join(base, row['FileName']) # Assuming generated name matches
                
            if not os.path.exists(fpath): continue
            
            feats = analyze_audio_features(fpath)
            if feats:
                durations.append(feats['dur'])
                freqs.append(feats['freq'])
        
        if not durations: continue
        
        # Calculate Stats
        min_dur = max(30, int(np.min(durations) * 0.8)) # 20% margin
        max_dur = int(np.max(durations) * 1.2)
        avg_freq = float(np.mean(freqs))
        
        # Determine Logic Type (Heuristic)
        # If cat name implies something, or maybe analysis of pitch slope?
        # For now, keep existing type or default to 'Point' for new
        current_type = "Point"
        cat_lower = cat.lower()
        if 'decision' in cat_lower: current_type = "Major"
        elif 'cancel' in cat_lower: current_type = "Fall"
        
        # Update or Create Prompt
        if cat_lower in prompt_map:
            p = prompt_map[cat_lower]
            p['min_ms'] = min_dur
            p['max_ms'] = max_dur
            p['target_freq'] = round(avg_freq, 1)
            # Reduce tolerance to be more specific now that we learned?
            # Or keep it distinct. Let's set high confidence.
            p['tolerance'] = 60 
            logger(f"  -> Updated '{cat}': {min_dur}-{max_dur}ms, {avg_freq:.0f}Hz")
        else:
            new_p = {
                "category": cat,
                "type": current_type,
                "min_ms": min_dur,
                "max_ms": max_dur,
                "target_freq": round(avg_freq, 1),
                "tolerance": 50,
                "processing_reverb": 0.0,
                "processing_release": 0
            }
            prompts.append(new_p)
            prompt_map[cat_lower] = new_p
            logger(f"  -> Created New Category '{cat}': {min_dur}-{max_dur}ms, {avg_freq:.0f}Hz")

    # Save Prompts
    with open(PROMPTS_FILE, 'w') as f:
        json.dump(prompts, f, indent=4)
        
    logger("Learning Complete. ui_prompts.json updated.")
    
    # Maybe generate Level+1 excel? (Optional)
    # generate_hypothesis(..., level=level+1) logic could go here

