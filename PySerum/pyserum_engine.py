import numpy as np
import scipy.signal
import scipy.io.wavfile
import datetime
import random

# Constants
SR = 48000
BLOCK_SIZE = 512
CHANNELS = 2
TABLE_SIZE = 2048
NUM_FRAMES = 64

class WavetableGenerator:
    @staticmethod
    def _generate_saw_table():
        tables = np.zeros((NUM_FRAMES, TABLE_SIZE), dtype=np.float32)
        t = np.linspace(0, 1, TABLE_SIZE, endpoint=False)
        for i in range(NUM_FRAMES):
            morph = i / (NUM_FRAMES - 1)
            saw = 2.0 * t - 1.0
            sq = np.sign(saw)
            wave = (1.0 - morph) * saw + morph * sq
            tables[i] = wave
        return tables

    @staticmethod
    def _generate_monster_table():
        tables = np.zeros((NUM_FRAMES, TABLE_SIZE), dtype=np.float32)
        t = np.linspace(0, 1, TABLE_SIZE, endpoint=False)
        for i in range(NUM_FRAMES):
            morph = i / (NUM_FRAMES - 1)
            carrier = 2 * np.pi * t
            ratio = 1.0 + morph * 3.0
            index = morph * 5.0
            modulator = np.sin(carrier * ratio)
            wave = np.sin(carrier + index * modulator)
            m = np.max(np.abs(wave))
            if m > 0: wave /= m
            tables[i] = wave
        return tables

    @staticmethod
    def _generate_basic_shapes():
        # Sine -> Tri -> Saw -> Square -> Pulse
        # 5 shapes, 4 morph zones.
        # 0.0-0.25: Sine->Tri
        # 0.25-0.5: Tri->Saw
        # 0.5-0.75: Saw->Square
        # 0.75-1.0: Square->Pulse
        tables = np.zeros((NUM_FRAMES, TABLE_SIZE), dtype=np.float32)
        t = np.linspace(0, 1, TABLE_SIZE, endpoint=False)
        
        # Primitives
        sine = np.sin(2 * np.pi * t)
        tri = 2.0 * np.abs(2.0 * t - 1.0) - 1.0 # -1..1
        saw = 2.0 * t - 1.0
        square = np.sign(np.sin(2 * np.pi * t))
        pulse = np.where(t < 0.125, 1.0, -1.0) # 12.5% pulse width roughly

        for i in range(NUM_FRAMES):
            pos = i / (NUM_FRAMES - 1)
            if pos < 0.25:
                # Sine -> Tri
                local = pos / 0.25
                tables[i] = (1.0 - local) * sine + local * tri
            elif pos < 0.50:
                # Tri -> Saw
                local = (pos - 0.25) / 0.25
                tables[i] = (1.0 - local) * tri + local * saw
            elif pos < 0.75:
                # Saw -> Square
                local = (pos - 0.50) / 0.25
                tables[i] = (1.0 - local) * saw + local * square
            else:
                # Square -> Pulse
                local = (pos - 0.75) / 0.25
                tables[i] = (1.0 - local) * square + local * pulse
        return tables

    @staticmethod
    def generate_tables():
        return {
            "Classic": WavetableGenerator._generate_saw_table(),
            "Monster": WavetableGenerator._generate_monster_table(),
            "Basic Shapes": WavetableGenerator._generate_basic_shapes()
        }

