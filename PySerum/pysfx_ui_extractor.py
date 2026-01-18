
import warnings
warnings.filterwarnings("ignore")

import os
import numpy as np
import librosa
import soundfile as sf
import pyworld as pw
import shutil
import scipy.signal
from pysfx_ui_models import UI_MODELS
from pysfx_effects import EffectsProcessor

# Output Directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "Test_UI_Output")

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def calculate_score_cursor(y, sr, onset_idx, model):
    min_dur_samples = int(model['duration_range_ms'][0] / 1000 * sr)
    max_dur_samples = int(model['duration_range_ms'][1] / 1000 * sr)
    
    segment = y[onset_idx : onset_idx + max_dur_samples]
    if len(segment) < min_dur_samples:
        return 0.0, None

    # Attack Check
    attack_samples = int(model['attack_ms'] / 1000 * sr)
    if len(segment) > attack_samples:
        atk_seg = segment[:attack_samples]
        rest_seg = segment[attack_samples:]
        if np.max(np.abs(atk_seg)) < np.max(np.abs(rest_seg)) * 0.5:
             pass 

    # Frequency
    S = np.abs(librosa.stft(segment))
    freqs = librosa.fft_frequencies(sr=sr)
    mean_spec = np.mean(S, axis=1)
    peak_idx = np.argmax(mean_spec)
    peak_freq = freqs[peak_idx]

    target = model['features']['target_freq_peak']
    freq_range = model['freq_range_hz']
    
    if not (freq_range[0] <= peak_freq <= freq_range[1]):
        freq_score = 0.2
    else:
        dist = abs(peak_freq - target)
        freq_score = max(0, 1.0 - (dist / 1000.0))

    # Decay
    rms = librosa.feature.rms(y=segment)[0]
    if len(rms) > 3:
        tail_energy = np.mean(rms[-int(len(rms)*0.3):])
        head_energy = np.max(rms)
        decay_score = 1.0 if tail_energy < head_energy * 0.1 else 0.5
    else:
        decay_score = 0.5

    return (freq_score * 0.6) + (decay_score * 0.4), segment

def calculate_score_decision(y, sr, onset_idx, model):
    dur_ms = 250
    dur_samples = int(dur_ms / 1000 * sr)
    
    segment = y[onset_idx : onset_idx + dur_samples]
    if len(segment) < dur_samples: # Pad if close?
        if len(segment) > dur_samples * 0.8:
             # Pad with zeros
             segment = np.pad(segment, (0, dur_samples - len(segment)))
        else:
            return 0.0, None

    cent = librosa.feature.spectral_centroid(y=segment, sr=sr)
    avg_cent = np.mean(cent)
    centroid_score = 1.0 if avg_cent >= model['features']['spectral_centroid_min'] else 0.0
    if avg_cent < 1500:
        centroid_score = max(0, (avg_cent / 1500.0) * 0.5)

    chroma = librosa.feature.chroma_stft(y=segment, sr=sr)
    avg_chroma = np.mean(chroma, axis=1)
    
    major_template = np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0])
    max_corr = 0.0
    avg_chroma_norm = avg_chroma / (np.max(avg_chroma) + 1e-6)
    
    for i in range(12):
        temp = np.roll(major_template, i)
        score = np.dot(avg_chroma_norm, temp) / 3.0
        if score > max_corr:
            max_corr = score

    return (max_corr * 0.6) + (centroid_score * 0.4), segment

def calculate_score_cancel(y, sr, onset_idx, model):
    dur_ms = 150
    dur_samples = int(dur_ms / 1000 * sr)
    
    segment = y[onset_idx : onset_idx + dur_samples]
    if len(segment) < dur_samples: return 0.0, None

    # Pitch
    y_double = segment.astype(np.float64)
    # PyWorld harvest - robust pitch tracking
    # If pyworld fails or returns empty, handling is needed.
    # Note: pyworld might detect unvoiced as 0.
    try:
        f0, t = pw.harvest(y_double, sr, frame_period=5.0)
    except:
        f0 = np.zeros(10)
    
    f0 = f0[f0 > 0]
    if len(f0) < 5: return 0.0, None

    start_pitch = f0[0]
    min_pitch = np.min(f0)
    
    if start_pitch > model['features'].get('frequency_max', 2000):
        freq_score = 0.0
    else:
        freq_score = 1.0

    ratio = min_pitch / (start_pitch + 1e-6)
    target_range = model['features']['pitch_drop_ratio']
    
    dist_to_perfect = abs(ratio - 0.25)
    
    if ratio < 0.8: # Must drop somewhat
        pitch_score = max(0, 1.0 - (dist_to_perfect * 2))
    else:
        pitch_score = 0.0

    return (pitch_score * 0.8) + (freq_score * 0.2), segment

