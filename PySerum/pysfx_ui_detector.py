
import os
import numpy as np
import librosa
import soundfile as sf
import scipy.signal
# import pyworld as pw # Optional heavy dependency, use librosa for valid pitch now
import warnings

# Output Directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "Test_UI_Output")

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

# --- Scoring Functions (Dynamic) ---

def score_generic(y, sr, onset_idx, params):
    """
    Generic scoring based on params:
    - min_ms, max_ms
    - target_freq (Peak)
    """
    min_samp = int(params.get('min_ms', 50) / 1000 * sr)
    max_samp = int(params.get('max_ms', 500) / 1000 * sr)
    
    # Slice max window
    segment = y[onset_idx : onset_idx + max_samp]
    
    # 1. Duration Check (Energy decay)
    # If segment is shorter than min, force fail (unless end of file)
    if len(segment) < min_samp:
        # Check if it's end of file
        # If we are at end, we might accept it if it's short enough?
        # But 'min_ms' suggests it MUST be at least that long.
        return 0.0, None, 0.0

    # Calculate approximate duration based on energy
    rms = librosa.feature.rms(y=segment)[0]
    # Threshold for silence relative to peak
    thresh = np.max(rms) * 0.1
    active_frames = np.where(rms > thresh)[0]
    
    if len(active_frames) > 0:
        est_duration_samples = (active_frames[-1] - active_frames[0]) * 512 # hop
        est_duration_ms = est_duration_samples / sr * 1000
    else:
        est_duration_ms = 0
        
    # Score 1: Duration Fit
    # Optimal is between min and max
    if params['min_ms'] <= est_duration_ms <= params['max_ms']:
        dur_score = 1.0
    else:
        # Penalty
        center = (params['min_ms'] + params['max_ms']) / 2
        diff = abs(est_duration_ms - center)
        dur_score = max(0, 1.0 - (diff / center))

    # Score 2: Freq Peak
    # FFT
    S = np.abs(librosa.stft(segment))
    freqs = librosa.fft_frequencies(sr=sr)
    mean_spec = np.mean(S, axis=1)
    peak_idx = np.argmax(mean_spec)
    peak_freq = freqs[peak_idx]
    
    target_f = params.get('target_freq', 1000)
    # Simple relative distance
    # if match exactly -> 1.0, if double or half -> 0.0?
    if peak_freq == 0: peak_freq = 1 # avoid div 0
    
    # Log scale difference is better for pitch
    # But linear is requested "Freq Peak"
    diff_f = abs(peak_freq - target_f)
    if diff_f < 200:
        freq_score = 1.0
    elif diff_f < 1000:
        freq_score = 1.0 - (diff_f / 1000.0)
    else:
        freq_score = 0.0

    # Special Logic based on 'type' parameter
    # (Default to 'auto' which checks category name for backward compat)
    logic_type = params.get('type', 'auto').lower()
    cat = params.get('category', '').lower()
    
    type_score = 0.0
    
    # 1. MAJOR / HARMONY Checking
    if logic_type == 'major' or (logic_type == 'auto' and 'decision' in cat):
        # Harmony Check (Major)
        chroma = librosa.feature.chroma_stft(y=segment, sr=sr)
        avg_chroma = np.mean(chroma, axis=1)
        major_template = np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0])
        max_corr = 0.0
        norm_c = avg_chroma / (np.max(avg_chroma)+1e-9)
        for i in range(12):
            s = np.dot(norm_c, np.roll(major_template, i))/3.0
            max_corr = max(max_corr, s)
        type_score = max_corr
        
        # Weighted sum for Major
        total = (dur_score * 0.3) + (freq_score * 0.3) + (type_score * 0.4)
        
    # 2. FALL / PITCH DROP Checking
    elif logic_type == 'fall' or (logic_type == 'auto' and 'cancel' in cat):
        # Pitch Drop Check using Spectral Centroid (Cheaper than pyworld)
        cent = librosa.feature.spectral_centroid(y=segment, sr=sr)[0]
        if len(cent) > 5:
            # Check slope
            half = len(cent) // 2
            start_c = np.mean(cent[:half])
            end_c = np.mean(cent[half:])
            
            # Expect Drop
            if end_c < start_c * 0.8:
                # The stecper the better?
                type_score = 1.0
            else:
                type_score = 0.0
        else:
            type_score = 0.0
            
        total = (dur_score * 0.3) + (freq_score * 0.3) + (type_score * 0.4)
        
    else:
        # POINT / SIMPLE (Cursor or others)
        # Just Duration and Frequency
        total = (dur_score * 0.5) + (freq_score * 0.5)
    
    return total, segment, peak_freq

