
import numpy as np
import soundfile as sf
import os

sr = 48000

def gen_sine(freq, dur_ms, amp=0.5):
    t = np.linspace(0, dur_ms/1000, int(dur_ms/1000*sr))
    return amp * np.sin(2*np.pi*freq*t)

def gen_sweep(f_start, f_end, dur_ms, amp=0.5):
    t = np.linspace(0, dur_ms/1000, int(dur_ms/1000*sr))
    phase = 2*np.pi * (f_start * t + 0.5 * (f_end - f_start) * t**2 / (dur_ms/1000))
    return amp * np.sin(phase)

# 1. Cursor: 1000Hz, 50ms, sharp attack
cursor = gen_sine(1000, 50)
cursor[:100] *= np.linspace(0, 1, 100) # Fast attack
cursor[100:] *= np.linspace(1, 0, len(cursor)-100) # Decay
sf.write("synthetic_cursor.wav", cursor, sr)

# 2. Decision: C Major (261, 329, 392) + Harmonics for brightness, 250ms
t = np.linspace(0, 0.25, int(0.25*sr))
c_maj = np.sin(2*np.pi*261.6*t) + np.sin(2*np.pi*329.6*t) + np.sin(2*np.pi*392.0*t)
# Add high harmonic for brightness/centroid
c_maj += 0.5 * np.sin(2*np.pi*2000*t) 
c_maj *= 0.3
sf.write("synthetic_decision.wav", c_maj, sr)

# 3. Cancel: Fall 2000 -> 500 (Ratio 0.25), 150ms
cancel = gen_sweep(2000, 500, 150)
sf.write("synthetic_cancel.wav", cancel, sr)

print("Generated synthetic test files.")