class ADSR:
    IDLE = 0
    ATTACK = 1
    DECAY = 2
    SUSTAIN = 3
    RELEASE = 4

    def __init__(self):
        self.state = self.IDLE
        self.level = 0.0
        self.sample_rate = SR
        self.attack_time = 0.01
        self.decay_time = 0.1
        self.sustain_level = 0.7
        self.release_time = 0.5
        self._calc_increments()
        
    def _calc_increments(self):
        self.attack_step = 1.0 / (self.attack_time * self.sample_rate + 1.0)
        self.decay_step = (1.0 - self.sustain_level) / (self.decay_time * self.sample_rate + 1.0)
        self.release_step = self.sustain_level / (self.release_time * self.sample_rate + 1.0)

    def set_params(self, a, d, s, r):
        self.attack_time = max(0.001, a)
        self.decay_time = max(0.001, d)
        self.sustain_level = np.clip(s, 0.0, 1.0)
        self.release_time = max(0.001, r)
        self._calc_increments()

    def trigger(self):
        self.state = self.ATTACK
        
    def release(self):
        if self.state != self.IDLE:
            self.state = self.RELEASE
            self.release_step = self.level / (self.release_time * self.sample_rate + 1.0)

    def process(self, num_samples):
        output = np.zeros(num_samples, dtype=np.float32)
        cursor = 0
        
        while cursor < num_samples:
            remaining = num_samples - cursor
            if self.state == self.IDLE:
                output[cursor:] = 0.0
                self.level = 0.0
                break
            elif self.state == self.ATTACK:
                needed = int((1.0 - self.level) / self.attack_step) + 1
                n = min(remaining, needed)
                output[cursor:cursor+n] = self.level + np.arange(n) * self.attack_step
                self.level += n * self.attack_step
                cursor += n
                if self.level >= 1.0:
                    self.level = 1.0
                    self.state = self.DECAY
            elif self.state == self.DECAY:
                needed = int((self.level - self.sustain_level) / self.decay_step) + 1
                n = min(remaining, needed)
                output[cursor:cursor+n] = self.level - np.arange(n) * self.decay_step
                self.level -= n * self.decay_step
                cursor += n
                if self.level <= self.sustain_level:
                    self.level = self.sustain_level
                    self.state = self.SUSTAIN
            elif self.state == self.SUSTAIN:
                output[cursor:] = self.level
                cursor = num_samples
            elif self.state == self.RELEASE:
                if self.release_step <= 1e-9:
                    output[cursor:] = 0.0
                    self.level = 0.0
                    self.state = self.IDLE
                    break
                needed = int(self.level / self.release_step) + 1
                n = min(remaining, needed)
                output[cursor:cursor+n] = self.level - np.arange(n) * self.release_step
                self.level -= n * self.release_step
                cursor += n
                if self.level <= 0.0:
                    self.level = 0.0
                    self.state = self.IDLE
        return output

class UnisonOscillator:
    def __init__(self):
        self.phases = np.zeros(7, dtype=np.float32)
        self.detune_multipliers = np.ones(7, dtype=np.float32)
        # Stereo spread panning
        self.pan_l = np.array([1.0, 0.9, 0.8, 0.5, 0.2, 0.1, 0.0], dtype=np.float32)
        self.pan_r = np.array([0.0, 0.1, 0.2, 0.5, 0.8, 0.9, 1.0], dtype=np.float32)
        self.pan_l /= np.sqrt(np.sum(self.pan_l**2))
        self.pan_r /= np.sqrt(np.sum(self.pan_r**2))
        
    def reset_phases(self, start_phase, is_random):
        if is_random:
            self.phases = np.random.rand(7).astype(np.float32)
        else:
            self.phases[:] = start_phase
            
    def set_detune(self, amount):
        if amount == 0:
            self.detune_multipliers[:] = 1.0
        else:
            spread = 0.04 * amount 
            steps = np.array([-3, -2, -1, 0, 1, 2, 3])
            step_val = spread / 3.0
            self.detune_multipliers = 1.0 + steps * step_val
            
    def process(self, freq, table_frames, table_pos, pan_balance):
        voice_freqs = freq * self.detune_multipliers
        t_steps = np.arange(BLOCK_SIZE, dtype=np.float32)
        increments = voice_freqs / SR
        
        phase_block = self.phases[:, np.newaxis] + np.outer(increments, t_steps)
        phase_block %= 1.0
        self.phases += increments * BLOCK_SIZE
        self.phases %= 1.0
        
        pos_idx = table_pos * (NUM_FRAMES - 1)
        idx0 = int(pos_idx); idx1 = min(idx0 + 1, NUM_FRAMES - 1)
        alpha = pos_idx - idx0
        table0 = table_frames[idx0]; table1 = table_frames[idx1]
        
        sample_indices = (phase_block * TABLE_SIZE).astype(int)
        sample_indices = np.clip(sample_indices, 0, TABLE_SIZE - 1)
        
        wave0 = table0[sample_indices]
        wave1 = table1[sample_indices]
        waves = (1.0 - alpha) * wave0 + alpha * wave1
        
        # Apply Pan Balance
        # PanBalance -1 (Left) to +1 (Right)
        # Standard Panning Law (Constant Power)
        # p_val: 0.0 to 1.0
        p_val = (pan_balance + 1.0) * 0.5
        gain_l = np.cos(p_val * np.pi * 0.5)
        gain_r = np.sin(p_val * np.pi * 0.5)
        
        # Mix Unison -> Stereo
        out_l = np.sum(waves * self.pan_l[:, np.newaxis], axis=0) * gain_l
        out_r = np.sum(waves * self.pan_r[:, np.newaxis], axis=0) * gain_r
        
        return out_l, out_r