def process_audio(segment, sr, params):
    # Apply post-processing (dummy placeholders + simple ones)
    y = segment.copy()
    
    # Release/Fade out
    rel_ms = params.get('processing_release', 0)
    if rel_ms > 0:
        rel_samps = int(rel_ms / 1000 * sr)
        tail = np.zeros(rel_samps)
        y = np.concatenate([y, tail])
        # Fade out end
        f_len = min(len(y), int(0.05 * sr))
        y[-f_len:] *= np.linspace(1,0,f_len)
        
    # Wet/Reverb (Simulated with simple delay logic or just dummy for now)
    # The user asked for "Reverb". 
    wet = params.get('processing_reverb', 0)
    if wet > 0:
        # Simple fake reverb (noise decay) or just ignore to keep clean?
        # Let's use the Feedback Delay from pysfx_effects if available, 
        # or just a simple IR convolution if we had one.
        # For this script self-contained:
        pass # To be implemented or linked to effects
        
    # Normalize
    m = np.max(np.abs(y))
    if m > 0: y = y/m * 0.95
        
    return y

def dynamic_scan(config, root_dir, logger=print, status_callback=None):
    """
    config: List of dicts (from ui_prompts.json)
    """
    logger(f"Dynamic Scan Started in: {root_dir}")
    ensure_dir(OUTPUT_DIR)
    
    scanned_count = 0
    # Store best match per category per file
    # file_path -> { cat: {score, data} }
    best_results = {} 

    anim_frames = ["|", "/", "-", "\\"]
    anim_idx = 0

    for root, dirs, files in os.walk(root_dir):
        if "Output" in os.path.basename(root): continue
        if os.path.basename(root).startswith('.'): continue

        for f in files:
            if not f.lower().endswith(('.wav', '.aiff', '.flac')): continue
            scanned_count += 1
            
            if status_callback and scanned_count % 10 == 0:
                status_callback(f"Scanning... {scanned_count} ({anim_frames[anim_idx%4]})")
                anim_idx += 1
            
            full_path = os.path.join(root, f)
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    y, sr = librosa.load(full_path, sr=48000)
            except:
                continue

            # Onset detection
            rms = librosa.feature.rms(y=y, frame_length=1024, hop_length=512)[0]
            peaks, _ = scipy.signal.find_peaks(rms, height=0.01, distance=int(0.1 * sr / 512))
            if len(peaks) == 0: peaks = [0]
            
            times = librosa.times_like(rms, sr=sr, hop_length=512)

            for p_idx in peaks:
                onset_sample = p_idx * 512
                if onset_sample < 2000: onset_sample = 0
                
                # Check against ALL config models
                for model in config:
                    cat = model['category']
                    tolerance = model.get('tolerance', 50) / 100.0 
                    
                    score, seg, pk_freq = score_generic(y, sr, onset_sample, model)
                    
                    if score >= tolerance:
                        # Found a match!
                        # Check strict best logic
                        if not full_path in best_results: best_results[full_path] = {}
                        if not cat in best_results[full_path]: best_results[full_path][cat] = {'score': -1}
                        
                        if score > best_results[full_path][cat]['score']:
                             best_results[full_path][cat] = {
                                 'score': score,
                                 'segment': seg,
                                 'file_name': f,
                                 'pk_freq': pk_freq,
                                 'model': model
                             }
                             # Immediate feedback on hit
                             if status_callback:
                                 status_callback(f"HIT:Scanning... {scanned_count} (● Found {cat})")

        # Regular heartbeat update
        if status_callback and scanned_count % 10 == 0:
             status_callback(f"Scanning... {scanned_count} ({anim_frames[anim_idx%4]})")
             anim_idx += 1

    # Process and Save Bests
    extracted_count = 0
    logger("\n--- Extraction Phase ---")
    
    for fpath, cats in best_results.items():
        for cat, res in cats.items():
            if res['score'] == -1: continue
            
            model = res['model']
            seg = res['segment']
            
            # Post Process
            processed_y = process_audio(seg, 48000, model)
            
            # Save
            fname = f"{cat}_{res['file_name']}"
            out_p = os.path.join(OUTPUT_DIR, fname)
            sf.write(out_p, processed_y, 48000)
            
            logger(f"[{cat}] {res['file_name']} (Score: {res['score']:.2f}) -> Saved.")
            extracted_count += 1
            
    logger(f"=== Done. Extracted {extracted_count} sounds. ===")
    return extracted_count
