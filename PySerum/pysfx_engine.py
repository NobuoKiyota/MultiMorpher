import numpy as np
from pysfx_dsp import SR, BLOCK_SIZE, ADSR, DSPUtils, AutomationLane
from pysfx_osc import WavetableGenerator, UnisonOscillator

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
        self.lfo_v = SimpleLFO()
        self.lfo_pan = SimpleLFO()
        
        # Filter State (Biquad Zi) [L/R]
        # Zi size for lfilter (b, a) is max(len(a), len(b)) - 1. Biquad is 3, so size is 2.
        self.lpf_zi_l = np.zeros(2)
        self.lpf_zi_r = np.zeros(2)
        self.hpf_zi_l = np.zeros(2)
        self.hpf_zi_r = np.zeros(2)
        
        # Filter Envelope
        self.filter_adsr = ADSR()
        
        # Advanced OSC A
        self.osc_sfx = UnisonOscillator()
        # Advanced OSC B
        self.osc_sfx_b = UnisonOscillator()
        
        self.sfx_tables = None # Reference to engine tables
        self.phase_rnd = False
        self.start_phase = 0.0
        self.start_phase_b = 0.0
        self.phase_rnd_b = False
        
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
        
        # Trigger Filter Envelope
        self.filter_adsr.trigger()
        
        # Reset Filter State
        self.lpf_zi_l = np.zeros(2)
        self.lpf_zi_r = np.zeros(2)
        self.hpf_zi_l = np.zeros(2)
        self.hpf_zi_r = np.zeros(2)
        
        # Reset Advanced OSC Phases
        self.osc_sfx.reset_phases(self.start_phase, self.phase_rnd)
        self.osc_sfx_b.reset_phases(self.start_phase_b, self.phase_rnd_b)
        
    def note_off(self):
        self.adsr.release()
        self.filter_adsr.release()

    def process(self, params, pitch_mod=0.0):
        """
        Returns (left, right) block tuple.
        """
        env = self.adsr.process(BLOCK_SIZE)
        if np.all(env <= 0) and self.adsr.state == ADSR.IDLE:
            self.active = False
            zero = np.zeros(BLOCK_SIZE)
            return zero, zero

        if abs(self.freq - self.target_freq) > 0.1:
            self.freq += (self.target_freq - self.freq) * (1.0/(1.0 + params.get('portamento', 0)*SR/1000.0/BLOCK_SIZE)) 

        # --- LFOs ---
        lfo_p_val = np.zeros(BLOCK_SIZE)
        if params.get('lfo_p_range', 0) > 0:
            lfo_p_val = self.lfo_p.generate(BLOCK_SIZE, params.get('lfo_p_speed', 5), 
                                            params.get('lfo_p_type', 0), params.get('lfo_p_shape', 50))
            lfo_p_val *= (params['lfo_p_range'] / 100.0)

        mod_vol = 1.0
        if params.get('lfo_v_range', 0) > 0:
            lfo_v_raw = self.lfo_v.generate(BLOCK_SIZE, params.get('lfo_v_speed', 5), 
                                            params.get('lfo_v_type', 0), params.get('lfo_v_shape', 50))
            norm_lfo = (lfo_v_raw + 1.0) * 0.5
            depth = params['lfo_v_range'] / 100.0
            mod_vol = 1.0 - (depth * (1.0 - norm_lfo))

        pan_mod_val = np.zeros(BLOCK_SIZE)
        if params.get('lfo_pan_range', 0) > 0:
            lfo_pan_raw = self.lfo_pan.generate(BLOCK_SIZE, params.get('lfo_pan_speed', 5),
                                                params.get('lfo_pan_type', 0), params.get('lfo_pan_shape', 50))
            pan_mod_val = lfo_pan_raw * (params['lfo_pan_range'] / 100.0 * 64.0)
            
        # --- Filter Envelope ---
        f_env = self.filter_adsr.process(BLOCK_SIZE)
        # Apply Env to Filter params later


        # Total Pitch Modulation (Semi)
        total_semi = params.get('semi', 0) + pitch_mod + lfo_p_val
        
        # --- Automation & Modulations for Advanced OSC ---
        # 1. Warp (Table Pos)
        # static + auto (via Engine params passed as array or scalar)
        warp_static = params.get('osc_a_pos', 0.0)
        warp_auto_val = params.get('warp_auto_val', 0.0) # From Engine (scalar or array? Engine gives scalar per block?)
        # NOTE: Engine.generate_block usually gives ONE value per block for automation currently.
        # But we want smooth modulation? 
        # AutomationLane.get_value(dt) updates time.
        # If we want per-sample automation, we need AutomationLane to return array.
        # Current AutomationLane is per-block scalar. 
        # We will Linear Interpolate this Block Scalar if it changes fast, or just use block scalar (Stepped).
        # For Warp/Detune, block stepped (approx 10ms) might be OK, but ideally we interpolate.
        # Let's assume block scalar for now as per current architecture.
        
        warp_depth = params.get('osc_warpautorange', 0.0)
        total_warp = np.clip(warp_static + (warp_auto_val * warp_depth), 0.0, 1.0)
        
        # 2. Detune
        det_static = params.get('osc_a_unison', 0.0)
        det_auto_val = params.get('detune_auto_val', 0.0)
        det_depth = params.get('osc_detuneautorange', 0.0)
        total_detune = np.clip(det_static + (det_auto_val * det_depth), 0.0, 1.0)
        

        # --- Output Buffers ---
        out_l = np.zeros(BLOCK_SIZE)
        out_r = np.zeros(BLOCK_SIZE)
        
        # 1. Simple OSC (Legacy Layer)
        # ----------------------------
        # If OscType is 0-3.
        # Check volume? SimpleOsc doesn't have separate vol param in UI yet? 
        # But 'vol' is Global Master.
        # Let's assume SimpleOsc is ALWAYS ON unless specific mode? 
        # User said "OSC:A is master volume". That implies OSC:A is a NEW layer.
        # What controls SimpleOsc volume? "MasterVolume" (which is global).
        # We'll continue to render SimpleOsc as "Layer 1".
        
        # Prepare params for DSP call
        dsp_params = params.copy()
        dsp_params['semi'] = total_semi
        
        wave_simple, next_phase = DSPUtils.generate_osc_block(self.freq, self.phase, dsp_params, vectorized_fm=True)
        self.phase = next_phase
        
        # Pan Processing for Simple OSC (Scalar Pan + LFO)
        # master_pan handled in engine or here? Let's do here for unified stereo output.
        master_pan_offset = params.get('master_pan_offset', 0) # Passed from Engine
        
        final_pan = np.clip(self.pan + master_pan_offset + pan_mod_val, 0, 127)
        
        # Vectorized Pan Law
        pan_norm = np.where(final_pan < 64, 
                            final_pan / 128.0, 
                            0.5 + ((final_pan - 64) / 126.0) * 0.5)
        pan_mp = pan_norm * (np.pi / 2.0)
        gain_l = np.cos(pan_mp)
        gain_l = np.cos(pan_mp)
        gain_r = np.sin(pan_mp)
        
        simple_osc_vol = params.get('simple_osc_vol', 1.0)
        out_l += wave_simple * gain_l * simple_osc_vol
        out_r += wave_simple * gain_r * simple_osc_vol

        # 2. Advanced OSC (OSC:A)
        # -----------------------
        osc_a_vol = params.get('osc_a_vol', 0.0)
        if osc_a_vol > 0.001 and self.sfx_tables:
            # Table Selection
            tbl_idx = params.get('osc_a_table', 0)
            table_key = "Classic"
            if tbl_idx == 1: table_key = "Monster"
            elif tbl_idx == 2: table_key = "Basic Shapes"
            
            tables = self.sfx_tables.get(table_key, self.sfx_tables["Classic"])
            
            # Setup Unison Params (Initial Static, Dynamic handling is in process)
            # self.osc_sfx.set_detune(params.get('osc_a_unison', 0.0)) # Removed, handled in process() override
            
            # Update Phase Params if changed (usually Init only, but here we sync)
            self.phase_rnd = params.get('osc_a_rand', False)
            self.start_phase = params.get('osc_a_phase', 0.0)
            
            # Pitch Calculation for OSC:A
            # It has its own semi/oct/fine
            # Plus the global/voice pitch mod
            # Base Freq matches Voice Note
            # Apply Oct/Semi/Fine offset
            # Apply Oct/Semi/Fine offset
            semi_a = params.get('osc_a_semi', 0)
            oct_a = params.get('osc_a_oct', 0)
            fine_a = params.get('osc_a_fine', 0)
            
            offset_semis = semi_a + (oct_a * 12) + (fine_a / 100.0)

            # Pitch Calculation for OSC:A
            # Uses Global Pitch Mod (Glide/LFO) + OSC:A Specific Offsets
            # Excludes params['semi'] (SimpleOsc Transpose)
            mods_semi_a = pitch_mod + lfo_p_val + offset_semis
            
            freq_a = self.freq * (2.0 ** (mods_semi_a / 12.0))
            
            # Process OSC:A
            # Pan: OSC:A Pan + Mod Pan?
            pan_a = params.get('osc_a_pan', 0.0) # -1.0 to 1.0
            # Mix with pan_mod_val (which is -64 to 64 approx, scaled).
            # Map pan_mod_val to -1.0..1.0
            pan_mod_norm = pan_mod_val / 64.0 
            total_pan_a = np.clip(pan_a + pan_mod_norm, -1.0, 1.0)
            
            uni_l, uni_r = self.osc_sfx.process(freq_a, tables, total_warp, total_pan_a, detune_amount=total_detune)
            
            out_l += uni_l * osc_a_vol
            out_r += uni_r * osc_a_vol

        # 3. Advanced OSC (OSC:B)
        # -----------------------
        osc_b_vol = params.get('osc_b_vol', 0.0)
        if osc_b_vol > 0.001 and self.sfx_tables:
            # Table Selection
            tbl_idx = params.get('osc_b_table', 0)
            table_key = "Classic"
            if tbl_idx == 1: table_key = "Monster"
            elif tbl_idx == 2: table_key = "Basic Shapes"
            
            tables = self.sfx_tables.get(table_key, self.sfx_tables["Classic"])
            
            # Phase
            self.phase_rnd_b = False # params.get('osc_b_rand', False) # No param yet
            self.start_phase_b = params.get('osc_b_phase', 0.0)
            
            # Warp
            warp_static = params.get('osc_b_pos', 0.0)
            warp_auto_val = params.get('warp_auto_b_val', 0.0)
            warp_depth = params.get('osc_b_warpautorange', 0.0)
            total_warp = np.clip(warp_static + (warp_auto_val * warp_depth), 0.0, 1.0)
            
            # Detune
            det_static = params.get('osc_b_unison', 0.0)
            det_auto_val = params.get('detune_auto_b_val', 0.0)
            det_depth = params.get('osc_b_detuneautorange', 0.0)
            total_detune = np.clip(det_static + (det_auto_val * det_depth), 0.0, 1.0) # UnisonOsc takes 0-1 amount for spread

            # Pitch Calculation for OSC:B
            semi_b = params.get('osc_b_semi', 0)
            oct_b = params.get('osc_b_oct', 0)
            
            offset_semis = semi_b + (oct_b * 12)
            mods_semi_b = pitch_mod + lfo_p_val + offset_semis
            
            freq_b = self.freq * (2.0 ** (mods_semi_b / 12.0))
            
            # Pan
            pan_b = params.get('osc_b_pan', 0.0)
            pan_mod_norm = pan_mod_val / 64.0 
            total_pan_b = np.clip(pan_b + pan_mod_norm, -1.0, 1.0)
            
            uni_l, uni_r = self.osc_sfx_b.process(freq_b, tables, total_warp, total_pan_b, detune_amount=total_detune)
            
            out_l += uni_l * osc_b_vol
            out_r += uni_r * osc_b_vol

        global_vol = params.get('vol', 0.8)
        out_l *= env * global_vol * self.gain * mod_vol
        out_r *= env * global_vol * self.gain * mod_vol
        
        # --- Filter Section (Before Effects) ---
        # NOTE: If we do dynamic modulation per sample, we need loop. 
        # But Biquad calc is heavy. We do Block Processing with AVERAGE modulation for now,
        # OR we can assume AutomationLane gives a single value per block if we call it once?
        # The user requested "AutoRange" with "Image".
        # We'll calculate ONE set of coefficients per block based on average envelope/auto value.
        # This might cause "stepping" if block size is large (512 @ 48k is ~10ms).
        # 10ms stepping is audible for very fast sweeps (zips).
        # But for Python realtime, per-sample biquad is impossible without C++/Numba.
        # We stick to Block Processing.
        
        # Calculate Modulators (Mean of block)
        env_val = np.mean(f_env)
        
        # LPF
        if params.get('lpf_enable', False):
            base_cut = params.get('lpf_cutoff', 20000)
            
            # Auto (Image/Lane)
            # Assuming 'pitch' type automation logic works for Filters too. 
            # We need to access engine automation... Voice process doesn't see engine.
            # Passed via params? 
            # Params is a dict. If automation is running, engine should write current value to params?
            # Or we pass a callback?
            # User requirement 4: "Combine static setting and Hand-drawn Image Automation in pysfx_engine.py"
            # Engine 'generate_block' should calculate automation value and pass it in 'params'.
            
            auto_val = params.get('lpf_auto_val', 0.0) # -1.0 to 1.0 (from automation)
            auto_depth = params.get('lpf_autorange', 0.0)
            
            env_depth = params.get('filter_envamt', 0.0)
            
            # Env is 0..1. Map to -1..1? No, usually 0..1 add.
            # If EnvAmt is negative, it inverts.
            
            # Total Mod in Hz
            # Linear Add or Logarithmic? Synth filters usually Log (Octaves).
            # But the param says "Hz". We'll do Linear for simplicity or check if user specified.
            # "LPF_AutoRange: ... (Hz)" -> Linear addition.
            
            mod_freq = (auto_val * auto_depth) + (env_val * env_depth * 10000.0) # Scaling EnvAmt? EnvAmt is -1.0 to 1.0. 
            # If EnvAmt is 1.0, what is the range? 
            # Usually Env Amount is in Hz or Octaves.
            # Config says "Filter_EnvAmt" range -1.0 to 1.0.
            # Let's assume 1.0 = Full Sweep (up to 10kHz?)
            # Or maybe EnvAmt multiplies the Cutoff?
            # Let's assume Linear Hz addition: EnvAmt * 10000Hz (Arbitrary plausible range)
            
            final_cut = np.clip(base_cut + mod_freq, 20.0, 20000.0)
            
            # Resonance
            base_res = params.get('lpf_resonance', 0.0) # 0.0-1.0
            res_auto_val = params.get('lpf_res_auto_val', 0.0)
            res_depth = params.get('lpf_resautorange', 0.0)
            
            final_res = np.clip(base_res + (res_auto_val * res_depth), 0.0, 1.0)
            # Map 0..1 to Q. Q=0.707 is flat. Q=10 is scream.
            # Mapping: Q = 0.707 + (final_res * 20.0)
            q_val = 0.707 + (final_res * 10.0)
            
            b, a = DSPUtils.get_biquad_coeffs('lpf', final_cut, q_val, SR)
            
            out_l, self.lpf_zi_l = DSPUtils.apply_biquad_block(out_l, b, a, self.lpf_zi_l)
            out_r, self.lpf_zi_r = DSPUtils.apply_biquad_block(out_r, b, a, self.lpf_zi_r)

        # HPF
        if params.get('hpf_enable', False):
            base_cut = params.get('hpf_cutoff', 20.0)
            auto_val = params.get('hpf_auto_val', 0.0)
            auto_depth = params.get('hpf_autorange', 0.0)
            
            # Apply Env to HPF too? "Filter_EnvAmt" -> "LPF/HPF Common Env Amount"
            # Yes.
            env_depth = params.get('filter_envamt', 0.0)
            mod_freq = (auto_val * auto_depth) + (env_val * env_depth * 10000.0)
            
            final_cut = np.clip(base_cut + mod_freq, 20.0, 20000.0)
            
            base_res = params.get('hpf_resonance', 0.0)
            res_auto_val = params.get('hpf_res_auto_val', 0.0)
            res_depth = params.get('hpf_resautorange', 0.0)
            
            final_res = np.clip(base_res + (res_auto_val * res_depth), 0.0, 1.0)
            q_val = 0.707 + (final_res * 10.0)
            
            b, a = DSPUtils.get_biquad_coeffs('hpf', final_cut, q_val, SR)
            
            out_l, self.hpf_zi_l = DSPUtils.apply_biquad_block(out_l, b, a, self.hpf_zi_l)
            out_r, self.hpf_zi_r = DSPUtils.apply_biquad_block(out_r, b, a, self.hpf_zi_r)

        
        return out_l, out_r