class Voice:
    def __init__(self, unison_osc):
        self.active = False
        self.note = 0
        self.freq = 440.0
        self.adsr = ADSR()      
        self.adsr_mod = ADSR()  
        
        self.osc_a = UnisonOscillator()
        self.osc_b = UnisonOscillator()
        self.osc_a.set_detune(0.0)
        self.osc_b.set_detune(0.0)
        
        # Phase Params
        self.phase_val_a = 0.0; self.phase_rand_a = False
        self.phase_val_b = 0.0; self.phase_rand_b = False
        
    def note_on(self, note):
        self.note = note
        self.freq = 440.0 * (2.0 ** ((note - 69) / 12.0))
        self.active = True
        self.adsr.trigger()
        self.adsr_mod.trigger()
        # Reset Phases
        self.osc_a.reset_phases(self.phase_val_a, self.phase_rand_a)
        self.osc_b.reset_phases(self.phase_val_b, self.phase_rand_b)
        
    def note_off(self):
        self.adsr.release()
        self.adsr_mod.release()
        
    def is_playing(self): return self.adsr.state != ADSR.IDLE
        
    def set_detune(self, amount_a, amount_b):
        self.osc_a.set_detune(amount_a)
        self.osc_b.set_detune(amount_b)
        
    def set_phases(self, phase_a, rand_a, phase_b, rand_b):
        self.phase_val_a = phase_a; self.phase_rand_a = rand_a
        self.phase_val_b = phase_b; self.phase_rand_b = rand_b

    def process(self, table_a, pos_a, table_b, pos_b, vol_a, vol_b, semi_a, semi_b, fine_a, fine_b, oct_a, oct_b, pan_a, pan_b, mod_amt_pitch):
        env = self.adsr.process(BLOCK_SIZE)
        env_mod = self.adsr_mod.process(BLOCK_SIZE)
        
        if np.all(env == 0) and self.adsr.state == ADSR.IDLE:
            self.active = False
            return np.zeros(BLOCK_SIZE), np.zeros(BLOCK_SIZE), np.zeros(BLOCK_SIZE)
            
        pitch_mod_val = np.mean(env_mod) * mod_amt_pitch 
        
        # Pitch A
        # semi + oct*12
        total_semi_a = semi_a + (oct_a * 12) + pitch_mod_val
        pitch_factor_a = (2.0 ** (total_semi_a / 12.0)) * (2.0 ** (fine_a / 1200.0))
        freq_a = self.freq * pitch_factor_a
        
        # Pitch B
        total_semi_b = semi_b + (oct_b * 12) + pitch_mod_val
        pitch_factor_b = (2.0 ** (total_semi_b / 12.0)) * (2.0 ** (fine_b / 1200.0))
        freq_b = self.freq * pitch_factor_b
            
        la, ra = self.osc_a.process(freq_a, table_a, pos_a, pan_a)
        lb, rb = self.osc_b.process(freq_b, table_b, pos_b, pan_b)
        
        out_l = (la * vol_a) + (lb * vol_b)
        out_r = (ra * vol_a) + (rb * vol_b)
        
        out_l *= env
        out_r *= env
        return out_l, out_r, env_mod

class FXFilter:
    def __init__(self):
        self.enabled = False
        self.cutoff = 20000.0
        self.zi = np.zeros((2, CHANNELS))

    def set_params(self, cutoff):
        self.cutoff = np.clip(cutoff, 20.0, 20000.0)
        
    def process(self, audio_block):
        if not self.enabled: return audio_block
        nyq = SR * 0.5
        norm_cutoff = np.clip(self.cutoff / nyq, 0.001, 0.999)
        b, a = scipy.signal.butter(2, norm_cutoff, btype='low')
        out_block, self.zi = scipy.signal.lfilter(b, a, audio_block, axis=0, zi=self.zi)
        return out_block.astype(np.float32)

class FXDistortion:
    def __init__(self):
        self.enabled = False
        self.drive = 0.0
    def set_params(self, drive): self.drive = drive
    def process(self, audio_block):
        if not self.enabled or self.drive <= 0.001: return audio_block
        k = self.drive * 20.0
        return audio_block * (1.0 + k) / (1.0 + k * np.abs(audio_block))

