
# UI Sound Models Definition for Quartz UI Extractor

UI_MODELS = {
    "CURSOR_MOVE": {
        "name": "Cursor Move",
        "desc": "Short, sharp blip for navigation",
        "duration_range_ms": (30, 200),
        "freq_range_hz": (400, 5000),
        "attack_ms": 5,
        "features": {
            "type": "spectral_point",  # Point source-like
            "target_freq_peak": 1000.0,
            "max_reverb_tail_ms": 10
        }
    },
    
    "DECISION": {
        "name": "Decision / Confirm",
        "desc": "Positive, harmonious confirmation sound",
        "duration_range_ms": (200, 1000),
        "features": {
            "harmony": "Major Triad", # Root, M3, P5
            "spectral_centroid_min": 1500.0,
            "timbre": "Bright"
        },
        "processing": {
            "add_release_ms": 300,
            "reverb": {
                "wet": 0.20,
                "time_s": 0.5, # Default generic time
                "spread": 0.5
            }
        }
    },
    
    "CANCEL": {
        "name": "Cancel / Back",
        "desc": "Descending pitch for rejection or back",
        "duration_range_ms": (100, 400),
        "freq_peak_max": 2000.0,
        "features": {
            "pitch_trajectory": "Rapid Fall",
            "pitch_drop_ratio": (0.2, 0.3), # Drops TO 20-30% of start freq
            "drop_window_ms": 100
        },
        "processing": {
            "fade_in_ms": 50,
            "fade_out_ms": 100
        }
    }
}