def process_and_save(segment, model_key, sr, filename, score):
    model = UI_MODELS[model_key]
    proc = model.get('processing', {})
    
    yillator = segment.copy()
    
    if model_key == "DECISION":
        rel_ms = proc.get('add_release_ms', 0)
        rel_samples = int(rel_ms / 1000 * sr)
        if rel_samples > 0:
            tail = np.zeros(rel_samples)
            yillator = np.concatenate([yillator, tail])
            fade_len = int(0.01 * sr)
            if len(yillator) > fade_len:
                yillator[-fade_len:] *= np.linspace(1, 0, fade_len)

        rv = proc.get('reverb', {})
        yillator = EffectsProcessor.apply_reverb(
            yillator, 
            time=rv.get('time_s', 0.5), 
            spread=rv.get('spread', 0.5), 
            wet=rv.get('wet', 0.2)
        )
    
    elif model_key == "CANCEL":
        fi_ms = proc.get('fade_in_ms', 0)
        fo_ms = proc.get('fade_out_ms', 0)
        fi_samps = int(fi_ms / 1000 * sr)
        fo_samps = int(fo_ms / 1000 * sr)
        
        if fi_samps > 0 and len(yillator) > fi_samps:
            yillator[:fi_samps] *= np.linspace(0, 1, fi_samps)
        if fo_samps > 0 and len(yillator) > fo_samps:
            yillator[-fo_samps:] *= np.linspace(1, 0, fo_samps)
            
    max_val = np.max(np.abs(yillator))
    if max_val > 0:
        yillator = yillator / max_val * 0.9

    out_name = f"{model_key}_{score:.2f}_{filename}"
    out_path = os.path.join(OUTPUT_DIR, out_name)
    sf.write(out_path, yillator, sr)
    return out_path

def scan_and_extract(root_dir, logger=print, status_callback=None):
    logger(f"=== Quartz UI Extractor Scan Start ===")
    logger(f"Scanning Directory: {root_dir}")
    ensure_dir(OUTPUT_DIR)
    
    candidates = []
    scanned_count = 0
    
    # Progress animation frames
    anim_frames = ["|--->---|", "-|--->---|", "--|--->---|", "---|--->---|", "----|--->---|", "-----|--->|", "------|---|", "-------|--|", "--------|-|", "---------||"]
    anim_idx = 0

    for root, dirs, files in os.walk(root_dir):
        # Exclude output directories
        if "Test_UI_Output" in os.path.basename(root) or "Output" in os.path.basename(root): 
            logger(f"Skipping excluded folder: {root}")
            continue
            
        # Optional: Skipping hidden folders
        if os.path.basename(root).startswith('.'):
            continue

        for f in files:
            if not f.lower().endswith(('.wav', '.aiff', '.flac')): continue
            
            scanned_count += 1
            if status_callback and scanned_count % 5 == 0:
                anim_str = anim_frames[anim_idx % len(anim_frames)]
                status_callback(f"Scanning... {scanned_count} files {anim_str}")
                anim_idx += 1
            
            full_path = os.path.join(root, f)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    y, sr = librosa.load(full_path, sr=48000)
            except Exception as e:
                logger(f"Error loading {f}: {e}")
                continue
            
            rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=512)[0]
            
            peaks, _ = scipy.signal.find_peaks(rms, height=0.01, distance=int(0.2 * sr / 512))
            
            if len(peaks) == 0 and len(y) > 0 and rms[0] > 0.01:
                 peaks = [0]
            
            # Per-file best match storage
            best_in_file = {
                "CURSOR_MOVE": {"score": 0.0, "data": None},
                "DECISION": {"score": 0.0, "data": None},
                "CANCEL": {"score": 0.0, "data": None}
            }

            times = librosa.times_like(rms, sr=sr, hop_length=512)

            for p_idx in peaks:
                onset_sample = p_idx * 512
                if onset_sample < 4000: onset_sample = 0
                
                # Check Cursor
                s_cur, seg_cur = calculate_score_cursor(y, sr, onset_sample, UI_MODELS["CURSOR_MOVE"])
                if s_cur > best_in_file["CURSOR_MOVE"]["score"]:
                    best_in_file["CURSOR_MOVE"] = {"score": s_cur, "data": { "type": "CURSOR_MOVE", "score": s_cur, "file": f, "pos": times[p_idx], "segment": seg_cur }}

                # Check Decision
                s_dec, seg_dec = calculate_score_decision(y, sr, onset_sample, UI_MODELS["DECISION"])
                if s_dec > best_in_file["DECISION"]["score"]:
                    best_in_file["DECISION"] = {"score": s_dec, "data": { "type": "DECISION", "score": s_dec, "file": f, "pos": times[p_idx], "segment": seg_dec }}

                # Check Cancel
                s_can, seg_can = calculate_score_cancel(y, sr, onset_sample, UI_MODELS["CANCEL"])
                if s_can > best_in_file["CANCEL"]["score"]:
                    best_in_file["CANCEL"] = {"score": s_can, "data": { "type": "CANCEL", "score": s_can, "file": f, "pos": times[p_idx], "segment": seg_can }}

            # Add bests to candidates if threshold met
            # Only add ONE entry per category per file
            if best_in_file["CURSOR_MOVE"]["score"] > 0.4:
                candidates.append(best_in_file["CURSOR_MOVE"]["data"])
            
            if best_in_file["DECISION"]["score"] > 0.4:
                candidates.append(best_in_file["DECISION"]["data"])
                
            if best_in_file["CANCEL"]["score"] > 0.4:
                candidates.append(best_in_file["CANCEL"]["data"])

    logger(f"\n--- Scan Complete: {scanned_count} files processed ---")
    logger("--- Extraction Results ---")
    for cat in ["CURSOR_MOVE", "DECISION", "CANCEL"]:
        cands = [c for c in candidates if c['type'] == cat]
        cands.sort(key=lambda x: x['score'], reverse=True)
        top_cands = cands[:3]
        
        if top_cands:
            logger(f"[{cat}] Top Matches:")
            for i, c in enumerate(top_cands):
                out_path = process_and_save(c['segment'], cat, 48000, c['file'], c['score'])
                logger(f"  {i+1}. {c['file']} (Score: {c['score']:.2f}) -> {os.path.basename(out_path)}")
        else:
            logger(f"[{cat}] No matches found.")

if __name__ == "__main__":
    target_dir = os.path.dirname(os.path.abspath(__file__))
    scan_and_extract(target_dir)