class FXDelay:
    def __init__(self):
        self.enabled = False
        self.time = 0.25; self.feedback = 0.4; self.mix = 0.3
        self.buffer_len = 48000
        self.buffer = np.zeros((self.buffer_len, 2), dtype=np.float32)
        self.write_ptr = 0
    def set_params(self, time_s, fb, mix):
        self.time = np.clip(time_s, 0.01, 1.0)
        self.feedback = np.clip(fb, 0.0, 0.95)
        self.mix = np.clip(mix, 0.0, 1.0)
    def process(self, audio_block):
        if not self.enabled or self.mix <= 0.001: return audio_block
        n_samples = len(audio_block)
        delay_samples = min(int(self.time * SR), self.buffer_len - 1)
        read_start = self.write_ptr - delay_samples
        indices = (np.arange(n_samples) + read_start) % self.buffer_len
        delayed_signal = self.buffer[indices]
        input_signal = audio_block + delayed_signal * self.feedback
        end_ptr = self.write_ptr + n_samples
        if end_ptr <= self.buffer_len: self.buffer[self.write_ptr:end_ptr] = input_signal
        else:
            part1 = self.buffer_len - self.write_ptr
            self.buffer[self.write_ptr:] = input_signal[:part1]
            self.buffer[:(n_samples - part1)] = input_signal[part1:]
        self.write_ptr = (self.write_ptr + n_samples) % self.buffer_len
        return audio_block * (1.0 - self.mix) + delayed_signal * self.mix

class LFO:
    def __init__(self):
        self.rate = 1.0; self.shape = "Sine"; self.phase = 0.0
    def set_params(self, rate, shape): self.rate = np.clip(rate, 0.01, 20.0); self.shape = shape
    def process(self, num_samples):
        phase_inc = self.rate / SR
        phases = self.phase + np.arange(num_samples) * phase_inc
        phases %= 1.0
        self.phase = (self.phase + num_samples * phase_inc) % 1.0
        if self.shape == "Sine": return 0.5 + 0.5 * np.sin(2 * np.pi * phases)
        elif self.shape == "Saw": return phases
        elif self.shape == "Tri": return 1.0 - np.abs(2.0 * phases - 1.0)
        return phases

class AudioRecorder:
    def __init__(self): self.active = False; self.buffer = []
    def start(self): self.buffer = []; self.active = True
    def stop(self):
        if not self.active: return None
        self.active = False
        if not self.buffer: return None
        full_audio = np.concatenate(self.buffer)
        fname = f"output_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        scipy.io.wavfile.write(fname, SR, full_audio)
        return fname
    def process(self, block):
        if self.active: self.buffer.append(block)