class PyQuartzEngine:
    def __init__(self):
        self.voices = [Voice() for _ in range(64)] # Increased from 16 to 64 for Detune Stacks
        self.next_v = 0
        self.automations = {}
        self.filter_zi_l = np.zeros(1)
        self.filter_zi_r = np.zeros(1)
        
        # Load tables
        self.wavetables = WavetableGenerator.generate_tables()
        for v in self.voices:
            v.sfx_tables = self.wavetables
            
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

    def set_filter_adsr(self, a, d, s, r):
        for v in self.voices: v.filter_adsr.set_params(a, d, s, r)

    def generate_block(self):
        dt = BLOCK_SIZE / SR
        
        # 1. Update Automations
        pitch_mod = 0.0
        if 'pitch' in self.automations:
            pitch_mod = self.automations['pitch'].get_value(dt)
            
        auto_targets = [
            'lpf_auto', 'lpf_res_auto', 'hpf_auto', 'hpf_res_auto', 
            'warp_auto', 'detune_auto', # A
            'warp_auto_b', 'detune_auto_b' # B
        ]
        for tgt in auto_targets:
            val = 0.0
            if tgt in self.automations:
                 val = self.automations[tgt].get_value(dt)
            self.params[f'{tgt}_val'] = val

        # 2. Init Buffers & Global Params
        ml, mr = np.zeros(BLOCK_SIZE), np.zeros(BLOCK_SIZE)
        
        master_pan = self.params.get('master_pan', 64)
        self.params['master_pan_offset'] = master_pan - 64

        # 3. Process Voices
        for v in self.voices:
            if v.active:
                vl, vr = v.process(self.params, pitch_mod)
                ml += vl
                mr += vr

            
        if self.params['dist'] > 0:
            ml = DSPUtils.apply_distortion(ml, self.params['dist'])
            mr = DSPUtils.apply_distortion(mr, self.params['dist'])
            
        return np.column_stack((ml, mr)).flatten()