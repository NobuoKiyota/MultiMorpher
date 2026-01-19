
import os
import sys
import time

# Add current directory to path so imports work
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from sfx_pipeline_manager import SFXPipeline

def main():
    print("Initializing Home Run Batch...", flush=True)
    pipeline = SFXPipeline()
    
    # "Heavy" Complexity Overrides
    overrides = {
         "Duration": 2.5,
         "VoiceCount": 3.0,
         "DetuneVoice": 2.0,
         "Chord": 1.0
    }
    
    batch_name = "Home_Run_001"
    total_opt = 1000
    source_opt = 50
    
    print(f"Starting Pipeline: {batch_name}", flush=True)
    print(f"Target: {total_opt}, Source: {source_opt}", flush=True)
    print(f"Complexity: Heavy {overrides}", flush=True)
    
    try:
        pipeline.run_pipeline(
            batch_name=batch_name, 
            total_count=total_opt, 
            source_count=source_opt, 
            factory_settings=overrides
        )
        print("Batch Complete.", flush=True)
    except Exception as e:
        print(f"Batch Failed: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
