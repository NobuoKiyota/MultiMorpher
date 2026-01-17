import numpy as np
from pysfx_dsp import SR, BLOCK_SIZE, ADSR, DSPUtils, AutomationLane

class Voice:
    def __init__(self):
        self.active = False
        self.note = 0
        self.freq = 440.0
        self.adsr = ADSR()
        self.phase = 0.0
        
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
        self.adsr.trigger()
        
    def note_off(self):
        self.adsr.release()

    def process(self, params, pitch_mod=0.0):
        env = self.adsr.process(BLOCK_SIZE)
        if np.all(env <= 0) and self.adsr.state == ADSR.IDLE:
            self.active = False
            return np.zeros(BLOCK_SIZE)

        if abs(self.freq - self.target_freq) > 0.1:
            self.freq += (self.target_freq - self.freq) * (1.0/(1.0 + params.get('portamento', 0)*SR/1000.0/BLOCK_SIZE)) 

        # GUIの 'semi' 値をここで反映 + Pitch Mod
        # Gain applied here
        wave, next_phase = DSPUtils.generate_osc_block(self.freq, self.phase, {'semi': params.get('semi', 0) + pitch_mod})
        self.phase = next_phase
        global_vol = params.get('vol', 0.8)
        return wave * global_vol * self.gain * env

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
                
                # --- Per Voice Pan Logic ---
                # Combine Voice Pan and Master Offset
                final_pan = np.clip(v.pan + master_offset, 0, 127)
                
                # Pan Calculation (Center 64 Snap)
                if final_pan == 64:
                    pan_norm = 0.5
                elif final_pan < 64:
                    pan_norm = final_pan / 128.0
                else:
                    pan_norm = 0.5 + ((final_pan - 64) / 126.0) * 0.5
                
                # Apply Constant Power Pan
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