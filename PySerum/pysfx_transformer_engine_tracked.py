import os
import random
import numpy as np
import scipy.io.wavfile
import scipy.signal
# import soundfile as sf # original used sf
import soundfile as sf
import traceback

from pysfx_dsp import resample_by_position, apply_flutter_var
from pysfx_image_tracer import ImageTracer
from pysfx_engine import PyQuartzEngine

SR = 48000

class QuartzTransformerEngineTracked:
    def __init__(self):
        self.tracer = ImageTracer()
        self.engine_ref = PyQuartzEngine() # Use for effects
        
    def load_wav(self, path):
        try:
            data, sr = sf.read(path, dtype='float32') 
            if len(data.shape) == 1:
                data = np.stack([data, data], axis=1)
            elif data.shape[1] > 2:
                data = data[:, :2]
                
            if sr != SR:
                num_new_samples = int(len(data) * SR / sr)
                # Linear interp for speed in batch
                indices = np.linspace(0, len(data)-1, num_new_samples)
                # Quick stereo interp
                new_data = np.zeros((num_new_samples, 2), dtype=np.float32)
                for c in range(2):
                    new_data[:, c] = np.interp(indices, np.arange(len(data)), data[:, c])
                data = new_data
                
            return data
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return None

    def process_tracked(self, input_folder, output_folder, params, progress_cb=None):
        """
        Returns a list of dicts:
        [
            {
                "output_file": "filename.wav",
                "source_files": ["src1.wav", "src2.wav"],
                "params": { ... used params ... }
            },
            ...
        ]
        """
        if not os.path.exists(output_folder): os.makedirs(output_folder)
        
        exts = ('.wav', '.aiff', '.aif', '.flac', '.ogg', '.mp3')
        files = [f for f in os.listdir(input_folder) if f.lower().endswith(exts)]
        if len(files) < 1:
            print(f"No audio files found (checked {exts}).")
            return []

        iterations = int(params.get("Iteration", 10))
        logs = []
        
        # Helper for randomization support
        def get_val(key, default, record_target=None):
            val = default
            # Check if randomized
            if params.get(f"{key}_Rnd", False):
                vmin = float(params.get(f"{key}_Min", 0.0))
                vmax = float(params.get(f"{key}_Max", 1.0))
                if isinstance(default, int):
                    val = random.randint(int(vmin), int(vmax))
                else:
                    val = random.uniform(vmin, vmax)
            else:
                 val = params.get(key, default)
            
            if record_target is not None:
                record_target[key] = val
            return val

        for i in range(iterations):
            if progress_cb: progress_cb(i, iterations)
            
            # Record params for this instance
            instance_params = {}
            
            # 2. Select Sources based on MixCount
            mix_count = int(get_val("MixCount", 2, instance_params))
            if mix_count < 1: mix_count = 1
            if mix_count > 4: mix_count = 4 # Safety
            
            # Ensure we don't crash if mix_count > len(files)
            if mix_count > len(files): mix_count = len(files)
            
            selected_filenames = []
            for _ in range(mix_count):
                selected_filenames.append(random.choice(files))
            
            instance_params["Sources"] = str(selected_filenames) # Log readable
            
            datas = []
            for f in selected_filenames:
                d = self.load_wav(os.path.join(input_folder, f))
                if d is not None:
                    datas.append(d)
                
            if not datas: continue
            
            # Apply Start Offset
            offset_ratio = float(get_val("MorphStartOffset", 0.0, instance_params))
            
            processed_datas = []
            for d in datas:
                if offset_ratio > 0.0:
                    shift_samples = int(len(d) * offset_ratio)
                    d = np.roll(d, -shift_samples, axis=0)
                processed_datas.append(d)
            datas = processed_datas
            
            # Resize
            max_len = max([len(d) for d in datas])
            # Simple pad wrap
            datas_resized = []
            for d in datas:
                if len(d) < max_len:
                    pad_len = max_len - len(d)
                    d = np.pad(d, ((0, pad_len), (0,0)), mode='wrap')
                datas_resized.append(d[:max_len])
            datas = datas_resized
            
            # Mixing
            mixed = np.zeros_like(datas[0])
            if len(datas) == 1:
                mixed = datas[0]
            elif len(datas) == 2:
                morph_freq = float(get_val("MorphFreq", 0.5, instance_params))
                t = np.linspace(0, max_len/SR, max_len)
                morph_curve = 0.5 + 0.5 * np.sin(2 * np.pi * morph_freq * t)
                morph_curve = morph_curve[:, np.newaxis]
                mixed = datas[0] * (1.0 - morph_curve) + datas[1] * morph_curve
            else:
                for d in datas: mixed += d
                mixed /= len(datas)

            # Reverse
            rev_prob = float(get_val("ReverseProb", 0.0, None)) # Don't log prob, log result
            do_rev = (random.random() < rev_prob)
            instance_params["IsReverse"] = do_rev
            
            if do_rev:
                mixed = mixed[::-1]

            # Scratch / Stretch
            # Logic: Scratch (Position Map) OR Stretch (Respeed)
            scratch_prob = float(get_val("ScratchProb", 0.0, None))
            stretch_prob = float(get_val("StretchProb", 0.0, None))
            
            mode = "Raw"
            if random.random() < scratch_prob: mode = "Scratch"
            elif random.random() < stretch_prob: mode = "Stretch"
            
            instance_params["TimeMode"] = mode
            final_audio = mixed
            
            if mode == "Scratch":
                count = self.tracer.get_curve_count()
                if count > 0:
                    img_idx = random.randint(0, count - 1)
                    instance_params["CurveID"] = img_idx
                    curve = self.tracer.get_curve(img_idx, resolution=max_len)
                    final_audio = resample_by_position(mixed, curve)
            elif mode == "Stretch":
                count = self.tracer.get_curve_count()
                if count > 0:
                     img_idx = random.randint(0, count - 1)
                     instance_params["CurveID"] = img_idx
                     rate_curve_raw = self.tracer.get_curve(img_idx, resolution=1000)
                     # Integrate to get position
                     # rate 0.5 to 1.5
                     rate_curve = 0.5 + rate_curve_raw
                     pos_float = np.cumsum(rate_curve)
                     pos_curve = pos_float / pos_float[-1]
                     final_audio = resample_by_position(mixed, pos_curve)

            # Flutter
            flutter_prob = float(get_val("FlutterProb", 0.0, None))
            do_flut = (random.random() < flutter_prob)
            instance_params["IsFlutter"] = do_flut
            
            if do_flut:
                count = self.tracer.get_curve_count()
                if count > 0:
                    f_img = random.randint(0, count - 1)
                    f_curve = self.tracer.get_curve(f_img, resolution=len(final_audio))
                    f_rate = 5.0 + (f_curve * 25.0)
                    final_audio = apply_flutter_var(final_audio, f_rate, depth=0.8, sr=SR)

            # Save
            # Incorporate source name if MixCount=1
            base_name = "Mix"
            if len(selected_filenames) == 1:
                base_name = os.path.splitext(selected_filenames[0])[0]
            
            out_name = f"Tr_{i}_{base_name[:15]}_{random.randint(100,999)}.wav"
            out_path = os.path.join(output_folder, out_name)
            
            sf.write(out_path, final_audio, SR)
            
            logs.append({
                "output_file": out_name,
                "source_files": selected_filenames,
                "params": instance_params
            })
            
        return logs
