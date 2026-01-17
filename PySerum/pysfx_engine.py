import numpy as np
from pysfx_dsp import SR, BLOCK_SIZE, ADSR, DSPUtils, AutomationLane

class SimpleLFO:
    def __init__(self, sr=SR):
        self.sr = sr
        self.phase = 0.0
        
    def generate(self, num_samples, rate_hz, shape_type, width_pct=50):
        if rate_hz <= 0: return np.zeros(num_samples)
        
        delta = (rate_hz / self.sr)
        phases = self.phase + np.arange(num_samples) * delta
        phases %= 1.0 
        self.phase = (self.phase + num_samples * delta) % 1.0
        
        if shape_type == 0: # Sine
            return np.sin(2 * np.pi * phases)
        elif shape_type == 1: # Triangle
            return 4.0 * np.abs(phases - 0.5) - 1.0
        elif shape_type == 2: # Saw
            return 2.0 * phases - 1.0
        elif shape_type == 3: # Square
            w = width_pct / 100.0
            return np.where(phases < w, 1.0, -1.0)
        elif shape_type == 4: # Random (Noise)
            return np.random.uniform(-1.0, 1.0, num_samples)
        return np.zeros(num_samples)
        
    def reset(self):
        self.phase = 0.0

class Voice:
    def __init__(self):
        self.active = False
        self.note = 0
        self.freq = 440.0
        self.adsr = ADSR()
        self.adsr = ADSR()
        self.phase = 0.0
        self.lfo_p = SimpleLFO()
        self.lfo_v = SimpleLFO()
        self.lfo_pan = SimpleLFO()
        
    def note_on(self, note, velocity=1.0, detune=0.0, glide_time=0.0, pan=64):
        # detune: semitones
        target_freq = 440.0 * (2.0 ** ((note + detune - 69) / 12.0))
        self.gain = velocity
        self.pan = pan # 0-127
        
        if self.active and glide_time > 0:
            self.target_freq = target_freq
            self.glide_coeff = 1.0 - np.exp(-1.0 / (glide_time * SR / 1000.0))
            self.glide_alpha = 1.0 / (glide_time * SR / 1000.0 + 1.0)
        else:
            self.note = note
            self.freq = target_freq
            self.target_freq = target_freq
            self.glide_alpha = 1.0
            
        self.active = True
        self.active = True
        self.adsr.trigger()
        self.lfo_p.reset()
        self.lfo_v.reset()
        self.lfo_pan.reset()
        
    def note_off(self):
        self.adsr.release()

    def process(self, params, pitch_mod=0.0):
        env = self.adsr.process(BLOCK_SIZE)
        if np.all(env <= 0) and self.adsr.state == ADSR.IDLE:
            self.active = False
            return np.zeros(BLOCK_SIZE)

        if abs(self.freq - self.target_freq) > 0.1:
            self.freq += (self.target_freq - self.freq) * (1.0/(1.0 + params.get('portamento', 0)*SR/1000.0/BLOCK_SIZE)) 

        # --- LFO Generation ---
        # Pitch LFO (Cent range)
        lfo_p_range = params.get('lfo_p_range', 0)
        lfo_p_val = np.zeros(BLOCK_SIZE)
        if lfo_p_range > 0:
            lfo_p_val = self.lfo_p.generate(BLOCK_SIZE, params.get('lfo_p_speed', 5), 
                                            params.get('lfo_p_type', 0), params.get('lfo_p_shape', 50))
            # Convert cent to semitone: val * (range / 100)
            lfo_p_val = lfo_p_val * (lfo_p_range / 100.0)

        # Vol LFO (0-100%)
        lfo_v_range = params.get('lfo_v_range', 0)
        mod_vol = 1.0
        if lfo_v_range > 0:
            lfo_v_raw = self.lfo_v.generate(BLOCK_SIZE, params.get('lfo_v_speed', 5), 
                                            params.get('lfo_v_type', 0), params.get('lfo_v_shape', 50))
            # Unipolar modulation? Or Bipolar? Usually Tremolo varies from 1.0 down to (1-depth).
            # If shape is -1 to 1.
            # Let's map -1..1 to (1-depth)..1 
            # Depth 100% -> 0..1. Depth 0% -> 1..1.
            # Formula: 1.0 - (depth/100 * (1 - raw)/2) ? No that's complex.
            # Simple Tremolo: gain = 1.0 + raw * (depth/200.0) ... can exceed 1.
            # Let's do: gain = 1.0 - (depth/100.0) * ((raw + 1)/2) ? (raw+1)/2 is 0..1.
            # depth=100 -> gain = 1.0 - 1.0 * (0..1) -> 1..0. Correct.
            norm_lfo = (lfo_v_raw + 1.0) * 0.5 # 0.0 to 1.0
            depth = lfo_v_range / 100.0
            mod_vol = 1.0 - (depth * (1.0 - norm_lfo)) # If LFO is 1, mod is 1. If LFO is 0, mod is 1-depth.

        # Pan LFO (0-100%) stored in self.mod_pan for engine to pick up?
        # Voice process returns wave. Pan is applied in Engine.generate_block via self.pan.
        # But we need per-sample pan modulation for audio rate pan?
        # Engine loop applies pan using scalar v.pan.
        # If we want Audio Rate Pan, we must return stereo signal from Voice?
        # Or return mod_pan array?
        # Refactoring Engine to handle per-sample pan from Voice is expensive/complex change.
        # But "30kHz Speed" on Pan implies it.
        # Let's return (wave, pan_mod_array) ?
        # Or apply pan INSIDE voice and return stereo?
        # That changes signature.
        
        # Alternative: We return `wave` and store `self.pan_mod_buffer` for Engine to read?
        lfo_pan_range = params.get('lfo_pan_range', 0)
        self.pan_mod_buffer = np.zeros(BLOCK_SIZE)
        if lfo_pan_range > 0:
            lfo_pan_raw = self.lfo_pan.generate(BLOCK_SIZE, params.get('lfo_pan_speed', 5),
                                                params.get('lfo_pan_type', 0), params.get('lfo_pan_shape', 50))
            # Pan range %: offset from center? or offset from current pan?
            # 0..127 scale.
            # depth 100% -> full sweep L to R?
            # range is 0-100.
            # Let's say +/- (range/100 * 64).
            self.pan_mod_buffer = lfo_pan_raw * (lfo_pan_range / 100.0 * 64.0)

        # GUIの 'semi' 値をここで反映 + Pitch Mod + LFO Pitch
        total_semi = params.get('semi', 0) + pitch_mod + lfo_p_val
        
        # Prepare params for DSP call (Include OscType and modulated semi)
        dsp_params = params.copy()
        dsp_params['semi'] = total_semi
        
        wave, next_phase = DSPUtils.generate_osc_block(self.freq, self.phase, dsp_params, vectorized_fm=True)
        self.phase = next_phase
        global_vol = params.get('vol', 0.8)
        return wave * global_vol * self.gain * env * mod_vol

