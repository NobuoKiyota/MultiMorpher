import numpy as np
import scipy.ndimage

class MorphProcessors:
    
    @staticmethod
    def ensure_shape(a, b):
        """Truncates to minimum common shape (frames)."""
        min_cols = min(a.shape[1], b.shape[1])
        return a[:, :min_cols], b[:, :min_cols]

    @staticmethod
    def spectral_blend(stft_a, stft_b, split_freq_hz, sr, n_fft):
        """
        Mixes Low Freqs of A with High Freqs of B.
        """
        a, b = MorphProcessors.ensure_shape(stft_a, stft_b)
        
        freqs = np.linspace(0, sr/2, 1 + n_fft//2)
        # Find bin index
        split_idx = np.searchsorted(freqs, split_freq_hz)
        
        # Create mask
        # 1.0 for Low (Index < Split), 0.0 for High
        mask = np.zeros((a.shape[0], 1))
        mask[:split_idx, :] = 1.0
        
        # Smooth mask edge to prevent clicking
        # Simple 3-bin smoothing
        if split_idx > 1 and split_idx < a.shape[0]-2:
            mask[split_idx-1, 0] = 0.75
            mask[split_idx, 0] = 0.5
            mask[split_idx+1, 0] = 0.25
        
        # Blend
        combined = a * mask + b * (1.0 - mask)
        return combined

    @staticmethod
    def interpolate(stft_a, stft_b, mix):
        """
        Linear Magnitude Interpolation with Phase Locking.
        mix: 0.0 (A) -> 1.0 (B)
        """
        a, b = MorphProcessors.ensure_shape(stft_a, stft_b)
        
        mag_a = np.abs(a)
        mag_b = np.abs(b)
        
        # Interpolate Magnitude
        mag_mix = mag_a * (1.0 - mix) + mag_b * mix
        
        # Phase Locking: Use phase of whichever source is dominant for that bin?
        # Or simple hard switch at 0.5?
        # Hard switch is safer for transients.
        if mix < 0.5:
            phase = np.angle(a)
        else:
            phase = np.angle(b)
            
        return mag_mix * np.exp(1j * phase)

    @staticmethod
    def cross_synthesis(stft_carrier, stft_modulator, envelope_smoothness=10):
        """
        Imprints spectral envelope of Modulator onto Carrier.
        """
        c, m = MorphProcessors.ensure_shape(stft_carrier, stft_modulator)
        
        mag_c = np.abs(c)
        mag_m = np.abs(m)
        
        # 1. Extract Envelope from Modulator
        # Simple method: Gaussian filter over frequency axis
        env_m = scipy.ndimage.gaussian_filter1d(mag_m, sigma=envelope_smoothness, axis=0)
        
        # 2. Flatten Carrier (Whitening)
        env_c = scipy.ndimage.gaussian_filter1d(mag_c, sigma=envelope_smoothness, axis=0)
        # Avoid div by zero
        env_c = np.maximum(env_c, 1e-6)
        
        whitened_c = c / env_c
        
        # 3. Apply Modulator Envelope
        result = whitened_c * env_m
        return result

    @staticmethod
    def formant_shift(stft_src, shift, n_fft):
        """
        Resamples magnitude spectrum axis.
        shift > 1.0: Spectrum stretches up (Smurf/High) - actually shift UP means formants move UP => Higher timbre.
        shift < 1.0: Spectrum shrinks down (Giant/Low).
        """
        mag = np.abs(stft_src)
        phase = np.angle(stft_src)
        
        rows, cols = mag.shape
        
        # X-axis (Frequency bins)
        x = np.arange(rows)
        
        # New X-axis (Inverse of shift)
        # If we want to shift Formants UP (x2), we need to grab data from LOWER frequencies.
        # Wait: Moving Formant at 500Hz to 1000Hz (Shift=2.0). 
        # Current bin 100 needs data from bin 50.
        x_new = x / shift 
        
        # Interpolate for each column is slow in Python loop.
        # Use map_coordinates for heavy vectorization?
        # Or just simple per-column interpolation if fast enough. 
        # Let's use a simple per-column resize logic or approximate for speed.
        
        new_mag = np.zeros_like(mag)
        
        # Vectorized interpolation? 
        # We can treat this as an image resize on Axis 0.
        # scipy.ndimage.zoom is easy but fixed grid.
        # Let's try row-mapping.
        
        # Limit to valid range
        x_new = np.clip(x_new, 0, rows-1)
        
        # Nearest neighbor for extreme speed? No, sound bad. Linear.
        # Linear Interp:
        x_l = np.floor(x_new).astype(int)
        x_h = np.ceil(x_new).astype(int)
        alpha = (x_new - x_l)[:, np.newaxis] # broadcast to cols
        
        # Gather
        val_l = mag[x_l, :] # advanced indexing
        val_h = mag[x_h, :]
        
        new_mag = val_l * (1.0 - alpha) + val_h * alpha
        
        return new_mag * np.exp(1j * phase)

