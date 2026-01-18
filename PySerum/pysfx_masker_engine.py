import os
import random
import numpy as np
import scipy.io.wavfile
import scipy.signal
import soundfile as sf
import traceback

class QuartzMaskerEngine:
    def __init__(self, sr=48000):
        self.SR = sr

    def load_wav(self, path):
        try:
            data, sr = sf.read(path, dtype='float32') # Always float32
            # Mono to Stereo
            if len(data.shape) == 1:
                data = np.stack([data, data], axis=1)
            elif data.shape[1] > 2:
                data = data[:, :2]
                
            if sr != self.SR:
                # Basic Linear Resample for speed (or just skip for now)
                # For high quality offline, we could use scipy.signal.resample
                num_new_samples = int(len(data) * self.SR / sr)
                # To avoid huge memory on large files, simple linear interp is safer?
                # or scipy.signal.resample_poly
                # Let's use simple indexing for now as fallback
                # indices = np.linspace(0, len(data)-1, num_new_samples)
                # data = data[indices.astype(int)] # Nearest neighbor
                # Improved: use scipy for acceptable speed usually
                import scipy.signal
                if len(data) < self.SR * 60: # 1 min limit for heavy resample
                     data = scipy.signal.resample(data, num_new_samples)
                else: 
                     # Fallback nearest
                     indices = np.linspace(0, len(data)-1, num_new_samples)
                     data = data[indices.astype(int)]
            return data
        except Exception as e:
            print(f"Error loading {path}: {e}")
            return None

    def get_envelope(self, data, window_ms=10):
        """Extract smooth envelope from audio"""
        # Rectify
        abs_sig = np.abs(data)
        # Average L/R? Or Stereo Env?
        # Let's keep stereo env
        # Moving average or Lowpass
        # 10ms window
        win_len = int(self.SR * window_ms / 1000)
        # Fast way: uniform filter
        from scipy.ndimage import uniform_filter1d
        env = uniform_filter1d(abs_sig, size=win_len, axis=0)
        return env

    def generate_noise(self, n_samples, color='white', ch=2):
        """Generate colored noise"""
        if color == 'white':
            return np.random.uniform(-1, 1, (n_samples, ch))
        
        # Pink: 1/f. Voss algorithm is standard but complex.
        # Simple method: Filter white noise with -3db/oct filter?
        # Or simple spectral method (FFT -> scale -> IFFT) - accurate but block based
        # Let's use simple filtering (scipy)
        
        white = np.random.normal(0, 1, (n_samples, ch))
        
        if color == 'pink':
            # 10dB/dec filter approximation
            # b = [0.049922035, -0.095993537, 0.050612699, -0.004408786]
            # a = [1, -2.494956002,   2.017265875,  -0.522189400]
            # Reference: Paul Kellet
            b = np.array([0.049922035, -0.095993537, 0.050612699, -0.004408786])
            a = np.array([1, -2.494956002, 2.017265875, -0.522189400])
            pink = scipy.signal.lfilter(b, a, white, axis=0)
            # Normalize
            return pink / (np.max(np.abs(pink)) + 1e-6)
            
        elif color == 'brown':
             # 1/f^2 = Integration of white noise
             # Leaky integrator
             brown = np.cumsum(white, axis=0)
             # Highpass to remove DC drift
             # Simple DC block
             brown = brown - np.mean(brown, axis=0)
             # Normalize
             return brown / (np.max(np.abs(brown)) + 1e-6)
             
        return white

    def process(self, input_folder, output_folder, params, progress_cb=None):
        if not os.path.exists(output_folder): os.makedirs(output_folder)
        
        exts = ('.wav', '.aiff', '.flac', '.ogg', '.mp3')
        if os.path.isfile(input_folder):
             files = [input_folder]
             input_folder = os.path.dirname(input_folder)
        else:
             files = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.lower().endswith(exts)]
        
        if not files:
            print("No files found.")
            return

        noise_type = params.get("NoiseType", "White")
        # Params are fetched inside loop for per-file randomization if Rnd is checked
        # FilterLink need to be checked? 
        # Actually standard flow is resolve per iteration.
        pass

        for i, fpath in enumerate(files):
            if progress_cb: progress_cb(i, len(files))
            
            try:
                # Load
                data = self.load_wav(fpath)
                if data is None: continue
                
                N = len(data)
                
                # 1. Envelope Follower
                env = self.get_envelope(data, window_ms=20)
                
                # Resolve Random Params
                current_noise = noise_type
                if current_noise == "Random":
                    current_noise = random.choice(["White", "Pink", "Brown"])
                
                # Resolve Random Params (Float)
                def get_float_param(key, default):
                    # Check Random Flag
                    is_rnd = params.get(f"{key}_Rnd", False)
                    if is_rnd:
                         # Use Min/Max
                         vmin = float(params.get(f"{key}_Min", 0.0))
                         vmax = float(params.get(f"{key}_Max", 1.0))
                         return random.uniform(vmin, vmax)
                    else:
                         return float(params.get(key, default))

                current_mask = get_float_param("MaskAmount", 0.5)
                current_fade = get_float_param("FadeLen", 0.1)
                
                # Check Probability for previously boolean features
                invert_prob = get_float_param("InvertProb", 0.0)
                do_invert = (random.random() < invert_prob)
                
                reverse_prob = get_float_param("ReverseProb", 0.0)
                do_reverse = (random.random() < reverse_prob)
                
                filter_link_prob = get_float_param("FilterLinkProb", 0.0)
                filter_link = (random.random() < filter_link_prob)


                # 2. Noise Gen
                noise = self.generate_noise(N, color=current_noise.lower(), ch=2)
                
                # (FilterLink logic skipped for brevity/complexity)
                
                # 3. Apply Mask
                modulated_noise = noise * env * 1.5 
                
                # 4. Mixing
                orig_sig = data
                if do_invert:
                    orig_sig = -data
                    
                out = (1.0 - current_mask) * orig_sig + current_mask * modulated_noise
                
                # 5. Reverse & Fade
                if do_reverse:
                    out = out[::-1]
                
                flen_samples = int(N * current_fade)
                if flen_samples > 0:
                    fade_in = np.linspace(0, 1, flen_samples)
                    fade_out = np.linspace(1, 0, flen_samples)
                    fade_in = fade_in[:, np.newaxis]
                    fade_out = fade_out[:, np.newaxis]
                    out[:flen_samples] *= fade_in
                    out[-flen_samples:] *= fade_out
                
                # Save with Color Name
                fname = os.path.splitext(os.path.basename(fpath))[0]
                save_name = f"{fname}_{current_noise}.wav"
                sf.write(os.path.join(output_folder, save_name), out, self.SR)

                
            except Exception as e:
                print(f"Error {fpath}: {e}")
                traceback.print_exc()
