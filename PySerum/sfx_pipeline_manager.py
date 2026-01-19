import os
import shutil
import glob
import random
import time
import datetime
import traceback
import openpyxl

# Import Engines
from pysfx_factory import PyQuartzFactory
from pysfx_transformer_engine_tracked import QuartzTransformerEngineTracked
from pysfx_masker_engine import QuartzMaskerEngine
from pysfx_slicer_engine import QuartzSlicerEngine
from pysfx_normalizer_engine import QuartzNormalizerEngine
from pysfx_logger import SFXLogger

class SFXPipeline:
    def __init__(self, workspace_root=None):
        if workspace_root is None:
            workspace_root = os.path.dirname(os.path.abspath(__file__))
            
        self.root_dir = os.path.join(workspace_root, "Pipeline_Output")
        self.factory = PyQuartzFactory()
        self.transformer = QuartzTransformerEngineTracked()
        self.masker = QuartzMaskerEngine()
        self.slicer = QuartzSlicerEngine()
        self.normalizer = QuartzNormalizerEngine()
        
    def run_pipeline(self, batch_name, total_count=100, source_count=None, factory_settings=None):
        """
        Full Pipeline.
        source_count: Explicit number of Step 1 files. If None, calculated from total_count.
        factory_settings: Dict of param overrides for Factory (e.g. {'Duration': 1.0, 'VoiceCount': 1})
        """
        
        # Setup Directories
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if not batch_name: batch_name = f"Batch_{timestamp}"
        
        base_dir = os.path.join(self.root_dir, batch_name)
        dir_step1 = os.path.join(base_dir, "01_Factory_Raw")
        dir_step2 = os.path.join(base_dir, "02_Transformed")
        dir_step3 = os.path.join(base_dir, "03_Masked")
        dir_step4 = os.path.join(base_dir, "04_Sliced")
        dir_step5 = os.path.join(base_dir, "05_Final_Normalized")
        
        for d in [dir_step1, dir_step2, dir_step3, dir_step4, dir_step5]:
            os.makedirs(d, exist_ok=True)
            
        print(f"=== SFX Pipeline Started: {batch_name} (Overview Target: {total_count}) ===")
        
        t_start_total = time.time()
        step_times = {}

        # --- Step 1: Factory Generation ---
        # Scale input files for variance
        if source_count is None:
            count_step1 = max(10, int(total_count * 0.2)) 
            if count_step1 > 200: count_step1 = 200 # Cap base material if huge
        else:
            count_step1 = int(source_count)
        
        print(f"--- Step 1: Factory Generation ({count_step1}) ---")
        t_s1 = time.time()
        
        self.factory.out_dir = dir_step1
        config = self.factory.get_random_config()
        
        # Apply Overrides
        if factory_settings:
            for k, v in factory_settings.items():
                if k in config:
                    config[k]["value"] = v
                    print(f"  > Override {k}: {v}")
        
        self.factory.run_advanced_batch(config, num_files=count_step1)
        
        step_times["Step 1 (Factory)"] = time.time() - t_s1
        
        # Load Step 1 Parameters into Memory
        # Map: Filename -> ParamDict
        step1_log_path = os.path.join(dir_step1, "generation_log.xlsx")
        factory_params_map = {}
        if os.path.exists(step1_log_path):
            wb = openpyxl.load_workbook(step1_log_path, data_only=True)
            ws = wb.active
            headers = [c.value for c in ws[1]]
            # Filename is Col 2 (Index 1) usually. "File Name"
            name_idx = -1
            if "File Name" in headers: name_idx = headers.index("File Name")
            
            if name_idx >= 0:
                for row in ws.iter_rows(min_row=2, values_only=True):
                    fname = row[name_idx]
                    if fname:
                        # Capture all params
                        p_dict = {}
                        for i, h in enumerate(headers):
                            if i != name_idx and h != "Score" and h != "Date":
                                p_dict[f"Fac_{h}"] = row[i] # Prefix Factory
                        factory_params_map[fname] = p_dict

        # --- Step 2: Transformer ---
        print(f"--- Step 2: Transformer ({total_count}) ---")
        t_s2 = time.time()
        
        t_params = {
            "Iteration": total_count,
            "MixCount_Rnd": True, "MixCount_Min": 1, "MixCount_Max": 2, # Keep low for clarity
            "MorphStartOffset_Rnd": True, "MorphStartOffset_Min": 0.0, "MorphStartOffset_Max": 0.3,
            "ReverseProb": 0.3, "ScratchProb": 0.3, "StretchProb": 0.3, "FlutterProb": 0.2,
        }
        
        # Returns list of {output_file, source_files, params}
        step2_logs = self.transformer.process_tracked(dir_step1, dir_step2, t_params, progress_cb=lambda i,t: print(f"Trans {i}/{t}", end="\r"))
        print("")
        
        step_times["Step 2 (Transformer)"] = time.time() - t_s2
        
        # --- Step 3: Masker ---
        print(f"--- Step 3: Masker ---")
        t_s3 = time.time()
        m_params = {
            "NoiseType": "Random",
            "MaskAmount_Rnd": True, "MaskAmount_Min": 0.1, "MaskAmount_Max": 0.4,
            "FadeLen": 0.05
        }
        # Masker is 1:1. We can just scan output and deduce input if naming convention is reliable.
        # But Masker engine appends suffix.
        # Let's run it.
        self.masker.process(dir_step2, dir_step3, m_params, progress_cb=lambda i,t: print(f"Mask {i}/{t}", end="\r"))
        print("")
        
        step_times["Step 3 (Masker)"] = time.time() - t_s3
        
        # --- Step 4: Slicer ---
        print(f"--- Step 4: Slicer ---")
        t_s4 = time.time()
        
        s_params = {
            "threshold_db": -50,
            "min_interval_ms": 500,
            "min_duration_ms": 500, 
            "pad_ms": 100
        }
        self.slicer.process_folder(dir_step3, dir_step4, s_params, progress_cb=lambda i,t: print(f"Slice {i}/{t}", end="\r"))
        print("")
        
        step_times["Step 4 (Slicer)"] = time.time() - t_s4
        
        # --- Step 5: Normalizer ---
        print(f"--- Step 5: Normalizer ---")
        t_s5 = time.time()
        
        n_params = {
            "target_time_min": 1.0, "target_time_max": 5.0,
            "attack_rate_min": 0.01, "attack_rate_max": 0.05,
            "release_rate_min": 0.05, "release_rate_max": 0.3
        }
        self.normalizer.process_folder(dir_step4, dir_step5, n_params, progress_cb=lambda i,t: print(f"Norm {i}/{t}", end="\r"))
        
        step_times["Step 5 (Normalizer)"] = time.time() - t_s5
        print("\n\n=== Pipeline Complete ===")
        t_end_step = time.time()
        step_times["Step 5: Normalizer"] = t_end_step - t_s5
        
        # --- Trace & Aggregate Logs ---
        t_start_step = time.time()
        # Goal: For every file in Final (Stef 5), trace back to Step 1 and gather params.
        
        final_files = glob.glob(os.path.join(dir_step5, "*.wav"))
        print(f"Generating Final Manifest for {len(final_files)} files...")
        
        # Manifest Logger needs to support Dynamic Columns (Factory + Trans + Mask ...)
        # We start with headers from Factory + Extra
        
        # Helper to trace lineage
        # Final -> Sliced -> Masked -> Transformed -> Sources
        
        # Step 4/5/3 naming conventions are usually appended.
        # Norm: X_Norm.wav -> X.wav (Step 4 output)
        # Slice: Y_01.wav -> Y.wav (Step 3 output) or just Y.wav if no split
        # Mask: Z_White.wav -> Z.wav (Step 2 output)
        # Trans: Tr_... (Step 2 log has this)
        
        # Build Lookup for Step 2 Log
        # OutFile -> {Sources, Params}
        step2_map = {log['output_file']: log for log in step2_logs}
        
        final_logger = SFXLogger(os.path.join(dir_step5, "final_manifest.xlsx"))
        
        # We need to force-add headers for dynamic params?
        # SFXLogger currently uses PySFXParams fixed list.
        # We should modify/extend SFXLogger or just inject columns using openpyxl directly.
        # Let's bypass SFXLogger param logic and write row directly for maximum flexibility.
        
        # 1. Collect all data
        all_rows = []
        all_keys = set()
        
        for fpath in final_files:
            fname = os.path.basename(fpath)
            
            # Unwind Normalizer (_Norm)
            # "Name_Norm.wav" -> "Name.wav"
            # Watch out for complex names
            
            s4_name = fname.replace("_Norm.wav", ".wav")
            
            # Unwind Slicer (_01, _02...)
            # "Name_01.wav" -> "Name.wav"
            # Regex or rsplit underbar?
            # Masker adds "_White.wav", "_Pink.wav".
            # Slicer adds "_01.wav".
            # It's safest to look for files in Step 3 that match prefix.
            
            # Simple Heuristic De-suffixing
            # Remove digits at end?
            # "Tr_0_Mix_123_White_01_Norm.wav"
            
            base = fname
            if base.endswith("_Norm.wav"): base = base[:-9] # Remove _Norm
            # Check if ends with _\d\d
            import re
            m = re.search(r'_(\d{2})$', base)
            if m:
                base = base[:-3] # Remove _01
                
            # Now "Tr_0_Mix_123_White" or "Tr_0_Mix_123_White_Pink" (if multi mask?)
            # Masker adds "_[Type]"
            # Types: White, Pink, Brown, Random
            masks = ["_White", "_Pink", "_Brown"]
            found_mask = ""
            for mk in masks:
                if base.endswith(mk):
                    base = base[:-len(mk)]
                    found_mask = mk[1:] # "White"
                    break
            
            # Now "Tr_0_Mix_123" -> Step 2 Output
            # Check in Step 2 Map
            # Need extension? Step 2 logs include extension.
            # base is without extension likely? No, we stripped extension at Slicer step?
            # Slicer input was .wav.
            # wait, `fname` is full filename.
            # `s4_name` replaced .wav.
            # Let's be careful. Step 2 log keys have .wav.
            
            s2_candidate = base + ".wav"
            
            row_data = {"File Name": fname}
            
            if s2_candidate in step2_map:
                s2_data = step2_map[s2_candidate]
                
                # Transformer Params
                for k, v in s2_data['params'].items():
                    row_data[f"Tr_{k}"] = v
                
                # Sources
                srcs = s2_data['source_files']
                # Pick 1st Source for Factory Params inheritance
                if srcs:
                    src_main = srcs[0]
                    if src_main in factory_params_map:
                        f_params = factory_params_map[src_main]
                        row_data.update(f_params)
            
            # Masker Params (Inferred)
            if found_mask:
                row_data["Mask_Type"] = found_mask
                
            all_rows.append(row_data)
            all_keys.update(row_data.keys())
            
        # 2. Write XLS
        # Sort Keys: File Name, Score, Fac_..., Tr_..., others
        
        # Priority Headers
        sorted_keys = ["Score", "File Name"]
        # Factory keys
        fac_keys = sorted([k for k in all_keys if k.startswith("Fac_")])
        tr_keys = sorted([k for k in all_keys if k.startswith("Tr_")])
        other_keys = sorted([k for k in all_keys if k not in sorted_keys and k not in fac_keys and k not in tr_keys])
        
        headers = sorted_keys + fac_keys + tr_keys + other_keys
        
        # Re-init Logger Sheet
        final_logger.ws.delete_rows(1, final_logger.ws.max_row)
        final_logger.ws.append(headers)
        
        for r in all_rows:
            vals = []
            for h in headers:
                if h == "Score": vals.append("")
                else: vals.append(r.get(h, ""))
            final_logger.ws.append(vals)
            
        final_logger.save()
        print(f"Manifest Saved: {os.path.join(dir_step5, 'final_manifest.xlsx')}")
        t_end_step = time.time()
        step_times["Step 6: Log Aggregation"] = t_end_step - t_start_step

        # --- Performance Report ---
        t_end_total = time.time()
        dur_total = t_end_total - t_start_total
        
        final_count = len(final_files)
        avg_per_item = dur_total / final_count if final_count > 0 else 0
        
        report_path = os.path.join(base_dir, "performance_report.txt")
        with open(report_path, "w", encoding='utf-8') as f:
            f.write(f"=== SFX Generation Performance Report ===\n")
            f.write(f"Batch Name: {batch_name}\n")
            f.write(f"Date: {datetime.datetime.now()}\n")
            f.write(f"Total Target: {total_count}\n")
            f.write(f"Final Count: {final_count}\n")
            f.write(f"Total Duration: {dur_total:.2f} seconds ({dur_total/60:.2f} minutes)\n")
            f.write(f"Average Time Per File: {avg_per_item:.2f} seconds\n\n")
            
            f.write("--- Step Details ---\n")
            for step_key, dur in step_times.items():
                f.write(f"{step_key}: {dur:.2f} seconds\n")
            
            f.write("\n--- Efficiency Estimates ---\n")
            f.write(f"Estimated time for 1000 files: {(avg_per_item * 1000) / 60:.2f} minutes\n")

        print(f"Performance Report Saved: {report_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10, help="Total target count")
    parser.add_argument("--name", type=str, default="", help="Batch Name")
    args = parser.parse_args()
    
    pipeline = SFXPipeline()
    pipeline.run_pipeline(args.name, args.count)