class SerumEngine:
    def __init__(self):
        self.wavetables = WavetableGenerator.generate_tables()
        self.table_a_frames = self.wavetables["Classic"]
        self.table_b_frames = self.wavetables["Monster"] 
        self.voices = [Voice(None) for _ in range(4)]
        self.next_voice_idx = 0
        
        # OSC A
        self.pos_a = 0.0; self.unison_a = 0.0; self.vol_a = 0.8; self.semi_a = 0
        self.oct_a = 0; self.fine_a = 0; self.pan_a = 0.0; self.phase_val_a = 0.0; self.phase_rand_a = False
        
        # OSC B
        self.pos_b = 0.0; self.unison_b = 0.0; self.vol_b = 0.0; self.semi_b = 0
        self.oct_b = 0; self.fine_b = 0; self.pan_b = 0.0; self.phase_val_b = 0.0; self.phase_rand_b = False
        
        self.fx_filter = FXFilter()
        self.fx_dist = FXDistortion()
        self.fx_delay = FXDelay()
        self.lfo = LFO()
        self.recorder = AudioRecorder()
        
        self.mod_cutoff = 0.0; self.mod_wt = 0.0
        self.mod_env_amt_cutoff = 0.0; self.mod_env_amt_pitch = 0.0
        self.base_cutoff = 20000.0

    def set_osc_a_params(self, table_name, pos, unison, vol, semi, octave=0, fine=0, pan=0.0, phase_val=0.0, phase_rand=False):
        if table_name in self.wavetables: self.table_a_frames = self.wavetables[table_name]
        self.pos_a = np.clip(pos, 0.0, 1.0)
        self.unison_a = np.clip(unison, 0.0, 1.0)
        self.vol_a = np.clip(vol, 0.0, 1.0)
        self.semi_a = int(semi); self.oct_a = int(octave); self.fine_a = int(fine)
        self.pan_a = np.clip(pan, -1.0, 1.0)
        self.phase_val_a = phase_val; self.phase_rand_a = phase_rand
        
        for v in self.voices: 
            v.set_detune(self.unison_a, self.unison_b)
            v.set_phases(self.phase_val_a, self.phase_rand_a, self.phase_val_b, self.phase_rand_b)
            
    def set_osc_b_params(self, table_name, pos, unison, vol, semi, octave=0, fine=0, pan=0.0, phase_val=0.0, phase_rand=False):
        if table_name in self.wavetables: self.table_b_frames = self.wavetables[table_name]
        self.pos_b = np.clip(pos, 0.0, 1.0)
        self.unison_b = np.clip(unison, 0.0, 1.0)
        self.vol_b = np.clip(vol, 0.0, 1.0)
        self.semi_b = int(semi); self.oct_b = int(octave); self.fine_b = int(fine)
        self.pan_b = np.clip(pan, -1.0, 1.0)
        self.phase_val_b = phase_val; self.phase_rand_b = phase_rand

        for v in self.voices: 
            v.set_detune(self.unison_a, self.unison_b)
            v.set_phases(self.phase_val_a, self.phase_rand_a, self.phase_val_b, self.phase_rand_b)

    def set_adsr(self, a, d, s, r):
        for v in self.voices: v.adsr.set_params(a, d, s, r)

    def set_mod_adsr(self, a, d, s, r, amt_cut, amt_pitch):
        self.mod_env_amt_cutoff = amt_cut; self.mod_env_amt_pitch = amt_pitch
        for v in self.voices: v.adsr_mod.set_params(a, d, s, r)

    def set_filter(self, enabled, cutoff): self.fx_filter.set_params(cutoff); self.fx_filter.enabled = enabled; self.base_cutoff = cutoff
    def set_dist(self, enabled, drive): self.fx_dist.set_params(drive); self.fx_dist.enabled = enabled
    def set_delay(self, enabled, time_s, fb, mix): self.fx_delay.set_params(time_s, fb, mix); self.fx_delay.enabled = enabled
    def set_lfo(self, rate, shape, mod_cut, mod_wt): self.lfo.set_params(rate, shape); self.mod_cutoff = mod_cut; self.mod_wt = mod_wt
    
    def note_on(self, note):
        v = self.voices[self.next_voice_idx]
        v.note_on(note)
        self.next_voice_idx = (self.next_voice_idx + 1) % len(self.voices)
        
    def note_off(self, note):
        for v in self.voices:
            if v.note == note and v.is_playing(): v.note_off()
    
    def start_recording(self): self.recorder.start()
    def stop_recording(self): return self.recorder.stop()

    def generate_block(self):
        lfo_block = self.lfo.process(BLOCK_SIZE)
        mod_val = np.mean(lfo_block)
        current_wt_pos_a = np.clip(self.pos_a + (mod_val * self.mod_wt), 0.0, 1.0)
        current_wt_pos_b = self.pos_b 
        
        mix_l = np.zeros(BLOCK_SIZE, dtype=np.float32)
        mix_r = np.zeros(BLOCK_SIZE, dtype=np.float32)
        
        # Mod Env Capture
        avg_mod_env = 0.0
        active_voices = 0
        
        for v in self.voices:
            if v.active:
                vl, vr, ve_mod = v.process(
                    self.table_a_frames, current_wt_pos_a,
                    self.table_b_frames, current_wt_pos_b,
                    self.vol_a, self.vol_b,
                    self.semi_a, self.semi_b,
                    self.fine_a, self.fine_b,
                    self.oct_a, self.oct_b,
                    self.pan_a, self.pan_b,
                    self.mod_env_amt_pitch
                )
                mix_l += vl
                mix_r += vr
                if active_voices == 0: avg_mod_env = np.mean(ve_mod)
                else: avg_mod_env += np.mean(ve_mod)
                active_voices += 1
        
        if active_voices > 1: avg_mod_env /= active_voices
        
        mod_total = (mod_val * self.mod_cutoff) + (avg_mod_env * self.mod_env_amt_cutoff)
        current_cutoff = self.base_cutoff + (mod_total * 5000.0) 
        self.fx_filter.set_params(current_cutoff)

        stereo = np.column_stack((mix_l, mix_r))
        stereo = self.fx_filter.process(stereo)
        stereo = self.fx_dist.process(stereo)
        stereo = self.fx_delay.process(stereo)
        stereo = np.tanh(stereo)
        self.recorder.process(stereo)
        return stereo.flatten()

    def get_patch_state(self):
        v0 = self.voices[0]
        return {
            "osc_a": {
                "params": {"pos": self.pos_a, "unison": self.unison_a, "vol": self.vol_a, "semi": self.semi_a, 
                           "oct": self.oct_a, "fine": self.fine_a, "pan": self.pan_a, "phase": self.phase_val_a, "rand": self.phase_rand_a}
            },
            "osc_b": {
                "params": {"pos": self.pos_b, "unison": self.unison_b, "vol": self.vol_b, "semi": self.semi_b,
                           "oct": self.oct_b, "fine": self.fine_b, "pan": self.pan_b, "phase": self.phase_val_b, "rand": self.phase_rand_b}
            },
            "filter": {"enabled": self.fx_filter.enabled, "cutoff": self.base_cutoff},
            "lfo": {"rate": self.lfo.rate, "shape": self.lfo.shape, "mod_cutoff": self.mod_cutoff, "mod_wt": self.mod_wt},
            "adsr_amp": {"a": v0.adsr.attack_time, "d": v0.adsr.decay_time, "s": v0.adsr.sustain_level, "r": v0.adsr.release_time},
            "adsr_mod": {"a": v0.adsr_mod.attack_time, "d": v0.adsr_mod.decay_time, "s": v0.adsr_mod.sustain_level, "r": v0.adsr_mod.release_time, "amt_cutoff": self.mod_env_amt_cutoff, "amt_pitch": self.mod_env_amt_pitch},
            "fx_dist": {"enabled": self.fx_dist.enabled, "drive": self.fx_dist.drive},
            "fx_delay": {"enabled": self.fx_delay.enabled, "time": self.fx_delay.time, "feedback": self.fx_delay.feedback, "mix": self.fx_delay.mix}
        }

    def set_patch_state(self, state):
        p = state.get("osc_a", {}).get("params", {})
        self.pos_a = p.get("pos", 0.0); self.unison_a = p.get("unison", 0.0); self.vol_a = p.get("vol", 0.8)
        self.semi_a = p.get("semi", 0); self.oct_a = p.get("oct", 0); self.fine_a = p.get("fine", 0)
        self.pan_a = p.get("pan", 0.0); self.phase_val_a = p.get("phase", 0.0); self.phase_rand_a = p.get("rand", False)
        for v in self.voices: v.osc_a.set_unison_spread(self.unison_a); v.set_phases(self.phase_val_a, self.phase_rand_a, self.phase_val_b, self.phase_rand_b)
        
        p = state.get("osc_b", {}).get("params", {})
        self.pos_b = p.get("pos", 0.0); self.unison_b = p.get("unison", 0.0); self.vol_b = p.get("vol", 0.0)
        self.semi_b = p.get("semi", 0); self.oct_b = p.get("oct", 0); self.fine_b = p.get("fine", 0)
        self.pan_b = p.get("pan", 0.0); self.phase_val_b = p.get("phase", 0.0); self.phase_rand_b = p.get("rand", False)
        for v in self.voices: v.osc_b.set_unison_spread(self.unison_b); v.set_phases(self.phase_val_a, self.phase_rand_a, self.phase_val_b, self.phase_rand_b)
        
        f = state.get("filter", {}); self.set_filter(f.get("enabled", False), f.get("cutoff", 20000))
        l = state.get("lfo", {}); self.set_lfo(l.get("rate", 1.0), l.get("shape", "Sine"), l.get("mod_cutoff", 0.0), l.get("mod_wt", 0.0))
        aa = state.get("adsr_amp", {}); self.set_adsr(aa.get("a", 0.1), aa.get("d", 0.1), aa.get("s", 1.0), aa.get("r", 0.1))
        am = state.get("adsr_mod", {}); self.set_mod_adsr(am.get("a", 0.1), am.get("d", 0.1), am.get("s", 1.0), am.get("r", 0.1), am.get("amt_cutoff", 0.0), am.get("amt_pitch", 0.0))
        fd = state.get("fx_dist", {}); self.set_dist(fd.get("enabled", False), fd.get("drive", 0.0))
        fdel = state.get("fx_delay", {}); self.set_delay(fdel.get("enabled", False), fdel.get("time", 0.25), fdel.get("feedback", 0.4), fdel.get("mix", 0.3))