class PyQuartzEngine:
    def __init__(self):
        self.voices = [Voice() for _ in range(64)] # Increased from 16 to 64 for Detune Stacks
        self.next_v = 0
        self.automations = {}
        self.filter_zi_l = np.zeros(1)
        self.filter_zi_r = np.zeros(1)
        # 初期パラメータ
        self.params = {
            'vol': 0.8, 
            'semi': 0, 
            'cutoff': 20000, 
            'dist': 0, 
            'filter_en': True
        }

    def update_params(self, new_params):
        """GUIやFactoryからの設定値をエンジンに同期させる"""
        self.params.update(new_params)

    def note_on(self, n, velocity=1.0, detune=0.0, pan=64):
        v = self.voices[self.next_v]
        v.note_on(n, velocity, detune, self.params.get('portamento', 0), pan)
        self.next_v = (self.next_v + 1) % len(self.voices)

    def note_off(self, n):
        for v in self.voices:
            if v.note == n: v.note_off()

    def set_adsr(self, a, d, s, r):
        for v in self.voices: v.adsr.set_params(a, d, s, r)

    def generate_block(self):
        dt = BLOCK_SIZE / SR
        pitch_mod = 0.0
        if 'pitch' in self.automations:
            pitch_mod = self.automations['pitch'].get_value(dt)

        ml, mr = np.zeros(BLOCK_SIZE), np.zeros(BLOCK_SIZE)
        
        # Master Pan
        master_pan = self.params.get('master_pan', 64)
        # Shift master_pan to -64 to +63 range for adding?
        # Or simple average?
        # "Master Pan" usually shifts the whole stereo field.
        # Let's do: FinalPan = VoicePan + (MasterPan - 64)
        # Clamp to 0-127.
        
        master_offset = master_pan - 64

        for v in self.voices:
            if v.active:
                sample = v.process(self.params, pitch_mod)
                
                # --- Per Voice Pan Logic (Vectorized) ---
                # v.pan: scalar, master_offset: scalar
                # v.pan_mod_buffer: array (if LFO active) or 0
                
                # Check if we have modulation
                if hasattr(v, 'pan_mod_buffer') and np.any(v.pan_mod_buffer):
                    # Vectorized Pan
                    raw_pan = v.pan + master_offset + v.pan_mod_buffer
                    raw_pan = np.clip(raw_pan, 0, 127)
                    
                    # Vectorized Center Snap Logic
                    # if val < 64: val/128. else: 0.5 + (val-64)/126 * 0.5
                    pan_norm = np.where(raw_pan < 64, 
                                        raw_pan / 128.0, 
                                        0.5 + ((raw_pan - 64) / 126.0) * 0.5)
                                        
                    pan_mp = pan_norm * (np.pi / 2.0)
                    gain_l = np.cos(pan_mp)
                    gain_r = np.sin(pan_mp)
                    
                    ml += sample * gain_l
                    mr += sample * gain_r
                else:
                    # Scalar Pan (Faster)
                    final_pan = np.clip(v.pan + master_offset, 0, 127)
                    
                    if final_pan == 64:
                        pan_norm = 0.5
                    elif final_pan < 64:
                        pan_norm = final_pan / 128.0
                    else:
                        pan_norm = 0.5 + ((final_pan - 64) / 126.0) * 0.5
                    
                    pan_mp = pan_norm * (np.pi / 2.0)
                    gain_l = np.cos(pan_mp)
                    gain_r = np.sin(pan_mp)
                    
                    ml += sample * gain_l
                    mr += sample * gain_r
                

        
        # GUIの 'cutoff' や 'dist' をここで反映
        if self.params['filter_en']:
            ml, self.filter_zi_l = DSPUtils.apply_lowpass(ml, self.params['cutoff'], self.filter_zi_l)
            mr, self.filter_zi_r = DSPUtils.apply_lowpass(mr, self.params['cutoff'], self.filter_zi_r)
            
        if self.params['dist'] > 0:
            ml = DSPUtils.apply_distortion(ml, self.params['dist'])
            mr = DSPUtils.apply_distortion(mr, self.params['dist'])
            
        return np.column_stack((ml, mr)).flatten()