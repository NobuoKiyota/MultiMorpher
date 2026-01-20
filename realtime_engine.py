import sounddevice as sd
import numpy as np
import librosa
import threading
import time
from processors import MorphProcessors

class RealtimeEngine:
    def __init__(self, sr=48000, block_size=2048):
        self.sr = sr
        self.block_size = block_size
        self.hop_length = block_size // 4 # overlap 75% for smooth STFT
        
        # Audio Buffers (Looping)
        self.buffer_a = None
        self.buffer_b = None
        
        # Playhead (sample index)
        self.cursor = 0
        
        # Parameters (Thread-safe-ish via atomic read)
        self.active = False
        self.recording = False
        self.recorded_frames = []
        self.mode = "Spectrum Blender" # Default
        self.params = {
            "split_freq": 1000,
            "mix": 0.5,
            "smooth": 10,
            "shift": 1.0
        }
        
        self.stream = None
        self._stft_buffer = np.zeros(self.block_size) # for accum
        
    def load_buffers(self, y_a, y_b=None):
        """Loads audio data for streaming."""
        self.stop()
        self.buffer_a = y_a
        
        # Ensure B matches length of A for simple looping
        if y_b is not None:
             # Resize B to match A
             if len(y_b) != len(y_a):
                 y_b = librosa.util.fix_length(y_b, size=len(y_a))
             self.buffer_b = y_b
        else:
             self.buffer_b = None
             
        self.cursor = 0
        
    def start(self):
        if self.buffer_a is None: return
        self.active = True
        
        # Audio Callback
        def callback(outdata, frames, time, status):
            if status: print(status)
            
            # 1. Get chunk from buffers
            start = self.cursor
            end = start + frames
            
            # Handle Looping
            chunk_a = np.zeros(frames, dtype=np.float32)
            chunk_b = np.zeros(frames, dtype=np.float32)
            
            p_len = len(self.buffer_a)
            
            if end > p_len:
                # Wrap around
                remain = p_len - start
                chunk_a[:remain] = self.buffer_a[start:]
                chunk_a[remain:] = self.buffer_a[:frames-remain]
                
                if self.buffer_b is not None:
                    chunk_b[:remain] = self.buffer_b[start:]
                    chunk_b[remain:] = self.buffer_b[:frames-remain]
                
                self.cursor = frames - remain
            else:
                chunk_a[:] = self.buffer_a[start:end]
                if self.buffer_b is not None:
                    chunk_b[:] = self.buffer_b[start:end]
                self.cursor = end
                
            # 2. Process (STFT -> FX -> ISTFT)
            # Full block STFT is too slow for per-sample callback usually?
            # Actually, `frames` here corresponds to buffer size.
            
            try:
                # We need a windowed STFT. 
                # Calculating STFT on just this small block (e.g. 512 samples) has poor frequency resolution.
                # Usually we need a sliding window.
                # For this prototype, we'll try a simplified "Spectral Filter" approach 
                # or just use librosa.stft on this chunk (might click at edges due to windowing).
                
                # Better approach for real-time STFT: Overlap-Add. 
                # Complexity is high.
                # Let's try to perform the Morphing in Time Domain where possible, 
                # or use very efficient FFT size = data size.
                
                # Check Mode
                # For "Streaming", maybe we accept some latency (latency = block size).
                # If block_size = 2048 (~42ms), it's okay.
                
                # FFT
                n_fft = 2048 # Use power of two
                # If chunk is smaller, pad it
                pad_len = 0
                if len(chunk_a) < n_fft:
                     pad_len = n_fft - len(chunk_a)
                     in_a = np.pad(chunk_a, (0, pad_len))
                     in_b = np.pad(chunk_b, (0, pad_len)) if self.buffer_b is not None else None
                else:
                     in_a = chunk_a
                     in_b = chunk_b
                
                # Analyze
                S_a = np.fft.rfft(in_a)
                S_b = np.fft.rfft(in_b) if in_b is not None else None
                
                # Process
                P = None
                mode = self.mode
                
                # Freqs for blender
                # rfft returns n_fft//2 + 1 bins
                # freqs = np.linspace(0, sr/2, len(S_a))
                
                if mode == "Spectrum Blender" and S_b is not None:
                    # Logic needs to work on 1D complex array
                    split = self.params["split_freq"]
                    # Map Hz to bin
                    nyquist = self.sr / 2
                    bin_idx = int((split / nyquist) * len(S_a))
                    bin_idx = np.clip(bin_idx, 0, len(S_a))
                    
                    P = S_a.copy()
                    P[bin_idx:] = S_b[bin_idx:] # High part from B
                    
                elif mode == "Interpolator" and S_b is not None:
                    mix = self.params["mix"]
                    # Linear Mag
                    mag_a = np.abs(S_a)
                    mag_b = np.abs(S_b)
                    ph_a = np.angle(S_a)
                    # Mix Mag
                    mag_m = mag_a * (1-mix) + mag_b * mix
                    P = mag_m * np.exp(1j * ph_a)
                    
                elif mode == "Cross Synthesis" and S_b is not None:
                    # Simple spectral envelope impression
                    # Smooth B
                    mag_b = np.abs(S_b)
                    # Simple Lowpass on Mag (Moving Average)
                    k = self.params["smooth"]
                    env = np.convolve(mag_b, np.ones(k)/k, mode='same')
                    
                    # Whitening A
                    mag_a = np.abs(S_a)
                    env_a = np.convolve(mag_a, np.ones(k)/k, mode='same') + 1e-6
                    white_a = S_a / env_a
                    
                    P = white_a * env
                    
                elif mode == "Formant Shifter":
                    # Resample Axis
                    shift = self.params["shift"]
                    # Naive resampling of magnitude
                    mag = np.abs(S_a)
                    ph = np.angle(S_a)
                    x = np.arange(len(mag))
                    x_new = x / shift
                    mag_new = np.interp(x_new, x, mag, left=0, right=0)
                    P = mag_new * np.exp(1j * ph)
                
                else:
                    P = S_a # Bypass
                
                # ... (Existing Processing) ...
                
                # Y-Axis Effect: Spectral Filter (Lowpass)
                # If filter_cutoff is present and < 1.0 (1.0 = Open)
                cutoff_norm = self.params.get("filter_cutoff", 1.0)
                if cutoff_norm < 0.99 and P is not None:
                     # Simple brickwall or steep rolloff
                     n_bins = len(P)
                     cut_idx = int(cutoff_norm * n_bins)
                     # Smooth fade out
                     fade = 10
                     if cut_idx < n_bins:
                         P[cut_idx:] = 0
                         if cut_idx > fade:
                             fade_win = np.linspace(1, 0, fade)
                             P[cut_idx-fade:cut_idx] *= fade_win
                             
                # Inverse
                y_out = np.fft.irfft(P if P is not None else S_a)
                
                # De-pad
                if pad_len > 0:
                    y_out = y_out[:-pad_len]
                
                # Windowing to smooth edges
                fade = 32
                if len(y_out) > fade*2:
                    win = np.ones(len(y_out))
                    win[:fade] = np.linspace(0, 1, fade)
                    win[-fade:] = np.linspace(1, 0, fade)
                    y_out *= win
                
                # Output
                out_final = y_out.reshape(-1, 1) * 0.8
                outdata[:] = out_final
                
                # Recording
                if self.recording:
                    self.recorded_frames.append(out_final.copy())
                    
            except Exception as e:
                print(f"Callback Error: {e}")
                outdata.fill(0)

        # Start Stream
        self.stream = sd.OutputStream(samplerate=self.sr, blocksize=self.block_size, channels=1, callback=callback)
        self.stream.start()

    def start_recording(self):
        self.recorded_frames = []
        self.recording = True
        
    def stop_recording(self, filename="output/rec_live.wav"):
        self.recording = False
        if not self.recorded_frames: return
        
        # Save
        full_arr = np.concatenate(self.recorded_frames, axis=0)
        import soundfile as sf
        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        sf.write(filename, full_arr, self.sr)
        self.recorded_frames = []
        return filename

    def stop(self):
        self.recording = False
        self.active = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def set_param(self, key, value):
        self.params[key] = value

