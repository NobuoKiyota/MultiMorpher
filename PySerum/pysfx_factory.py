import numpy as np
import scipy.io.wavfile
import os
import datetime
import random
from pysfx_engine import PyQuartzEngine, SR, BLOCK_SIZE
from pysfx_factory_logic import GenerationLogic

class PyQuartzFactory:
    def __init__(self):
        self.engine = PyQuartzEngine()
        self.out_dir = "Output"
        if not os.path.exists(self.out_dir): os.makedirs(self.out_dir)

        # Initialize ImageTracer and update PitchType param range
        try:
            from pysfx_image_tracer import ImageTracer
            from pysfx_param_config import PySFXParams
            tracer = ImageTracer()
            count = tracer.get_curve_count()
            for p in PySFXParams.DEFINITIONS:
                if p.name == "PitchType":
                    p.max = 2 + count
                    p.desc = f"Type(0:Flat,1:Lin,2:Exp,3-{2+count}:Img)"
                    break
        except Exception as e:
            print(f"Warning: Failed to init ImageTracer: {e}")

    def _get_param_value(self, config, name):
        """Random設定を考慮して値を取得するヘルパー"""
        node = config[name]
        if node.get("random"):
            return random.uniform(float(node["min"]), float(node["max"]))
        return float(node["value"])

    def run_advanced_batch(self, config, num_files=10, progress_callback=None):
        print(f"--- PyQuartz SFX Factory Production: {num_files} files ---")
        
        for p_idx in range(num_files):
            if progress_callback: progress_callback(p_idx, num_files)
            # 1. 各種パラメータの決定 (Random設定対応)
            duration = self._get_param_value(config, "Duration")
            root_note = int(self._get_param_value(config, "NoteRange"))
            num_voices = int(self._get_param_value(config, "Voices"))
            strum_ms = self._get_param_value(config, "Strum")
            
            # 2. エンジン内部パラメータの同期
            engine_updates = {
                'vol': self._get_param_value(config, "MasterVolume"), 
                'osc_type': int(self._get_param_value(config, "SimpleOscType")),
                'simple_osc_vol': self._get_param_value(config, "SimpleOscVolume"),
                'semi': 0, 
                'cutoff': 20000, 
                'dist': 0,
                'filter_en': True,
                'portamento': self._get_param_value(config, "Portament"),
                'master_pan': self._get_param_value(config, "MasterPan"),
                
                # --- LFO Params ---
                'lfo_p_range': self._get_param_value(config, "LFO_P_Range"),
                'lfo_p_type': int(self._get_param_value(config, "LFO_P_Type")),
                'lfo_p_speed': self._get_param_value(config, "LFO_P_Speed"),
                'lfo_p_shape': self._get_param_value(config, "LFO_P_Shape"),
                
                'lfo_v_range': self._get_param_value(config, "LFO_V_Range"),
                'lfo_v_type': int(self._get_param_value(config, "LFO_V_Type")),
                'lfo_v_speed': self._get_param_value(config, "LFO_V_Speed"),
                'lfo_v_shape': self._get_param_value(config, "LFO_V_Shape"),
                
                'lfo_pan_range': self._get_param_value(config, "LFO_Pan_Range"),
                'lfo_pan_type': int(self._get_param_value(config, "LFO_Pan_Type")),
                'lfo_pan_speed': self._get_param_value(config, "LFO_Pan_Speed"),
                'lfo_pan_shape': self._get_param_value(config, "LFO_Pan_Shape"),
                
                # --- Filter Params ---
                'filter_envamt': self._get_param_value(config, "Filter_EnvAmt"),
                
                'lpf_enable': config["LPF_Enable"]["value"],
                'lpf_cutoff': self._get_param_value(config, "LPF_Cutoff"),
                'lpf_resonance': self._get_param_value(config, "LPF_Resonance"),
                'lpf_autorange': self._get_param_value(config, "LPF_AutoRange"),
                'lpf_resautorange': self._get_param_value(config, "LPF_ResAutoRange"),

                'hpf_enable': config["HPF_Enable"]["value"],
                'hpf_cutoff': self._get_param_value(config, "HPF_Cutoff"),
                'hpf_resonance': self._get_param_value(config, "HPF_Resonance"),
                'hpf_autorange': self._get_param_value(config, "HPF_AutoRange"),
                'hpf_resautorange': self._get_param_value(config, "HPF_ResAutoRange"),
                
                # --- OSC:A Params ---
                'osc_a_vol': self._get_param_value(config, "OSC:A"),
                'osc_a_table': int(self._get_param_value(config, "OSC:A:Table")),
                'osc_a_pos': self._get_param_value(config, "OSC:A:Pos"),
                'osc_a_unison': self._get_param_value(config, "OSC:A:Unison"),
                'osc_a_semi': int(self._get_param_value(config, "OSC:A:Semi")),
                'osc_a_oct': int(self._get_param_value(config, "OSC:A:Oct")),
                # 'osc_a_fine': int(self._get_param_value(config, "OSC:A:Fine")), # Removed from config
                'osc_a_pan': self._get_param_value(config, "OSC:A:Pan"),
                'osc_a_phase': self._get_param_value(config, "OSC:A:Phase"),
                'osc_warpautorange': self._get_param_value(config, "OSC:A:WarpAutoRange"),
                'osc_detuneautorange': self._get_param_value(config, "OSC:A:DetuneAutoRange"),
                # 'osc_a_rand': config["OSC:A:Rand"]["value"], # Boolean REMOVED
                
                # --- OSC:B Params ---
                'osc_b_vol': self._get_param_value(config, "OSC:B"),
                'osc_b_table': int(self._get_param_value(config, "OSC:B:Table")),
                'osc_b_pos': self._get_param_value(config, "OSC:B:Pos"),
                'osc_b_unison': self._get_param_value(config, "OSC:B:Unison"),
                'osc_b_semi': int(self._get_param_value(config, "OSC:B:Semi")),
                'osc_b_oct': int(self._get_param_value(config, "OSC:B:Oct")),
                'osc_b_pan': self._get_param_value(config, "OSC:B:Pan"),
                'osc_b_phase': self._get_param_value(config, "OSC:B:Phase"),
                'osc_b_warpautorange': self._get_param_value(config, "OSC:B:WarpAutoRange"),
                'osc_b_detuneautorange': self._get_param_value(config, "OSC:B:DetuneAutoRange"),
            }
            self.engine.update_params(engine_updates)
            
            # --- Pitch Automation Setup ---
            pitch_range_cents = self._get_param_value(config, "PitchRange")
            # Try/Except for PitchType in case config is old
            try: pitch_type = int(self._get_param_value(config, "PitchType"))
            except: pitch_type = 0
            
            pitch_val = 0
            if pitch_range_cents != 0 and pitch_type != 0:
                pitch_val = int(self._get_param_value(config, "PitchCurve"))
                # Use higher resolution (64 points) for smooth curves
                points = GenerationLogic.get_pitch_curve(pitch_range_cents, 64, curve_val=pitch_val, curve_type=pitch_type)
                range_semis = pitch_range_cents / 100.0
                scaled_points = [(t, v * range_semis) for t, v in points]
                from pysfx_dsp import AutomationLane
                auto = AutomationLane(duration)
                auto.points = scaled_points
                self.engine.automations['pitch'] = auto
            else:
                if 'pitch' in self.engine.automations: del self.engine.automations['pitch']

            # --- Filter Automation Setup ---
            # Helper for Filter automation generation
            def setup_filter_auto(target_key, type_param, range_param_name):
                try: 
                    atype = int(self._get_param_value(config, type_param))
                    arange = self._get_param_value(config, range_param_name)
                    
                    if arange != 0 and atype != 0:
                        # Use default curve/warp of 64 (Linear) since no specific param exists
                        points = GenerationLogic.get_pitch_curve(arange, 64, curve_val=64, curve_type=atype)
                        # Points are (t, 0.0-1.0). Range scaling handled in Engine (val * range).
                        # So we just pass raw 0.0-1.0 value? 
                        # Engine does: (auto_val * auto_depth).
                        # So automation should return 0.0 to 1.0.
                        # Wait, get_pitch_curve returns (t, val). Val depends on logic.
                        # Logic returns 0.0-1.0 if 'Image' or 'Linear'.
                        # So we assign directly.
                        from pysfx_dsp import AutomationLane
                        auto = AutomationLane(duration)
                        auto.points = points
                        self.engine.automations[target_key] = auto
                    else:
                         if target_key in self.engine.automations: del self.engine.automations[target_key]
                except Exception as e:
                    # print(f"Auto setup err {target_key}: {e}")
                    pass

            setup_filter_auto('lpf_auto', "LPF_AutoType", "LPF_AutoRange")
            setup_filter_auto('lpf_res_auto', "LPF_ResAutoType", "LPF_ResAutoRange")
            setup_filter_auto('hpf_auto', "HPF_AutoType", "HPF_AutoRange")
            setup_filter_auto('hpf_res_auto', "HPF_ResAutoType", "HPF_ResAutoRange")
            setup_filter_auto('warp_auto', "OSC:A:WarpAutoType", "OSC:A:WarpAutoRange")
            setup_filter_auto('detune_auto', "OSC:A:DetuneAutoType", "OSC:A:DetuneAutoRange")
            setup_filter_auto('warp_auto_b', "OSC:B:WarpAutoType", "OSC:B:WarpAutoRange")
            setup_filter_auto('detune_auto_b', "OSC:B:DetuneAutoType", "OSC:B:DetuneAutoRange")

            # 3. ADSRの設定
            a = self._get_param_value(config, "AmpAttack") / 1000.0
            d = self._get_param_value(config, "AmpDecay") / 1000.0
            s = self._get_param_value(config, "AmpSustain") / 127.0
            r = self._get_param_value(config, "AmpRelease") / 1000.0
            self.engine.set_adsr(a, d, s, r)

            # Filter ADSR
            fa = self._get_param_value(config, "Filter_Attack") / 1000.0
            fd = self._get_param_value(config, "Filter_Decay") / 1000.0
            fs = self._get_param_value(config, "Filter_Sustain") # 0-1
            fr = self._get_param_value(config, "Filter_Release") / 1000.0
            self.engine.set_filter_adsr(fa, fd, fs, fr)

            # 4. ノート生成
            is_chord = config["Chord"]["value"]
            notes, chord_name = GenerationLogic.get_chord_notes(root_note, num_voices, is_chord)
            
            # --- Voice & Detune Parameters ---
            vol_root = self._get_param_value(config, "RouteVoiceVolume")
            vol_multi = self._get_param_value(config, "MultiVoiceVolume")
            
            detune_count = int(self._get_param_value(config, "DetuneVoice"))
            detune_range_cents = self._get_param_value(config, "DetuneRange")
            detune_vol_ratio = self._get_param_value(config, "DetuneVolume")
            
            # 5. レンダリング
            # Phase 1: Hold (Gate Open)
            hold_samples = int(duration * SR)
            strum_samples = int((strum_ms / 1000.0) * SR)
            total_hold_blocks = int(np.ceil((hold_samples + (strum_samples * len(notes))) / BLOCK_SIZE))
            
            audio_buffer = []
            current_sample_global = 0
            
            for b in range(total_hold_blocks):
                block_start = current_sample_global
                for idx, n in enumerate(notes):
                    onset = idx * strum_samples
                    # Note On Timing
                    if block_start <= onset < block_start + BLOCK_SIZE:
                        # Determine Volume
                        velocity = vol_root if idx == 0 else vol_multi
                        
                        # 1. Main Voice
                        main_pan = self._get_param_value(config, "Pan")
                        self.engine.note_on(n, velocity=velocity, detune=0.0, pan=main_pan)
                        
                        # 2. Detune Voices
                        if detune_count > 0:
                            det_vol = velocity * detune_vol_ratio
                            for _ in range(detune_count):
                                d_cent = random.uniform(-detune_range_cents, detune_range_cents)
                                d_semi = d_cent / 100.0
                                d_pan = self._get_param_value(config, "Pan")
                                self.engine.note_on(n, velocity=det_vol, detune=d_semi, pan=d_pan)

                raw_data = self.engine.generate_block()
                audio_buffer.append(raw_data)
                current_sample_global += BLOCK_SIZE
            
            # Phase 2: Release & Tail Generation
            for n in notes: self.engine.note_off(n)
            
            # --- Smart Tail Logic ---
            # Generate enough silence to capture Reverb/Delay tails.
            # User requested ~5s timeout.
            # We generate dry silence, which FX chain will fill with tails.
            
            tail_sec = 5.0 
            max_tail_blocks = int(tail_sec * SR / BLOCK_SIZE)
            
            # We just generate the full buffer. Trimming happens POST-FX.
            # Premature optimization (breaking on dry silence) kills Reverb tails.
            
            for b_tail in range(max_tail_blocks):
                raw_data = self.engine.generate_block()
                audio_buffer.append(raw_data)

            
            # 6. 保存と後処理
            full_audio = np.concatenate(audio_buffer)

            # Reshape Interleaved (..., 2) for Stereo
            if len(full_audio) % 2 != 0:
                full_audio = full_audio[:len(full_audio)-1]
            
            stereo_audio = full_audio.reshape(-1, 2)
            
            # --- POST-PROCESSING FX CHAIN ---
            from pysfx_effects import EffectsProcessor
            
            # 1. Distortion
            dist_gain = self._get_param_value(config, "DistortionGain")
            dist_tone = self._get_param_value(config, "DistortionFeed")
            dist_wet = self._get_param_value(config, "DistortionWet")
            if dist_wet > 0:
                stereo_audio[:, 0] = EffectsProcessor.apply_distortion(stereo_audio[:, 0], dist_gain, dist_tone, dist_wet)
                stereo_audio[:, 1] = EffectsProcessor.apply_distortion(stereo_audio[:, 1], dist_gain, dist_tone, dist_wet)

            # 2. Phaser
            ph_depth = self._get_param_value(config, "PhaserDepth")
            ph_speed = self._get_param_value(config, "PhaserSpeed")
            ph_wet = self._get_param_value(config, "PhaserWet")
            if ph_wet > 0:
                stereo_audio[:, 0] = EffectsProcessor.apply_phaser(stereo_audio[:, 0], ph_depth, ph_speed, ph_wet)
                stereo_audio[:, 1] = EffectsProcessor.apply_phaser(stereo_audio[:, 1], ph_depth, ph_speed, ph_wet)

            # 3. Delay
            dly_time = self._get_param_value(config, "DelayTime")
            dly_fb = self._get_param_value(config, "DelayFeedback")
            dly_wet = self._get_param_value(config, "DelayWet")
            if dly_wet > 0:
                stereo_audio[:, 0] = EffectsProcessor.apply_delay(stereo_audio[:, 0], dly_time, dly_fb, dly_wet)
                stereo_audio[:, 1] = EffectsProcessor.apply_delay(stereo_audio[:, 1], dly_time, dly_fb, dly_wet)

            # 4. Reverb
            rv_time = self._get_param_value(config, "ReverbTime")
            rv_spread = self._get_param_value(config, "ReverbSpread")
            rv_wet = self._get_param_value(config, "ReverbWet")
            if rv_wet > 0:
                stereo_audio[:, 0] = EffectsProcessor.apply_reverb(stereo_audio[:, 0], rv_time, rv_spread, rv_wet)
                stereo_audio[:, 1] = EffectsProcessor.apply_reverb(stereo_audio[:, 1], rv_time, rv_spread, rv_wet)
                
            # 5. Spread
            sp_range = self._get_param_value(config, "SpreadRange")
            sp_density = self._get_param_value(config, "SpreadDensity")
            sp_wet = self._get_param_value(config, "SpreadWet")

            # --- Smart Silence Trimming (Backward) ---
            # Trim trailing silence down to the actual signal end.
            # Threshold: 1e-5 (-100dB)
            trim_thresh = 1e-5
            
            # Check magnitude (Mono Sum or Max)
            mag = np.abs(stereo_audio)
            is_loud = np.max(mag, axis=1) > trim_thresh
            
            if np.any(is_loud):
                # Find last index where signal exists
                last_idx = np.where(is_loud)[0][-1]
                
                # Add tiny buffer (e.g. 100ms) for fade out safety? 
                # User said "Trim that 500ms" of silence. 
                # If we detected 500ms of silence, we cut it.
                # Here we just cut *all* silence after last signal.
                # Let's add 100ms safety to avoid sharp cuts on Reverb tails.
                safety_samples = int(0.1 * SR)
                cut_point = min(len(stereo_audio), last_idx + safety_samples)
                
                stereo_audio = stereo_audio[:cut_point]
            else:
                # All silence?
                pass

            # Flatten for Normalize logic need Update?
            
            # --- Fade Out Processing ---
            fade_out_val = self._get_param_value(config, "FadeOutTime")
            fade_out_curve = self._get_param_value(config, "FadeOutCurve")
            
            if fade_out_val > 0.001:
                total_samples = len(stereo_audio)
                # Fade Length: relative to total length. Max (1.0) = 50% length.
                fade_len = int(total_samples * fade_out_val * 0.5) 
                
                if fade_len > 0:
                    start_fade_idx = total_samples - fade_len
                    # Linear 0 to 1
                    lin = np.linspace(0.0, 1.0, fade_len)
                    
                    # Mapping: power = 10.0 ** ((0.5 - curve) * 2) 
                    power = 10.0 ** ((0.5 - fade_out_curve) * 2.0)
                    # Use (1-x) base for fade out
                    fade_curve = (1.0 - lin) ** power
                    
                    # Apply
                    # stereo_audio is stereo (N, 2)
                    fade_curve = fade_curve[:, np.newaxis]
                    stereo_audio[start_fade_idx:] *= fade_curve

            do_normalize = config["Normalize"]["value"]
            peak = np.max(np.abs(stereo_audio))
            
            if do_normalize and peak > 0:
                stereo_audio = (stereo_audio / peak) * 0.95
            elif peak > 1.0: 
                stereo_audio = (stereo_audio / peak) * 0.99
            
            timestamp = datetime.datetime.now().strftime("%H%M%S%f")[:7]
            
            note_str = GenerationLogic.get_note_name(root_note)
            filename = f"Quartz_{note_str}_{chord_name}_{timestamp}.wav"
            filepath = os.path.join(self.out_dir, filename)
            
            scipy.io.wavfile.write(filepath, SR, stereo_audio.astype(np.float32))
            
            # --- Excel Logging (XLSX) ---
            from pysfx_param_config import PySFXParams
            from pysfx_color_config import PySFXColors
            import openpyxl
            from openpyxl.styles import PatternFill, Alignment, Font, Border, Side
            from openpyxl.utils import get_column_letter
            
            xlsx_path = os.path.join(self.out_dir, "generation_log.xlsx")
            
            if os.path.exists(xlsx_path):
                wb = openpyxl.load_workbook(xlsx_path)
                ws = wb.active
            else:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Generation Log"
                headers = ["File Name"] + [p.name for p in PySFXParams.get_sorted_params()] + ["Date"]
                ws.append(headers)
            
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
            sorted_params = PySFXParams.get_sorted_params()
            header_row = ws[1]
            header_row[0].alignment = Alignment(horizontal='center', vertical='bottom', text_rotation=0) 
            for cell in header_row:
                 cell.alignment = Alignment(text_rotation=70, horizontal='center', vertical='bottom')
                 cell.font = Font(bold=True)
                 cell.border = thin_border
                 
            for idx_p, p in enumerate(sorted_params):
                col_idx = idx_p + 2
                cell = ws.cell(row=1, column=col_idx)
                hex_color = PySFXColors.get_excel_color(p.group)
                if hex_color:
                    cell.fill = PatternFill(start_color=hex_color, end_color=hex_color, fill_type="solid")
            
            used_params = {
                "Duration": duration,
                "NoteRange": root_note,
                "Voices": num_voices,
                "Strum": strum_ms,
                "Chord": is_chord,
                "Portament": engine_updates.get('portamento', 0),
                "AmpAttack": a * 1000,
                "AmpDecay": d * 1000,
                "AmpSustain": s * 127,
                "AmpRelease": r * 1000,
                "PitchRange": pitch_range_cents,
                "PitchType": pitch_type,
                "PitchCurve": pitch_val if (pitch_range_cents != 0 and pitch_type != 0) else 0,
                "MasterPan": engine_updates.get('master_pan', 64),
                "Pan": "Per-Voice/Random" if config["Pan"]["random"] else config["Pan"]["value"],
                "Normalize": do_normalize,
                "RouteVoiceVolume": vol_root,
                "MultiVoiceVolume": vol_multi,
                "DetuneVoice": detune_count,
                "DetuneRange": detune_range_cents,
                "DetuneVolume": detune_vol_ratio,
                "DetuneRange": detune_range_cents,
                "DetuneVolume": detune_vol_ratio,
                "OSC:A:WarpAutoRange": engine_updates['osc_warpautorange'],
                "OSC:A:DetuneAutoRange": engine_updates['osc_detuneautorange'],
                
                "OSC:B:WarpAutoRange": engine_updates['osc_b_warpautorange'],
                "OSC:B:DetuneAutoRange": engine_updates['osc_b_detuneautorange'],
                
                "LFO_P_Range": engine_updates['lfo_p_range'],
                "LFO_P_Type": engine_updates['lfo_p_type'],
                "LFO_P_Speed": engine_updates['lfo_p_speed'],
                "LFO_P_Shape": engine_updates['lfo_p_shape'],
                "LFO_V_Range": engine_updates['lfo_v_range'],
                "LFO_V_Type": engine_updates['lfo_v_type'],
                "LFO_V_Speed": engine_updates['lfo_v_speed'],
                "LFO_V_Shape": engine_updates['lfo_v_shape'],
                "LFO_Pan_Range": engine_updates['lfo_pan_range'],
                "LFO_Pan_Type": engine_updates['lfo_pan_type'],
                "LFO_Pan_Speed": engine_updates['lfo_pan_speed'],
                "LFO_Pan_Shape": engine_updates['lfo_pan_shape'],
                "DistortionGain": dist_gain,
                "DistortionFeed": dist_tone,
                "DistortionWet": dist_wet,
                "PhaserDepth": ph_depth,
                "PhaserSpeed": ph_speed,
                "PhaserWet": ph_wet,
                "ReverbTime": rv_time,
                "ReverbSpread": rv_spread,
                "ReverbWet": rv_wet,
                "DelayTime": dly_time,
                "DelayFeedback": dly_fb,
                "DelayWet": dly_wet,
                "SpreadRange": sp_range,
                "SpreadDensity": sp_density,
                "SpreadWet": sp_wet,
                "LPF_Enable": config["LPF_Enable"]["value"],
                "LPF_Cutoff": engine_updates['lpf_cutoff'],
                "LPF_AutoRange": engine_updates['lpf_autorange'],
                "HPF_Enable": config["HPF_Enable"]["value"],
                "HPF_Cutoff": engine_updates['hpf_cutoff'],
                "HPF_AutoRange": engine_updates['hpf_autorange'],
                "FadeOutTime": fade_out_val,
                "FadeOutCurve": fade_out_curve
            }

            row_data = [filename]
            for p in sorted_params:
                val = used_params.get(p.name, "")
                if isinstance(val, (float, np.floating)) and isinstance(val, (int, float)):
                     val = round(val, 2)
                row_data.append(val)
                
            row_data.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            ws.append(row_data)
            current_row = ws.max_row
            for cell in ws[current_row]:
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center')
            
            ws.freeze_panes = "B2"
            ws.auto_filter.ref = ws.dimensions
            ws.column_dimensions['A'].width = 30
            ws.column_dimensions[get_column_letter(len(row_data))].width = 20
            
            try:
                wb.save(xlsx_path)
                print(f"[{p_idx+1}/{num_files}] {filename} (Dur:{duration:.2f}s) -> Logged to XLSX")
            except PermissionError:
                print(f"[{p_idx+1}/{num_files}] WARNING: Excel Open! Log skipped. Close 'generation_log.xlsx'.")
            except Exception as e:
                print(f"[{p_idx+1}/{num_files}] ERROR: Excel: {e}")