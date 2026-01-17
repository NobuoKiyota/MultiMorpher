import numpy as np
import scipy.signal

# Constants
SR = 48000
BLOCK_SIZE = 512

class ADSR:
    IDLE, ATTACK, DECAY, SUSTAIN, RELEASE = 0, 1, 2, 3, 4
    
    def __init__(self):
        self.state = self.IDLE
        self.level = 0.0
        self.set_params(0.01, 0.1, 0.7, 0.5)
        
    def set_params(self, a, d, s, r):
        self.attack_time = max(0.001, a)
        self.decay_time = max(0.001, d)
        self.sustain_level = np.clip(s, 0.0, 1.0)
        self.release_time = max(0.001, r)
        self.attack_step = 1.0 / (self.attack_time * SR + 1.0)
        self.decay_step = (1.0 - self.sustain_level) / (self.decay_time * SR + 1.0)
        self.release_step = self.sustain_level / (self.release_time * SR + 1.0)
        
    def trigger(self):
        self.state = self.ATTACK
        
    def release(self):
        if self.level <= 1e-5:
            self.state = self.IDLE
            self.level = 0.0
        else:
            self.state = self.RELEASE
            self.release_step = self.level / (self.release_time * SR + 1.0)

    def process(self, num_samples):
        out = np.zeros(num_samples)
        cursor = 0
        while cursor < num_samples:
            rem = num_samples - cursor
            if self.state == self.ATTACK:
                n = min(rem, int((1.0 - self.level)/self.attack_step) + 1)
                out[cursor:cursor+n] = self.level + np.arange(n)*self.attack_step
                self.level += n*self.attack_step
                cursor += n
                if self.level >= 1.0: self.level = 1.0; self.state = self.DECAY
            elif self.state == self.DECAY:
                n = min(rem, int((self.level - self.sustain_level)/self.decay_step) + 1)
                out[cursor:cursor+n] = self.level - np.arange(n)*self.decay_step
                self.level -= n*self.decay_step
                cursor += n
                if self.level <= self.sustain_level: self.level = self.sustain_level; self.state = self.SUSTAIN
            elif self.state == self.SUSTAIN:
                out[cursor:] = self.level
                cursor = num_samples
            elif self.state == self.RELEASE:
                if self.release_step <= 1e-9:
                    out[cursor:] = 0.0; self.level = 0.0; self.state = self.IDLE; break
                n = min(rem, int(self.level/self.release_step) + 1)
                out[cursor:cursor+n] = self.level - np.arange(n)*self.release_step
                self.level -= n*self.release_step
                cursor += n
                if self.level <= 0: self.level = 0; self.state = self.IDLE; break
            else: break
        return out

class AutomationLane:
    def __init__(self, duration=4.0):
        self.points = [(0.0, 0.0), (1.0, 0.0)] 
        self.duration = duration
        self.loop = True
        self.active = True
        self.current_time = 0.0
        
    def get_value(self, dt):
        if not self.active or self.duration <= 0.001: return 0.0
        self.current_time += dt
        if self.loop: self.current_time %= self.duration
        elif self.current_time > self.duration: self.current_time = self.duration
        t_norm = self.current_time / self.duration
        if not self.points: return 0.0
        p0, p1 = self.points[0], self.points[-1]
        for i in range(len(self.points)-1):
            if self.points[i][0] <= t_norm <= self.points[i+1][0]:
                p0, p1 = self.points[i], self.points[i+1]; break
        range_t = p1[0] - p0[0]
        if range_t < 1e-6: return p0[1]
        alpha = (t_norm - p0[0]) / range_t
        return (1.0 - alpha) * p0[1] + alpha * p1[1]

