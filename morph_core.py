import numpy as np
import librosa
import soundfile as sf
import pyworld as pw
import scipy.signal

class MorphCore:
    def __init__(self, sr=48000, frame_period=5.0):
        self.sr = sr
        self.frame_period = frame_period
        
        # Caches
        self.source_a = None # { 'audio': np.array, 'stft': np.array, 'world': dict }
        self.source_b = None
        self.result_audio = None
        
        # Settings
        self.n_fft = 2048
        self.hop_length = int(self.sr * (self.frame_period / 1000.0))

    def load_source(self, filepath, slot='A'):
        """Loads audio and performs initial lightweight analysis."""
        try:
            # lightweight load
            y, orig_sr = sf.read(filepath)
            if orig_sr != self.sr:
                # Fast resample if needed, or use librosa for better quality
                y = librosa.resample(y, orig_sr=orig_sr, target_sr=self.sr)
                
            # Mono mix if needed for analysis
            if y.ndim > 1:
                y_mono = np.mean(y, axis=1)
            else:
                y_mono = y
                
            # Store
            data = {
                'audio': y_mono, 
                'stft': None,   # Lazy load
                'world': None,  # Lazy load
                'len': len(y_mono)
            }
            
            if slot == 'A': self.source_a = data
            elif slot == 'B': self.source_b = data
            
            return True, f"Loaded {len(y_mono)/self.sr:.2f}s"
        except Exception as e:
            return False, str(e)

    def get_stft(self, slot='A'):
        """Lazy computes STFT."""
        src = self.source_a if slot == 'A' else self.source_b
        if src is None: return None
        
        if src['stft'] is None:
            # Compute STFT
            # Complex STFT: (1 + n_fft/2, frames)
            src['stft'] = librosa.stft(src['audio'], n_fft=self.n_fft, hop_length=self.hop_length)
            
        return src['stft']

    def get_world(self, slot='A'):
        """Lazy computes WORLD parameters (Heavy)."""
        src = self.source_a if slot == 'A' else self.source_b
        if src is None: return None
        
        if src['world'] is None:
            y = src['audio'].astype(np.float64)
            _f0, t = pw.harvest(y, self.sr, frame_period=self.frame_period)
            _sp = pw.cheaptrick(y, _f0, t, self.sr)
            _ap = pw.d4c(y, _f0, t, self.sr)
            src['world'] = {'f0': _f0, 'sp': _sp, 'ap': _ap, 't': t}
            
        return src['world']

    def match_length(self, source_data, target_len):
        """Simple time-stretch to match length (used for sync)."""
        # Linear interp for raw audio or STFT stretch?
        # For lightweight, we might just loop or pad?
        # User wants "Interpolation", usually implies 1:1 mapping.
        # We will use simple resampling (speed change) to match lengths for now.
        pass # To be implemented in Processors

    def istft(self, stft_matrix):
        """Inverse STFT wrapper."""
        return librosa.istft(stft_matrix, hop_length=self.hop_length)

    def synthesize_world(self, f0, sp, ap):
        """WORLD synthesis wrapper."""
        return pw.synthesize(f0, sp, ap, self.sr, frame_period=self.frame_period)

