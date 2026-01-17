import numpy as np
import scipy.signal

# Constants usually shared, but can redefine or import.
SR = 48000

class EffectsProcessor:
    """Post-Processing Effects for PyQuartz SFX"""
    
    @staticmethod
    def apply_distortion(audio, gain, tone=0.5, wet=0.5):
        if gain <= 0.01 and wet <= 0.01: return audio
        
        # Drive amount
        drive = 1.0 + gain * 20.0
        
        # Simple Soft Clip: x / (1 + |x|)
        driven = audio * drive
        distorted = driven / (1.0 + np.abs(driven))
        
        # Tone (Lowpass LPF)
        if tone < 0.99:
            cutoff = 200 + tone * 15000
            b, a = scipy.signal.butter(1, cutoff / (SR/2), btype='low')
            try:
                distorted = scipy.signal.lfilter(b, a, distorted, axis=0)
            except:
                # Fallback if axis fail (1D array)
                distorted = scipy.signal.lfilter(b, a, distorted)
        
        # Mix
        return audio * (1.0 - wet) + distorted * wet

    @staticmethod
    def apply_phaser(audio, depth, speed, wet):
        if wet <= 0: return audio
        # Simple Vibrato/Delay modulation (Flanger-ish)
        n = len(audio)
        t = np.arange(n) / SR
        avg_delay_ms = 2.0 
        mod_ms = 0.5 + depth * 3.0
        
        lfo = np.sin(2 * np.pi * speed * t)
        delay_samples = (avg_delay_ms + lfo * mod_ms) * (SR / 1000.0)
        
        # Linear Interpolation Delay
        idx_base = np.arange(n) - delay_samples
        idx_floor = np.floor(idx_base).astype(int)
        idx_ceil = idx_floor + 1
        alpha = idx_base - idx_floor
        
        idx_floor = np.clip(idx_floor, 0, n-1)
        idx_ceil = np.clip(idx_ceil, 0, n-1)
        
        delayed = audio[idx_floor] * (1-alpha) + audio[idx_ceil] * alpha
        
        return audio * (1.0 - wet/2) + delayed * (wet/2)

    @staticmethod
    def apply_delay(audio, time_s, feedback, wet):
        if wet <= 0: return audio
        delay_samples = int(time_s * SR)
        if delay_samples >= len(audio): return audio 
        
        out = audio.copy()
        current_delay = delay_samples
        current_gain = feedback
        
        # Iterative Echoes
        while current_gain > 0.01:
            echo = np.zeros_like(audio)
            if current_delay < len(audio):
                echo[current_delay:] = audio[:-current_delay] * current_gain
                out += echo * wet
            else:
                break
            current_delay += delay_samples
            current_gain *= feedback
            
        return out

    @staticmethod
    def apply_reverb(audio, time, spread, wet):
        if wet <= 0: return audio
        decay_samples = int(time * SR)
        if decay_samples <= 0: return audio
        
        # Noise Convolution
        t = np.linspace(0, 1, decay_samples)
        noise = np.random.uniform(-1, 1, decay_samples)
        envelope = np.exp(-t * 5.0)
        ir = noise * envelope
        
        # FFT Convolve
        # If stereo, we might want decorrelated noise for R channel?
        # But simplify for now.
        verb = scipy.signal.fftconvolve(audio, ir, mode='full')[:len(audio)]
        mx = np.max(np.abs(verb))
        if mx > 0:
            verb = verb / mx * 0.8
        
        return audio * (1.0 - wet) + verb * wet

    @staticmethod
    def apply_spread(audio, width, density, wet):
        # Placeholder for Spread
        return audio
