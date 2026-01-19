import os
import glob
import numpy as np
import soundfile as sf
import random
import traceback

class QuartzNormalizerEngine:
    def __init__(self):
        pass

    def process_single_file(self, fpath, output_path, params):
        try:
            data, sr = sf.read(fpath, dtype='float32')
            if len(data.shape) == 1: data = np.stack([data, data], axis=1) # Stereo
            
            # 1. Trim Silence (Simple Energy)
            mag = np.abs(data).mean(axis=1)
            mask = mag > 0.001
            if not np.any(mask): return False
            
            coords = np.where(mask)[0]
            start, end = coords[0], coords[-1]
            trimmed = data[start:end+1]
            
            # 2. Stretch
            t_min = float(params.get('target_time_min', 1.0))
            t_max = float(params.get('target_time_max', 1.0))
            target_dur = random.uniform(t_min, t_max)
            target_len = int(target_dur * sr)
            
            if target_len < 100: return False
            
            # Linear Interp
            curr_len = len(trimmed)
            src_x = np.linspace(0, 1, curr_len)
            dst_x = np.linspace(0, 1, target_len)
            
            stretched = np.zeros((target_len, 2), dtype=np.float32)
            for ch in range(2):
                stretched[:, ch] = np.interp(dst_x, src_x, trimmed[:, ch])
                
            # 3. Envelope
            atk_min = float(params.get('attack_rate_min', 0.0))
            atk_max = float(params.get('attack_rate_max', 0.0))
            rel_min = float(params.get('release_rate_min', 0.0))
            rel_max = float(params.get('release_rate_max', 0.1))
            
            atk_rate = random.uniform(atk_min, atk_max)
            rel_rate = random.uniform(rel_min, rel_max)
            
            # Max 20% limit for env
            limit_len = target_len * 0.2
            atk_len = int(limit_len * atk_rate)
            rel_len = int(limit_len * rel_rate)
            
            if atk_len > 0:
                curve = np.linspace(0.0, 1.0, atk_len)
                stretched[:atk_len] *= curve[:, np.newaxis]
                
            if rel_len > 0:
                curve = np.linspace(1.0, 0.0, rel_len)
                stretched[-rel_len:] *= curve[:, np.newaxis]
                
            sf.write(output_path, stretched, sr)
            return True
            
        except Exception as e:
            print(f"Norm Error {fpath}: {e}")
            traceback.print_exc()
            return False

    def process_folder(self, input_dir, output_dir, params, progress_cb=None):
        if not os.path.exists(output_dir): os.makedirs(output_dir)

        exts = ['*.wav', '*.mp3', '*.aif', '*.flac']
        files = []
        for e in exts:
            files.extend(glob.glob(os.path.join(input_dir, e)))
            
        total_files = len(files)
        
        for i, fpath in enumerate(files):
            if progress_cb: progress_cb(i, total_files)
            
            base = os.path.splitext(os.path.basename(fpath))[0]
            out_name = f"{base}_Norm.wav"
            out_path = os.path.join(output_dir, out_name)
            
            self.process_single_file(fpath, out_path, params)
