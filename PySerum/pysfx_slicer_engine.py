import os
import glob
import numpy as np
import librosa
import soundfile as sf
import shutil
import traceback

class QuartzSlicerEngine:
    def __init__(self):
        pass

    def ensure_unique(self, path):
        if not os.path.exists(path): return path
        base, ext = os.path.splitext(path)
        count = 1
        while True:
            new_path = f"{base}_{count}{ext}"
            if not os.path.exists(new_path): return new_path
            count += 1

    def process_folder(self, input_dir, output_dir, params, progress_cb=None):
        """
        params: {
            'threshold_db': -30,
            'min_interval_ms': 500,
            'min_duration_ms': 100,
            'pad_ms': 50,
            'recursive': False,
            'mono': False,
            'norm': False
        }
        """
        if not os.path.exists(output_dir): os.makedirs(output_dir)

        search_path = input_dir
        if params.get('recursive', False):
            search_path = os.path.join(input_dir, "**")
        
        exts = ['*.wav', '*.mp3', '*.aif', '*.flac']
        files = []
        for e in exts:
            if params.get('recursive', False):
                files.extend(glob.glob(os.path.join(search_path, e), recursive=True))
            else:
                files.extend(glob.glob(os.path.join(input_dir, e)))
                
        thresh_db = float(params.get('threshold_db', -30))
        min_interval = float(params.get('min_interval_ms', 500)) / 1000.0
        min_dur = float(params.get('min_duration_ms', 100)) / 1000.0
        pad = float(params.get('pad_ms', 50)) / 1000.0
        do_mono = params.get('mono', False)
        do_norm = params.get('norm', False)

        total_files = len(files)
        total_slices_created = 0

        for i, fpath in enumerate(files):
            if progress_cb: progress_cb(i, total_files)
            
            try:
                # Load
                # Use librosa to load. Preserves stereo if mono=False
                y, sr = librosa.load(fpath, sr=None, mono=False)
                
                # Mono mix for detection
                if y.ndim > 1:
                    y_mono = librosa.to_mono(y)
                else:
                    y_mono = y
                    
                # Slicing Logic
                hop_length = 512
                frame_length = 1024
                rms = librosa.feature.rms(y=y_mono, frame_length=frame_length, hop_length=hop_length)[0]
                db_env = librosa.amplitude_to_db(rms, ref=np.max)
                
                is_over = db_env > thresh_db
                
                slices = []
                in_voice = False
                start_frame = 0
                cooldown_frames = 0
                wait_frames = int(min_interval * sr / hop_length)
                min_frames = int(min_dur * sr / hop_length)
                
                for idx, active in enumerate(is_over):
                    if cooldown_frames > 0:
                        cooldown_frames -= 1
                        if active: pass 
                        in_voice = False
                        continue
                    
                    if not in_voice and active:
                        in_voice = True
                        start_frame = max(0, idx - int(pad * sr / hop_length))
                    elif in_voice and not active:
                        in_voice = False
                        end_frame = idx + int(pad * sr / hop_length)
                        dur_frames = end_frame - start_frame
                        if dur_frames >= min_frames:
                            s_samp = max(0, start_frame * hop_length)
                            e_samp = min(y_mono.shape[-1], end_frame * hop_length)
                            slices.append((s_samp, e_samp))
                            cooldown_frames = wait_frames
                            
                # Handle End
                if in_voice:
                    end_frame = len(db_env)
                    dur_frames = end_frame - start_frame
                    if dur_frames >= min_frames:
                         s_samp = max(0, start_frame * hop_length)
                         e_samp = y_mono.shape[-1]
                         slices.append((s_samp, e_samp))
                
                # Export
                fname = os.path.basename(fpath)
                base, ext = os.path.splitext(fname)
                
                # If no slices, just copy? Or skip?
                # User request: "Audio Slicer: Trim silence". 
                # If no silence found (all loud), slice is full file.
                # If all silence, slice is empty.
                
                final_slices = slices
                if not slices:
                    # Check if file has ANY signal > threshold?
                    peak = np.max(db_env)
                    if peak > thresh_db:
                        # Whole file
                        final_slices = [(0, y.shape[-1])]
                    else:
                        # Silent file
                        continue

                for si, (start, end) in enumerate(final_slices):
                    if y.ndim > 1:
                        y_slice = y[:, start:end]
                    else:
                        y_slice = y[start:end]
                        
                    # Process
                    if do_mono and y_slice.ndim > 1:
                        y_slice = librosa.to_mono(y_slice)
                        
                    if do_norm:
                        max_val = np.max(np.abs(y_slice))
                        if max_val > 0:
                            y_slice = y_slice / max_val * 0.99
                            
                    # Name
                    suffix = f"_{si+1:02d}" if len(final_slices) > 1 else ""
                    out_name = f"{base}{suffix}{ext}"
                    out_path = os.path.join(output_dir, out_name)
                    out_path = self.ensure_unique(out_path)
                    
                    # Write
                    if y_slice.ndim > 1:
                        sf.write(out_path, y_slice.T, sr)
                    else:
                        sf.write(out_path, y_slice, sr)
                        
                    total_slices_created += 1
                    
            except Exception as e:
                print(f"Slicer Error {fpath}: {e}")
                traceback.print_exc()

        return total_slices_created
