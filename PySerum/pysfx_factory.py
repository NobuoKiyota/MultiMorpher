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

    def _get_param_value(self, config, name):
        """Random設定を考慮して値を取得するヘルパー"""
        node = config[name]
        if node.get("random"):
            return random.uniform(float(node["min"]), float(node["max"]))
        return float(node["value"])

    def run_advanced_batch(self, config, num_files=10):
        print(f"--- PyQuartz SFX Factory Production: {num_files} files ---")
        
        for i in range(num_files):
            # 1. 各種パラメータの決定 (Random設定対応)
            duration = self._get_param_value(config, "Duration")
            root_note = int(self._get_param_value(config, "NoteRange"))
            num_voices = int(self._get_param_value(config, "Voices"))
            strum_ms = self._get_param_value(config, "Strum")
            
            # 2. エンジン内部パラメータの同期
            # GUI上の 'PitchRange' などをエンジンの 'semi' 等に変換して適用
            engine_updates = {
                'vol': 0.8, # 必要に応じてGUI項目追加
                'semi': 0,   # 基本ピッチ
                'cutoff': 20000, # フィルタ未実装なら固定、あればGUIから取得
                'dist': 0,
                'filter_en': True,
                'filter_en': True,
                'portamento': self._get_param_value(config, "Portament"),
                'master_pan': self._get_param_value(config, "MasterPan")
            }
            self.engine.update_params(engine_updates)
            
            # --- Pitch Automation Setup ---
            pitch_range_cents = self._get_param_value(config, "PitchRange")
            if pitch_range_cents != 0:
                pitch_curve = int(self._get_param_value(config, "PitchCurve"))
                # Using 16 points for smooth envelope
                points = GenerationLogic.get_pitch_curve(pitch_range_cents, 16)
                # Scale points to Semitones
                range_semis = pitch_range_cents / 100.0
                scaled_points = [(t, v * range_semis) for t, v in points]
                from pysfx_dsp import AutomationLane
                auto = AutomationLane(duration)
                auto.points = scaled_points
                self.engine.automations['pitch'] = auto
            else:
                if 'pitch' in self.engine.automations: del self.engine.automations['pitch']

            # 3. ADSRの設定
            a = self._get_param_value(config, "AmpAttack") / 1000.0
            d = self._get_param_value(config, "AmpDecay") / 1000.0
            s = self._get_param_value(config, "AmpSustain") / 127.0
            r = self._get_param_value(config, "AmpRelease") / 1000.0
            self.engine.set_adsr(a, d, s, r)

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
            
            # Keep track of active notes to turn them off later
            # Actually engine handles note_off by note number. 
            # If we limit voices (polyphony), detunes might steal.
            # We increased voices to 64.
            
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
                                # Detune spread +/- range
                                d_cent = random.uniform(-detune_range_cents, detune_range_cents)
                                d_semi = d_cent / 100.0
                                
                                # Detune Voices also get Pan (Random if Pan is Random)
                                d_pan = self._get_param_value(config, "Pan")
                                self.engine.note_on(n, velocity=det_vol, detune=d_semi, pan=d_pan)

                raw_data = self.engine.generate_block()
                audio_buffer.append(raw_data)
                current_sample_global += BLOCK_SIZE
            
            # Phase 2: Release (Note Off & Tail)
            # Since multiple voices share the same note number (detunes),
            # engine.note_off(n) iterates ALL voices and releases ANY with matching note number.
            # So one call per note n is enough to kill main + all detunes for that note.
            for n in notes: self.engine.note_off(n)
            
            # リリース時間を計算 
            # 余裕を見て 1.5倍し、無音検知で早期終了
            release_sec = r 
            max_tail_blocks = int(np.ceil((release_sec * 3.0 * SR) / BLOCK_SIZE)) + 10 # 3倍 + margin
            
            silence_thresh = 1e-5
            
            for b in range(max_tail_blocks):
                raw_data = self.engine.generate_block()
                audio_buffer.append(raw_data)
                
                # Check silence (Peak of block)
                if np.max(np.abs(raw_data)) < silence_thresh:
                    # Ensure minimal tail length? No, silence is silence.
                    break
            
            # 6. 保存と後処理
            full_audio = np.concatenate(audio_buffer)
            
            # Normalize Logic
            do_normalize = config["Normalize"]["value"]
            peak = np.max(np.abs(full_audio))
            
            if do_normalize and peak > 0:
                full_audio = (full_audio / peak) * 0.95
            elif peak > 1.0: # Clip protection even if not normalizing
                full_audio = (full_audio / peak) * 0.99
            
            timestamp = datetime.datetime.now().strftime("%H%M%S%f")[:7]
            
            # Formatting Filename: Quartz_Cn3_Maj7_Timestamp.wav
            note_str = GenerationLogic.get_note_name(root_note)
            filename = f"Quartz_{note_str}_{chord_name}_{timestamp}.wav"
            filepath = os.path.join(self.out_dir, filename)
            
            # Reshape Interleaved (..., 2) for Stereo
            # Engine returns interleaved flat array
            if len(full_audio) % 2 != 0:
                # Should not happen with block size, but safer to trim
                full_audio = full_audio[:len(full_audio)-1]
            
            stereo_audio = full_audio.reshape(-1, 2)
            
            scipy.io.wavfile.write(filepath, SR, stereo_audio.astype(np.float32))
            
            # --- Excel Logging (XLSX) ---
            from pysfx_param_config import PySFXParams
            from pysfx_color_config import PySFXColors
            import openpyxl
            from openpyxl.styles import PatternFill, Alignment, Font, Border, Side
            from openpyxl.utils import get_column_letter
            
            xlsx_path = os.path.join(self.out_dir, "generation_log.xlsx")
            
            # --- Load or Create Workbook ---
            if os.path.exists(xlsx_path):
                wb = openpyxl.load_workbook(xlsx_path)
                ws = wb.active
            else:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Generation Log"
                
                # --- Create Headers ---
                headers = ["File Name"] + [p.name for p in PySFXParams.get_sorted_params()] + ["Date"]
                ws.append(headers)
            
            # --- Styling Constants ---
            thin_border = Border(left=Side(style='thin'), 
                                 right=Side(style='thin'), 
                                 top=Side(style='thin'), 
                                 bottom=Side(style='thin'))
                                 
            # --- Update Header Styles (Always, to fix existing) ---
            sorted_params = PySFXParams.get_sorted_params()
            header_row = ws[1]
            
            # 1. File Name Header
            header_row[0].alignment = Alignment(horizontal='center', vertical='bottom', text_rotation=0) # No rotation for File Name? 
            # User said: "1行目をカラムとして文字角度を70度" - implies all columns? 
            # Usually File Name is long, better flat? Or rotated too? Let's rotate all for consistency as requested.
            for cell in header_row:
                 cell.alignment = Alignment(text_rotation=70, horizontal='center', vertical='bottom')
                 cell.font = Font(bold=True)
                 cell.border = thin_border
                 
            # 2. Color Headers (Cols 2..N) based on Group
            # Col 1: File Name (No Group Color or specific?)
            # Col 2..N: Params
            for i, p in enumerate(sorted_params):
                col_idx = i + 2
                cell = ws.cell(row=1, column=col_idx)
                hex_color = PySFXColors.get_excel_color(p.group)
                if hex_color:
                    cell.fill = PatternFill(start_color=hex_color, end_color=hex_color, fill_type="solid")
            
            # --- Prepare Data ---
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
                "PitchCurve": pitch_curve if pitch_range_cents != 0 else 0,
                "MasterPan": engine_updates.get('master_pan', 64),
                "Pan": "Per-Voice/Random" if config["Pan"]["random"] else config["Pan"]["value"],
                "Normalize": do_normalize,
                "RouteVoiceVolume": vol_root,
                "MultiVoiceVolume": vol_multi,
                "DetuneVoice": detune_count,
                "DetuneRange": detune_range_cents,
                "DetuneVolume": detune_vol_ratio
            }

            row_data = [filename]
            
            for p in sorted_params:
                val = used_params.get(p.name, "")
                if isinstance(val, (float, np.floating)) and isinstance(val, (int, float)):
                     val = round(val, 2)
                row_data.append(val)
                
            row_data.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            
            # --- Append Row ---
            ws.append(row_data)
            current_row = ws.max_row
            
            # --- Apply Borders (Grid) to Data Row ---
            # And NO Color
            for cell in ws[current_row]:
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center')
            
            # --- Freezing & Filtering ---
            ws.freeze_panes = "B2" # Freeze Row 1 and Column A (File Name)
            ws.auto_filter.ref = ws.dimensions # Enable Autofilter for full range
            
            # Auto-fit Column A width
            ws.column_dimensions['A'].width = 30
            ws.column_dimensions[get_column_letter(len(row_data))].width = 20 # Date
            
            try:
                wb.save(xlsx_path)
                print(f"[{i+1}/{num_files}] {filename} (Dur:{duration:.2f}s) -> Logged to XLSX")
            except PermissionError:
                print(f"[{i+1}/{num_files}] WARNING: Excel Open! Log skipped for {filename}. Close 'generation_log.xlsx'.")
            except Exception as e:
                print(f"[{i+1}/{num_files}] ERROR: Excel save failed: {e}")