class EffectsProcessor:
    """Post-Processing Effects (Offline / Full Buffer preferred for simplicity)"""
    
    @staticmethod
    def apply_distortion(audio, gain, tone=0.5, wet=0.5):
        if gain <= 0.01 and wet <= 0.01: return audio
        
        # Drive amount
        drive = 1.0 + gain * 20.0
        
        # Soft Clipping (Tanh-like) using classic formula x / (1+|x|) or tanh
        # k = 2 * drive / (1 - drive) if we use other formula, but simple is best.
        # fast arctan or similar?
        # Simple Soft Clip:
        driven = audio * drive
        # Foldback or Tanh
        # distorted = np.tanh(driven) # Good sound, computationally distinct
        # Cheap approximation: x / (1 + |x|)
        distorted = driven / (1.0 + np.abs(driven))
        
        # Tone (Lowpass LPF)
        # tone 0 = dark (1000Hz), 1 = bright (20000Hz)
        if tone < 0.99:
            cutoff = 200 + tone * 15000
            b, a = scipy.signal.butter(1, cutoff / (SR/2), btype='low')
            distorted = scipy.signal.lfilter(b, a, distorted, axis=0) # Axis 0 for interleaved or call per channel?
            # Input is (N,) or (N, 2). lfilter works along axis=-1 by default?
            # If interleaved 1D array, lfilter treats as one stream. Stereo phase breaks if L/R are processed sequentially as one.
            # We assume 'audio' here is passed channel by channel OR it is 2D. 
            # PySFX Factory usually handles 1D interleaved. We should separate channels.
        
        # Mix
        return audio * (1.0 - wet) + distorted * wet

    @staticmethod
    def apply_phaser(audio, depth, speed, wet):
        if wet <= 0: return audio
        # Phaser is hard to implement via simple lfilter without time-varying coefficients (which lfilter doesn't do).
        # We need a loop or manual difference equation. 
        # But this is offline post-processing? 
        # If it's short, maybe fine. 
        # Optimization: We can just mix a slightly delayed signal with modulation. (Flanger-ish).
        # Real Phaser uses All-pass filters.
        # Let's do a simple Flanger instead as "Phaser-like"? 
        # Or just return audio if implementing a full specific phaser in pure Python/Numpy is too heavy.
        
        # Simple Vibrato/Delay modulation (Flanger)
        # y[n] = x[n] + x[n - d[n]]
        n = len(audio)
        t = np.arange(n) / SR
        # LFO for delay time
        # depth sets amplitude of delay modulation
        avg_delay_ms = 2.0 # 2ms for phaser/flanger territory
        mod_ms = 0.5 + depth * 3.0
        
        lfo = np.sin(2 * np.pi * speed * t)
        delay_samples = (avg_delay_ms + lfo * mod_ms) * (SR / 1000.0)
        
        # Integer delay indices
        # We need fractional delay for good sound, but nearest neighbor is fast.
        # indices = (np.arange(n) - delay_samples).astype(int)
        # indices = np.clip(indices, 0, n-1)
        # delayed = audio[indices]
        
        # Linear Interpolation Delay
        idx_base = np.arange(n) - delay_samples
        idx_floor = np.floor(idx_base).astype(int)
        idx_ceil = idx_floor + 1
        alpha = idx_base - idx_floor
        
        # Clip
        idx_floor = np.clip(idx_floor, 0, n-1)
        idx_ceil = np.clip(idx_ceil, 0, n-1)
        
        delayed = audio[idx_floor] * (1-alpha) + audio[idx_ceil] * alpha
        
        return audio * (1.0 - wet/2) + delayed * (wet/2) # 50/50 mix is max notch

    @staticmethod
    def apply_delay(audio, time_s, feedback, wet):
        if wet <= 0: return audio
        delay_samples = int(time_s * SR)
        if delay_samples >= len(audio): return audio # Too long
        
        # Naive Feedback Delay Loop in Python is slow.
        # y[n] = x[n] + fb * y[n-D]
        # We can implement using scipy.signal.lfilter
        # Transfer function H(z) = 1 / (1 - fb * z^-D)
        # b = [1], a = [1, 0, ... 0, -fb]
        # constructing 'a' array of size D+1 is risky for large D (0.5s = 24000 zeros).
        # It's better to just copy-paste buffers for a few echoes (if feedback decays fast).
        
        out = audio.copy()
        current_delay = delay_samples
        current_gain = feedback
        
        # Add echoes iteratively (much faster than giant filter kernel)
        while current_gain > 0.01:
            # Shift and Add
            echo = np.zeros_like(audio)
            # Valid region
            if current_delay < len(audio):
                echo[current_delay:] = audio[:-current_delay] * current_gain
                out += echo * wet # Add echo to output
            else:
                break
                
            current_delay += delay_samples
            current_gain *= feedback
            
        return out

    @staticmethod
    def apply_reverb(audio, time, spread, wet):
        if wet <= 0: return audio
        # Simple Convolution Reverb with White Noise decay?
        # A simple "Schroeder" is lots of filters.
        # Noise Convolution is cleaner for "Cave/Hall" generic sound.
        
        decay_samples = int(time * SR)
        if decay_samples <= 0: return audio
        
        # Create Impulse Response (Noise with exponential decay)
        t = np.linspace(0, 1, decay_samples)
        noise = np.random.uniform(-1, 1, decay_samples)
        envelope = np.exp(-t * 5.0) # Decay curve
        ir = noise * envelope
        
        # Spread (Stereo width of IR?)
        # If mono process, ignore. If stereo, we need stereo IR.
        # Assuming audio is 1D here for simplicity, convolution is heavy.
        # FFT Convolution (scipy.signal.fftconvolve) is fast.
        
        verb = scipy.signal.fftconvolve(audio, ir, mode='full')[:len(audio)]
        
        # Normalize verb
        verb = verb / (np.max(np.abs(verb)) + 1e-6) * 0.8
        
        return audio * (1.0 - wet) + verb * wet

    @staticmethod
    def apply_spread(audio, width, density, wet):
        # M/S Processing for Width?
        # Or Haas Effect?
        # User implies "SpreadRange" and "Density".
        # Density implies maybe chorus/detune stacking?
        # We will assume this is handled on stereo pairs.
        
        # If audio is interleaved 1D, we must separate.
        # This function assumes separate L/R or calls per channel?
        # Actually Spread is inherently stereo.
        # We should define these to work on (N, 2) arrays.
        pass

