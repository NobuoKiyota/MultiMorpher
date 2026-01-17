import numpy as np

# Constants from PySerum
SR = 48000
BLOCK_SIZE = 512
TABLE_SIZE = 2048
NUM_FRAMES = 64

class WavetableGenerator:
    """
    Generates wavetables for the oscillator.
    Transplanted from pyserum_engine.py
    """
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
        tables = np.zeros((NUM_FRAMES, TABLE_SIZE), dtype=np.float32)
        t = np.linspace(0, 1, TABLE_SIZE, endpoint=False)
        
        sine = np.sin(2 * np.pi * t)
        tri = 2.0 * np.abs(2.0 * t - 1.0) - 1.0
        saw = 2.0 * t - 1.0
        square = np.sign(np.sin(2 * np.pi * t))
        pulse = np.where(t < 0.125, 1.0, -1.0)

        for i in range(NUM_FRAMES):
            pos = i / (NUM_FRAMES - 1)
            if pos < 0.25:
                local = pos / 0.25
                tables[i] = (1.0 - local) * sine + local * tri
            elif pos < 0.50:
                local = (pos - 0.25) / 0.25
                tables[i] = (1.0 - local) * tri + local * saw
            elif pos < 0.75:
                local = (pos - 0.50) / 0.25
                tables[i] = (1.0 - local) * saw + local * square
            else:
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

