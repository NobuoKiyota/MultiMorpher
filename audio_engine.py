import librosa
import numpy as np
import soundfile as sf
import os
import scipy.signal
import pyworld as pw
from scipy.interpolate import PchipInterpolator

class AudioEngine:
    def __init__(self):
        self.sr = 44100
        self.frame_period = 5.0
        
        # Raw Data
        self.raw_a = None
        self.raw_b = None
        self.raw_c = None
        self.raw_d = None
        
        # Analyzed
        self.data_a = None
        self.data_b = None
        self.data_c = None
        self.data_d = None
        
        # Public properties
        self.y_a = None 
        self.y_b = None
        self.y_c = None
        self.y_d = None
        
        self.generated_audio = None
        self.processed_audio = None # Final output (can be stereo)
        
        self.last_trajectory_x = None
        self.last_trajectory_y = None

    def _load_file_fast(self, filepath):
        try:
            data, samplerate = sf.read(filepath)
            if len(data.shape) > 1: data = np.mean(data, axis=1) # Force mono for analysis source
            if samplerate != self.sr:
                data = librosa.resample(data, orig_sr=samplerate, target_sr=self.sr)
            return data.astype(np.float64)
        except Exception:
            y, _ = librosa.load(filepath, sr=self.sr, mono=True)
            return y.astype(np.float64)

    def _analyze(self, y):
        y = np.ascontiguousarray(y.astype(np.float64))
        try:
            _f0, t = pw.harvest(y, self.sr, frame_period=self.frame_period)
            _sp = pw.cheaptrick(y, _f0, t, self.sr)
            _ap = pw.d4c(y, _f0, t, self.sr)
            return {'f0': _f0, 'sp': _sp, 'ap': _ap, 'len': len(y)}
        except: return None

    def _align_and_analyze(self, raw_src, raw_master):
        if raw_src is None: return None
        if raw_master is None: return self._analyze(raw_src)
        
        len_src = len(raw_src)
        len_dst = len(raw_master)
        if len_src == 0 or len_dst == 0: return None
        
        rate = len_src / len_dst
        if abs(rate - 1.0) > 0.001:
             y_aligned = librosa.effects.time_stretch(raw_src, rate=rate)
        else:
             y_aligned = raw_src.copy()
             
        if len(y_aligned) > len_dst:
            y_aligned = y_aligned[:len_dst]
        elif len(y_aligned) < len_dst:
            y_aligned = np.pad(y_aligned, (0, len_dst - len(y_aligned)))
            
        return self._analyze(y_aligned)

    def load_source_a(self, filepath):
        self.raw_a = self._load_file_fast(filepath)
        self.y_a = self.raw_a
        self.data_a = self._analyze(self.raw_a)
        # Re-align others if they exist
        if self.raw_b is not None: self.data_b = self._align_and_analyze(self.raw_b, self.raw_a)
        if self.raw_c is not None: self.data_c = self._align_and_analyze(self.raw_c, self.raw_a)
        if self.raw_d is not None: self.data_d = self._align_and_analyze(self.raw_d, self.raw_a)

    def load_source_b(self, filepath):
        self.raw_b = self._load_file_fast(filepath)
        self.y_b = self.raw_b
        if self.raw_a is not None: self.data_b = self._align_and_analyze(self.raw_b, self.raw_a)

    def load_source_c(self, filepath):
        self.raw_c = self._load_file_fast(filepath)
        self.y_c = self.raw_c
        if self.raw_a is not None: self.data_c = self._align_and_analyze(self.raw_c, self.raw_a)
        
    def load_source_d(self, filepath):
        self.raw_d = self._load_file_fast(filepath)
        self.y_d = self.raw_d
        if self.raw_a is not None: self.data_d = self._align_and_analyze(self.raw_d, self.raw_a)

    def load_source(self, index, filepath):
        if index == 0: self.load_source_a(filepath)
        elif index == 1: self.load_source_b(filepath)
        elif index == 2: self.load_source_c(filepath)
        elif index == 3: self.load_source_d(filepath)

    @property
    def sources(self):
        return [self.raw_a, self.raw_b, self.raw_c, self.raw_d]

    def generate_trajectory(self, shape, speed_hz, num_frames):
        # Generate 0.0-1.0 trajectory
        t = np.linspace(0, num_frames * (self.frame_period / 1000.0), num_frames)
        
        if shape == "Static":
            return np.full(num_frames, 0.5), np.full(num_frames, 0.5)
            
        elif shape == "RandomPoint":
            # Just one random point for the whole duration
            rx = np.random.rand()
            ry = np.random.rand()
            return np.full(num_frames, rx), np.full(num_frames, ry)
            
        elif shape == "Circle":
            omega = 2 * np.pi * speed_hz
            x = 0.5 + 0.4 * np.cos(omega * t)
            y = 0.5 + 0.4 * np.sin(omega * t)
        elif shape == "Eight":
            omega = 2 * np.pi * speed_hz
            x = 0.5 + 0.4 * np.sin(omega * t)
            y = 0.5 + 0.4 * np.sin(2 * omega * t)
        elif shape == "Scan":
            period = 1.0 / max(0.1, speed_hz)
            phase = (t % period) / period
            x = phase
            y = phase
        elif shape == "RandomMovement":
            # True random trajectory each time
            # Combine multiple sines with random phases
            p1 = np.random.rand() * 2 * np.pi
            p2 = np.random.rand() * 2 * np.pi
            p3 = np.random.rand() * 2 * np.pi
            p4 = np.random.rand() * 2 * np.pi
            
            x = 0.5 + 0.2*np.sin(2*np.pi*speed_hz*t + p1) + 0.15*np.sin(2*np.pi*speed_hz*1.3*t + p2)
            y = 0.5 + 0.2*np.cos(2*np.pi*speed_hz*0.9*t + p3) + 0.15*np.cos(2*np.pi*speed_hz*1.7*t + p4)
        else:
            x, y = np.full(num_frames, 0.5), np.full(num_frames, 0.5)
            
        return np.clip(x, 0, 1), np.clip(y, 0, 1)

    def morph(self, x_in, y_in, shape="Static", speed=1.0, formant_shift=1.0, breath=0.0):
        if self.data_a is None: return None
        
        num_frames = len(self.data_a['f0'])
        
        if shape == "Static":
            mx = np.full(num_frames, x_in)
            my = np.full(num_frames, y_in)
        else:
            mx, my = self.generate_trajectory(shape, speed, num_frames)
            
        wa = (1.0 - mx) * (1.0 - my)
        wb = mx * (1.0 - my)
        wc = (1.0 - mx) * my
        wd = mx * my
        
        f0_mix_log_sum = np.zeros(num_frames)
        weight_sum = np.zeros(num_frames)
        
        sp_shape = self.data_a['sp'].shape
        sp_mix = np.zeros(sp_shape)
        ap_mix = np.zeros(sp_shape)
        
        def acc(src_data, w_arr):
            if src_data is None: return
            f0 = src_data['f0']
            f0_safe = np.where(f0 < 1.0, 1e-6, f0)
            f0_mix_log_sum[:] += w_arr * np.log(f0_safe)
            weight_sum[:] += w_arr
            
            w_col = w_arr[:, np.newaxis]
            sp_mix[:] += src_data['sp'] * w_col
            ap_mix[:] += src_data['ap'] * w_col

        acc(self.data_a, wa)
        acc(self.data_b, wb)
        acc(self.data_c, wc)
        acc(self.data_d, wd)
        
        f0_mix = np.exp(f0_mix_log_sum)
        f0_mix = np.where(f0_mix < 40, 0, f0_mix)
        
        # Safety for extrapolation
        sp_mix = np.maximum(0.0, sp_mix)
        ap_mix = np.clip(ap_mix, 0.0, 1.0)
        
        # Formant Shift
        if abs(formant_shift - 1.0) > 0.01:
            sp_mix = self._apply_formant_shift(sp_mix, formant_shift)
            
        # Breath Enhancement (AP)
        if breath > 0.01:
             ap_mix = np.power(ap_mix, 1.0 - (breath * 0.8))
             
        f0_mix = np.ascontiguousarray(f0_mix)
        sp_mix = np.ascontiguousarray(sp_mix)
        ap_mix = np.ascontiguousarray(ap_mix)
        
        y = pw.synthesize(f0_mix, sp_mix, ap_mix, self.sr, frame_period=self.frame_period)
        
        self.generated_audio = y
        self.processed_audio = None
        
        if shape != "Static":
            self.last_trajectory_x = mx
            self.last_trajectory_y = my
        else:
            self.last_trajectory_x = None
            self.last_trajectory_y = None
            
        return y

    def _apply_formant_shift(self, sp, shift):
        rows, cols = sp.shape
        actual_ratio = 1.0 / shift
        indices = np.arange(cols) * actual_ratio
        
        idx_l = np.floor(indices).astype(int)
        idx_h = np.ceil(indices).astype(int)
        alpha = indices - idx_l
        idx_l = np.clip(idx_l, 0, cols-1)
        idx_h = np.clip(idx_h, 0, cols-1)
        
        val_l = sp[:, idx_l]
        val_h = sp[:, idx_h]
        new_sp = val_l * (1 - alpha) + val_h * alpha
        # Fix shape mismatch if interpolation caused it (rare but possible with weird rounding)
        if new_sp.shape[1] != cols:
             new_sp = new_sp[:, :cols]
        return np.ascontiguousarray(new_sp)

    # ==================== NEW EFFECTS ====================

    def apply_bitcrush(self, y, depth, div):
        # div 1-50, depth 4-16
        if div <= 1 and depth >= 16: return y
        
        # 1. Sample Rate Redux
        div = int(div)
        if div > 1:
            indices = np.arange(0, len(y), div)
            y_sub = y[indices]
            y = np.repeat(y_sub, div)[:len(y)] # Repeat and crop
            
        # 2. Bit Depth
        if depth < 16:
            steps = 2 ** depth
            y = np.round(y * steps) / steps
            
        return y

    def apply_ringmod(self, y, freq, mix):
        if mix < 0.01: return y
        t = np.linspace(0, len(y)/self.sr, len(y))
        # Sinewave
        mod = np.sin(2 * np.pi * freq * t)
        y_mod = y * mod
        return y * (1-mix) + y_mod * mix

    def apply_delay(self, y, time_s, feedback, mix):
        if mix < 0.01 or time_s < 0.01: return y
        
        # Calculate sufficient tail
        # feedback^N < 0.001
        # N * log(fb) < log(0.001) -> N > -3 / log(fb)
        # If fb is 0, N=1.
        if feedback > 0.01:
            try: loops = int(-6.0 / np.log10(feedback)) + 2
            except: loops = 5
        else: loops = 1
        
        loops = min(loops, 20) # cap
        tail_len = int(time_s * self.sr * loops)
        delay_samps = int(time_s * self.sr)
        
        output_len = len(y) + tail_len
        y_padded = np.zeros(output_len)
        y_padded[:len(y)] = y
        
        wet_accum = np.zeros(output_len)
        
        # Add echoes
        cursor = 0
        current_amp = 1.0
        
        # We want: Out = Dry*(1-mix) + Wet*mix
        # Wet = Sum(Echoes)
        
        # Optimize: Sparse addition
        for i in range(1, loops + 1):
             start = i * delay_samps
             if start >= output_len: break
             vol = feedback ** i
             
             # Add shifted copy
             # We take "y" (original dry) and shift it
             # Limitation: This is simple echo (feed forward taps), not infinite feedback filtering 
             # But good enough for this app structure. 
             # True feedback requires IIR which is harder to implement without loop or compiled code for growing arrays.
             
             copy_len = len(y)
             if start + copy_len > output_len:
                 copy_len = output_len - start
                 
             wet_accum[start:start+copy_len] += y[:copy_len] * vol

        y_out = y_padded * (1.0 - mix) + wet_accum * mix
        
        # Trim silence at very end if needed? No, let user hear tail.
        return y_out

    def apply_reverb(self, y, mix):
        """
        Simple Convolution Reverb using White Noise decay impulse
        """
        if mix < 0.01: return y
        
        # Create impulse response: decaying noise
        rt60 = 2.0 # seconds
        len_impulse = int(rt60 * self.sr)
        
        # Reuse impulse cache/seed?
        # For determinism in batch?
        np.random.seed(42) 
        
        t = np.linspace(0, 1, len_impulse)
        noise = np.random.randn(len_impulse)
        envelope = np.exp(-7 * t) # Decay
        impulse = noise * envelope
        
        # Normalize impulse power?
        # Impulse sum roughly 1
        impulse /= np.sum(np.abs(impulse))
        impulse *= 1.5 # Gain compensation
        
        # Convolve
        # mode='full' adds tail size of impulse-1
        wet = scipy.signal.fftconvolve(y, impulse, mode='full')
        
        # Pad dry to match wet length
        if len(wet) > len(y):
            y_padded = np.pad(y, (0, len(wet) - len(y)))
        else:
            y_padded = y
            
        return y_padded * (1-mix) + wet * mix
        
    def apply_spacer(self, y, width):
        # Input y can be (N,) or (N,2).
        # Our internal pipeline uses mono y throughout morphing.
        # So usually y is (N,).
        
        # 1. Create Pseudo Stereo if Mono
        if y.ndim == 1:
            # Decorrelate for pseudo stereo
            # Delay Right channel by 15ms (661 samples at 44.1k)
            delay_samp = int(0.015 * self.sr)
            l = y
            r = np.roll(y, delay_samp) # Simple delay
            # Fix roll wrap-around?
            r[:delay_samp] = 0
            
            y_stereo = np.column_stack((l, r))
        else:
            y_stereo = y
            
        if width == 1.0: return y_stereo # Normal Stereo
        if width < 0.01: # Mono
            m = np.mean(y_stereo, axis=1)
            return np.column_stack((m, m))
            
        # Mid-Side Processing
        l = y_stereo[:, 0]
        r = y_stereo[:, 1]
        
        mid = (l + r) / 2.0
        side = (l - r) / 2.0
        
        side *= width
        # Optional: Compensate mid to keep energy?
        # mid *= (2.0 - width) 
        
        l_new = mid + side
        r_new = mid - side
        
        return np.column_stack((l_new, r_new))
        
    def process_pipeline(self, pitch_curve_y, 
                         speed=1.0, 
                         growl=0.0, tone=0.0, 
                         dist=0.0, 
                         bit_depth=16, bit_rate_div=1,
                         ring_freq=30, ring_mix=0.0,
                         delay_time=0.2, delay_fb=0.0, delay_mix=0.0,
                         reverb_mix=0.0,
                         spacer_width=1.0,
                         vol=1.0):
                         
        if self.generated_audio is None: return None
        
        # Ensure base
        y = self.generated_audio.copy()
        
        # 1. Morph Pitch (OLA)
        y = self.apply_pitch_contour(y, pitch_curve_y)
        
        # 2. Speed (Time Stretch)
        if abs(speed - 1.0) > 0.01:
            try: y = librosa.effects.time_stretch(y, rate=speed)
            except: pass

        # --- MOD & TONE ---
        # 3. Tone & Growl
        if growl > 0.01 or abs(tone) > 0.01:
            y = self.apply_tone_growl(y, growl, tone)

        # 4. Ring Mod
        if ring_mix > 0.01:
            y = self.apply_ringmod(y, ring_freq, ring_mix)

        # --- LO-FI ---
        # 5. Bitcrush
        if bit_rate_div > 1 or bit_depth < 16:
            y = self.apply_bitcrush(y, bit_depth, bit_rate_div)
            
        # 6. Distortion (Tanh)
        if dist > 0.01:
            gain = 1 + dist * 10
            y = np.tanh(y * gain)
        
        # --- TIME & SPACE ---
        # 7. Delay
        if delay_mix > 0.01:
            y = self.apply_delay(y, delay_time, delay_fb, delay_mix)
            
        # 8. Reverb
        if reverb_mix > 0.01:
            y = self.apply_reverb(y, reverb_mix)
            
        # 9. Volume
        y = y * vol
        
        # 10. Spacer (Last step, makes it stereo)
        # Even if width=0 (mono), it returns (N,2) array which is fine for SF.write
        y_final = self.apply_spacer(y, spacer_width)
        
        # Normalize hard clip protection
        max_val = np.max(np.abs(y_final))
        if max_val > 1.0:
            y_final /= max_val
            
        self.processed_audio = y_final
        return self.processed_audio

    def apply_pitch_contour(self, y, pitch_curve_y):
        if np.max(np.abs(pitch_curve_y)) < 0.01: return y
        
        total_samples = len(y)
        x_points = np.linspace(0, total_samples, len(pitch_curve_y))
        x_all = np.arange(total_samples)
        # Use Pchip for smooth interpolation matching GUI
        try:
            interp = PchipInterpolator(x_points, pitch_curve_y)
            pitch_envelope = interp(x_all)
        except:
            pitch_envelope = np.interp(x_all, x_points, pitch_curve_y)
        
        chunk_size = 4096 
        step = chunk_size // 2
        num_steps = (total_samples - chunk_size) // step
        y_out = np.zeros_like(y)
        window = np.hanning(chunk_size)
        if num_steps < 1: return y
        
        for i in range(num_steps + 1):
            start = i * step
            end = start + chunk_size
            chunk = y[start:end]
            avg_pitch = np.mean(pitch_envelope[start:end])
            if abs(avg_pitch) > 0.1:
                # Note: pitch_shift is slow. 
                chunk_shifted = librosa.effects.pitch_shift(chunk, sr=self.sr, n_steps=avg_pitch, n_fft=1024)
                if len(chunk_shifted) != len(chunk): chunk_shifted = librosa.util.fix_length(chunk_shifted, size=len(chunk))
            else: chunk_shifted = chunk
            y_out[start:end] += chunk_shifted * window
        return y_out

    def apply_tone_growl(self, y, growl, tone):
        if growl > 0.01:
            freq = 60.0 
            t = np.linspace(0, len(y)/self.sr, len(y))
            modulator = 1.0 + (growl * 0.9) * np.sin(2 * np.pi * freq * t)
            y = y * modulator
        if abs(tone) > 0.01:
            nyquist = 0.5 * self.sr
            if tone > 0: # HPF
                cutoff = max(10, 500 * tone) # up to 500Hz
                b, a = scipy.signal.butter(1, cutoff/nyquist, btype='high')
                y = scipy.signal.lfilter(b, a, y)
            else: # LPF
                # tone is -1 to 0
                cutoff = 20000 * (1.0 + tone * 0.9) + 100 # down to 100Hz
                b, a = scipy.signal.butter(1, cutoff/nyquist, btype='low')
                y = scipy.signal.lfilter(b, a, y)
        return y

    def save_output(self, filepath):
        target = self.processed_audio if self.processed_audio is not None else self.generated_audio
        if target is None: return
        sf.write(filepath, target, self.sr)
        
    def render_batch_sample(self, filepath, morph_x, morph_y, shape, m_speed, formant, breath, pitch_curve, 
                            speed, growl, tone, dist, 
                            bit_depth, bit_rate_div, ring_freq, ring_mix,
                            delay_time, delay_fb, delay_mix, reverb_mix, spacer_width, vol):
        try:
            self.morph(morph_x, morph_y, shape=shape, speed=m_speed, formant_shift=formant, breath=breath)
            self.process_pipeline(pitch_curve, speed=speed, growl=growl, tone=tone, dist=dist,
                                  bit_depth=bit_depth, bit_rate_div=bit_rate_div,
                                  ring_freq=ring_freq, ring_mix=ring_mix,
                                  delay_time=delay_time, delay_fb=delay_fb, delay_mix=delay_mix,
                                  reverb_mix=reverb_mix, spacer_width=spacer_width, vol=vol)
            self.save_output(filepath)
            return True, "Success"
        except Exception as e:
            return False, str(e)