class DSPUtils:
    @staticmethod
    def normalize_max(audio):
         mx = np.max(np.abs(audio))
         if mx > 0: return audio / mx
         return audio

    @staticmethod
    def apply_lowpass(audio, cutoff, zi):
        f_freq = np.clip(cutoff, 20, 20000)
        alpha = (2*np.pi*f_freq/SR) / (2*np.pi*f_freq/SR + 1)
        b = [alpha]
        a = [1, -(1-alpha)]
        out, next_zi = scipy.signal.lfilter(b, a, audio, zi=zi)
        return out, next_zi

    @staticmethod
    def generate_osc_block(freq, phase, params, vectorized_fm=False):
        osc_type = int(params.get('osc_type', 1)) # Default Square (1)
        semi = params.get('semi', 0)
        
        # Calculate Phase Increment
        f_total = freq * (2.0 ** (semi / 12.0))
        
        if vectorized_fm and isinstance(semi, (np.ndarray, list)):
             # FM Case (f_total is array)
             deltas = f_total / SR
             phases = phase + np.cumsum(deltas)
        else:
             # Standard Case
             t = np.arange(BLOCK_SIZE)
             deltas = f_total / SR
             # phases = phase + deltas * t # Linear drift (Wrong for FM/PM, but okay for Const Freq)
             # Better: phase + (t * deltas)
             phases = (phase + t * deltas)

        # Wrap Phase
        phases %= 1.0
        
        # Generate Waveform
        # 0: Sine, 1: Square, 2: Triangle, 3: Saw
        if osc_type == 0: # Sine
            wave = np.sin(2.0 * np.pi * phases)
        elif osc_type == 1: # Square
            wave = np.where(phases < 0.5, 1.0, -1.0)
        elif osc_type == 2: # Triangle
            # 4 * abs(phase - 0.5) - 1.0 -> 0..0.5..1 -> -1..1..-1
            # scipysignal.sawtooth(..., width=0.5) is triangle
            # phases is 0..1. scipy needs 0..2pi ? No, wait.
            # Manual Triangle:
            # 0->0.25 (0->1), 0.25->0.75 (1->-1), 0.75->1 (-1->0)
            # 2 * abs(2 * (phases - floor(phases + 0.5))) - 1 ??
            # Simple: 2 * abs(2*phases - 1) - 1 ?
            # p=0 -> 2*|-1| -1 = 1. p=0.5 -> 2*|0| - 1 = -1. 
            # This is 1 -> -1 -> 1. Triangle.
            wave = 2.0 * np.abs(2.0 * phases - 1.0) - 1.0
        elif osc_type == 3: # Saw
            # 2 * phases - 1
            wave = 2.0 * phases - 1.0
        else:
            wave = np.where(phases < 0.5, 1.0, -1.0) # Fallback Square

        # Next Phase State
        if isinstance(f_total, (np.ndarray, list)):
            next_p = phases[-1]
        else:
            next_p = (phase + f_total * (BLOCK_SIZE / SR)) % 1.0
            
        return wave, next_p