class UnisonOscillator:
    """
    Advanced Unison Oscillator with Detune and Stereo Spread.
    Transplanted from pyserum_engine.py
    """
    def __init__(self):
        self.phases = np.zeros(7, dtype=np.float32)
        self.detune_multipliers = np.ones(7, dtype=np.float32)
        # Stereo spread panning
        self.pan_l = np.array([1.0, 0.9, 0.8, 0.5, 0.2, 0.1, 0.0], dtype=np.float32)
        self.pan_r = np.array([0.0, 0.1, 0.2, 0.5, 0.8, 0.9, 1.0], dtype=np.float32)
        norm_l = np.sqrt(np.sum(self.pan_l**2))
        norm_r = np.sqrt(np.sum(self.pan_r**2))
        if norm_l > 0: self.pan_l /= norm_l
        if norm_r > 0: self.pan_r /= norm_r
        
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
            
    def process(self, freq, table_frames, table_pos, pan_balance, detune_amount=None):
        # freq: scalar or array
        # table_pos: scalar or array (0.0-1.0)
        # detune_amount: scalar or array (0.0-1.0) overrides internal self.detune_multipliers logic IF DYNAMIC
        
        # If detune_amount is provided (dynamic), we recalculate multipliers per block?
        # Re-calculating multipliers 512 times is heavy. 
        # But we can approximate efficiently.
        # "Unison Detune" usually scales the spread width.
        # steps = [-3, -2, -1, 0, 1, 2, 3]
        # mults = 1.0 + steps * (0.04 * amount / 3.0) -> steps * 0.0133 * amount
        # So multipliers are linear with amount.
        
        # We can implement DYNAMIC DETUNE by calculating multipliers on the fly or vectorizing.
        # Let's vectorize.
        
        steps = np.array([-3, -2, -1, 0, 1, 2, 3], dtype=np.float32) # (7,)
        
        if detune_amount is None:
             # Use static internal
             current_mults = self.detune_multipliers # (7,)
        elif np.ndim(detune_amount) == 0:
             # Static override
             spread = 0.04 * detune_amount
             current_mults = 1.0 + steps * (spread / 3.0)
        else:
             # Dynamic Detune (Array 512)
             # detune_amount: (512,)
             # steps: (7,)
             # target: (7, 512)
             spreads = 0.04 * detune_amount # (512,)
             # steps[:,None] (7,1) * spreads[None,:] (1,512) -> (7,512)
             current_mults = 1.0 + steps[:, np.newaxis] * (spreads[np.newaxis, :] / 3.0)
             
        # Freq Processing
        if np.ndim(freq) == 0 and np.ndim(current_mults) == 1:
            # Fully Static
            voice_freqs = freq * current_mults # (7,)
            t_steps = np.arange(BLOCK_SIZE, dtype=np.float32)
            increments = voice_freqs / SR
            phase_evolution = np.outer(increments, t_steps)
            phase_block = self.phases[:, np.newaxis] + phase_evolution
            self.phases += increments * BLOCK_SIZE
        else:
            # Dynamic Freq OR Dynamic Detune
            # Ensure Dimensions
            # freq: scalar or (512,)
            # current_mults: (7,) or (7, 512)
            
            f_arr = freq
            if np.ndim(f_arr) == 0: f_arr = np.full(BLOCK_SIZE, f_arr) # (512,)
            
            m_arr = current_mults
            if np.ndim(m_arr) == 1: m_arr = m_arr[:, np.newaxis] # (7, 1)
            
            # (7, 512)
            voice_freqs_dyn = f_arr[np.newaxis, :] * m_arr
            
            inc = voice_freqs_dyn / SR
            inc_cum = np.cumsum(inc, axis=1)
            phase_evolution = np.concatenate((np.zeros((7, 1)), inc_cum[:, :-1]), axis=1)
            phase_block = self.phases[:, np.newaxis] + phase_evolution
            self.phases += inc_cum[:, -1]

        phase_block %= 1.0
        self.phases %= 1.0
        
        # Wavetable Lookup (Morphing)
        # table_pos: scalar or (512,)
        
        if np.ndim(table_pos) == 0:
             pos_idx = np.full(BLOCK_SIZE, table_pos * (NUM_FRAMES - 1))
        else:
             pos_idx = table_pos * (NUM_FRAMES - 1)
             
        idx0 = pos_idx.astype(int)
        idx1 = np.minimum(idx0 + 1, NUM_FRAMES - 1)
        alpha = pos_idx - idx0
        
        # Vectorized lookup for variable pos per sample is tricky because table_frames is (64, 2048).
        # We need wave0 = table_frames[idx0, sample_indices].
        # sample_indices is (7, 512). idx0 is (512,).
        # We need to broadcast idx0 to (7, 512) or loop?
        # Actually idx0 depends only on time, so it's (512,). Same frame for all 7 voices at time t.
        # But sample_indices is different for each voice.
        
        # Advanced Indexing:
        # table_frames: (Frames, TableSize)
        # We want result (7, 512).
        # frame_indices: (7, 512) -> broadcasted from idx0 (512,)
        # sample_indices: (7, 512)
        
        idx0_broad = np.broadcast_to(idx0[np.newaxis, :], (7, BLOCK_SIZE))
        idx1_broad = np.broadcast_to(idx1[np.newaxis, :], (7, BLOCK_SIZE))
        
        sample_indices = (phase_block * TABLE_SIZE).astype(int)
        sample_indices = np.clip(sample_indices, 0, TABLE_SIZE - 1)
        
        wave0 = table_frames[idx0_broad, sample_indices]
        wave1 = table_frames[idx1_broad, sample_indices]
        
        alpha_broad = np.broadcast_to(alpha[np.newaxis, :], (7, BLOCK_SIZE))
        waves = (1.0 - alpha_broad) * wave0 + alpha_broad * wave1
        
        # Apply Pan Balance
        p_val = (pan_balance + 1.0) * 0.5
        gain_l = np.cos(p_val * np.pi * 0.5)
        gain_r = np.sin(p_val * np.pi * 0.5)
        
        # Mix Unison -> Stereo
        # waves: (7, 512). pan_l: (7,). gain_l: scalar (or array?)
        # pan_balance usually scalar for UnisonOsc param?
        # But in call we passed `total_pan_a` which might be array if pan mod is active.
        
        # Check pan_balance dim
        if np.ndim(gain_l) > 0:
            # Audio Rate Pan (512,)
            # gain_l: (512,)
            # waves: (7, 512)
            # pan_l: (7,)
            # out = sum(waves * pan_static, axis=0) * gain_dynamic
            
            mix_waves_l = waves * self.pan_l[:, np.newaxis] # (7, 512)
            mix_waves_r = waves * self.pan_r[:, np.newaxis]
            
            out_l = np.sum(mix_waves_l, axis=0) * gain_l
            out_r = np.sum(mix_waves_r, axis=0) * gain_r
        else:
            # Static Pan
            out_l = np.sum(waves * self.pan_l[:, np.newaxis], axis=0) * gain_l
            out_r = np.sum(waves * self.pan_r[:, np.newaxis], axis=0) * gain_r
        
        return out_l, out_r
