import librosa
import numpy as np
import soundfile as sf
import os
import scipy.signal
import pyworld as pw
import scipy.interpolate

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
        self.processed_audio = None
        
        self.last_trajectory_x = None
        self.last_trajectory_y = None

    def _load_file_fast(self, filepath):
        try:
            data, samplerate = sf.read(filepath)
            if len(data.shape) > 1: data = np.mean(data, axis=1)
            if samplerate != self.sr:
                data = librosa.resample(data, orig_sr=samplerate, target_sr=self.sr)
            return data.astype(np.float64)
        except Exception:
            y, _ = librosa.load(filepath, sr=self.sr, mono=True)
            return y.astype(np.float64)

    def _analyze(self, y):
        y = np.ascontiguousarray(y.astype(np.float64))
        _f0, t = pw.harvest(y, self.sr, frame_period=self.frame_period)
        _sp = pw.cheaptrick(y, _f0, t, self.sr)
        _ap = pw.d4c(y, _f0, t, self.sr)
        return {'f0': _f0, 'sp': _sp, 'ap': _ap, 'len': len(y)}

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

    def generate_trajectory(self, shape, speed_hz, num_frames):
        t = np.linspace(0, num_frames * (self.frame_period / 1000.0), num_frames)
        
        if shape == "Static":
            return np.full(num_frames, 0.5), np.full(num_frames, 0.5)
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
        elif shape == "Random":
            x = 0.5 + 0.2*np.sin(2*np.pi*speed_hz*t) + 0.15*np.sin(2*np.pi*speed_hz*1.3*t + 1)
            y = 0.5 + 0.2*np.cos(2*np.pi*speed_hz*0.9*t) + 0.15*np.cos(2*np.pi*speed_hz*1.7*t + 2)
        else:
            x, y = np.full(num_frames, 0.5), np.full(num_frames, 0.5)
            
        return np.clip(x, 0, 1), np.clip(y, 0, 1)

    def morph(self, x_in, y_in, shape="Static", speed=1.0, formant_shift=1.0, breath=0.0):
        """
        Morph with Breath parameter (AP enhancement)
        """
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
        
        # Formant Shift
        if abs(formant_shift - 1.0) > 0.01:
            sp_mix = self._apply_formant_shift(sp_mix, formant_shift)
            
        # Breath Enhancement (AP)
        # Power law: AP^ (1 - breath)
        # If breath is 1.0 (max), exponent 0 -> AP=1 (Max Noise)
        # If breath is 0.0 (min), exponent 1 -> AP=Normal
        if breath > 0.01:
             ap_mix = np.power(ap_mix, 1.0 - (breath * 0.8)) # Cap at 0.8 power to avoid white noise
             
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
        return np.ascontiguousarray(new_sp)

    def process_pipeline(self, pitch_curve_y, speed, growl, tone, dist, vol):
        if self.generated_audio is None: return None
        
        # 1. Pitch Shift (OLA) - Handles pitch curve
        y_pitched = self.apply_pitch_contour(self.generated_audio, pitch_curve_y)
        
        # 2. Time Stretch (Speed) - PRESERVES PITCH
        if abs(speed - 1.0) > 0.01:
            # librosa.effects.time_stretch works on audio y (float)
            # rate > 1.0 is faster
            try:
                y_pitched = librosa.effects.time_stretch(y_pitched, rate=speed)
            except: pass
            
        # 3. Tone & Growl
        y_fx = self.apply_tone_growl(y_pitched, growl, tone)
        
        # 4. Distortion
        if dist > 0.01:
            gain = 1 + dist * 5
            y_fx = np.tanh(y_fx * gain)
            # Optional: makeup gain? Tanh limits to 1.0
            
        # 5. Volume
        y_fx = y_fx * vol
        
        # Normalize
        max_val = np.max(np.abs(y_fx))
        if max_val > 1.0: y_fx /= max_val
            
        self.processed_audio = y_fx
        return self.processed_audio

    def apply_pitch_contour(self, y, pitch_curve_y):
        # Only if pitch curve active
        if np.max(np.abs(pitch_curve_y)) < 0.01: return y
        
        total_samples = len(y)
        x_points = np.linspace(0, total_samples, len(pitch_curve_y))
        x_all = np.arange(total_samples)
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
                chunk_shifted = librosa.effects.pitch_shift(chunk, sr=self.sr, n_steps=avg_pitch, n_fft=1024)
                if len(chunk_shifted) != len(chunk): chunk_shifted = librosa.util.fix_length(chunk_shifted, size=len(chunk))
            else: chunk_shifted = chunk
            y_out[start:end] += chunk_shifted * window
        return y_out

    def apply_tone_growl(self, y, growl, tone):
        if growl > 0.01:
            freq = 50.0 
            t = np.linspace(0, len(y)/self.sr, len(y))
            modulator = 1.0 + (growl * 0.8) * np.sin(2 * np.pi * freq * t)
            y = y * modulator
        if abs(tone) > 0.01:
            nyquist = 0.5 * self.sr
            if tone > 0:
                cutoff = max(10, 200 * tone)
                b, a = scipy.signal.butter(1, cutoff/nyquist, btype='high')
                y = scipy.signal.lfilter(b, a, y)
            else:
                cutoff = 1000 + (20000 - 1000) * (1.0 + tone) 
                b, a = scipy.signal.butter(1, cutoff/nyquist, btype='low')
                y = scipy.signal.lfilter(b, a, y)
        return y

    def save_output(self, filepath):
        target = self.processed_audio if self.processed_audio is not None else self.generated_audio
        if target is not None: sf.write(filepath, target, self.sr)
        
    def render_batch_sample(self, filepath, morph_x, morph_y, shape, m_speed, formant, breath, pitch_curve, speed, growl, tone, dist, vol):
        """
        Batch Helper: Automated full pipeline
        """
        try:
            # 1. Morph (Synthesis)
            self.morph(morph_x, morph_y, shape=shape, speed=m_speed, formant_shift=formant, breath=breath)
            
            # 2. Pipeline (FX)
            self.process_pipeline(pitch_curve, speed, growl, tone, dist, vol)
            
            # 3. Save
            self.save_output(filepath)
            return True, "Success"
        except Exception as e:
            return False, str(e)
