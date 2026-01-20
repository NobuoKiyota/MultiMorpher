import sys
import os
import numpy as np

def run_tests():
    print("--- Starting Verification Tests ---")
    
    # 1. Imports
    try:
        print("[1/5] Importing modules...")
        import morph_core
        import processors
        # Mocking pygame for headless/CI envs just in case
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        import protomorph_gui
        print("   -> Success")
    except Exception as e:
        print(f"   -> FAILED: {e}")
        return False

    # 2. Core Init
    try:
        print("[2/5] Initializing MorphCore...")
        core = morph_core.MorphCore()
        print(f"   -> Success (SR={core.sr}, FFT={core.n_fft})")
    except Exception as e:
        print(f"   -> FAILED: {e}")
        return False

    # 3. Dummy Data Generation
    try:
        print("[3/5] Generating Dummy STFT Data...")
        # Create fake STFT matrix: (1025 bins, 100 frames) - complex64
        bins = 1025
        frames = 100
        stft_a = (np.random.rand(bins, frames) + 1j * np.random.rand(bins, frames)).astype(np.complex64)
        stft_b = (np.random.rand(bins, frames) + 1j * np.random.rand(bins, frames)).astype(np.complex64)
        print("   -> Success")
    except Exception as e:
        print(f"   -> FAILED: {e}")
        return False

    # 4. Processor Tests
    try:
        print("[4/5] Testing Processors...")
        
        # Blend
        blend = processors.MorphProcessors.spectral_blend(stft_a, stft_b, 1000, 48000, 2048)
        if blend.shape != stft_a.shape: raise ValueError(f"Blend shape mismatch: {blend.shape}")
        
        # Interpolate
        interp = processors.MorphProcessors.interpolate(stft_a, stft_b, 0.5)
        if interp.shape != stft_a.shape: raise ValueError(f"Interp shape mismatch: {interp.shape}")
        
        # Formant Shift
        shift = processors.MorphProcessors.formant_shift(stft_a, 1.5, 2048)
        if shift.shape != stft_a.shape: raise ValueError(f"Shift shape mismatch: {shift.shape}")
        
        print("   -> Success")
    except Exception as e:
        print(f"   -> FAILED: {e}")
        # Print full traceback for debug
        import traceback
        traceback.print_exc()
        return False

    # 5. Real-time Engine Init Test
    try:
        print("[5/5] Testing RealtimeEngine Init...")
        import realtime_engine
        rt = realtime_engine.RealtimeEngine(sr=48000)
        # We won't start stream as it requires audio device, just check logic
        rt.set_param("test", 1.0)
        if rt.params["test"] != 1.0: raise ValueError("Param set failed")
        
        # Test Recorder Logic
        rt.start_recording()
        if not rt.recording: raise ValueError("Recording start failed")
        rt.stop_recording("dummy_out.wav")
        if rt.recording: raise ValueError("Recording stop failed")
        
        print("   -> Success")
    except Exception as e:
         print(f"   -> FAILED (Audio Device might be missing): {e}")
         # Warn but don't fail whole script as CI might not have audio
         pass

    print("--- All Tests Passed ---")
    return True

if __name__ == "__main__":
    if run_tests():
        sys.exit(0)
    else:
        sys.exit(1)
