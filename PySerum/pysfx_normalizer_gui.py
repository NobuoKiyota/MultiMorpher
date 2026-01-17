import customtkinter as ctk
import os
import threading
from tkinter import filedialog
from tkinterdnd2 import TkinterDnD, DND_ALL
import soundfile as sf
import numpy as np
import scipy.signal
import json

class NormalizerGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("Quartz Normalizer - Auto Trim & Stretch")
        self.geometry("400x300")
        
        self.settings_file = "normalizer_settings.json"
        self._init_ui()
        self.load_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def _init_ui(self):
        # 1. Input Area
        frame_in = ctk.CTkFrame(self)
        frame_in.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame_in, text="Input File/Folder:").pack(side="left", padx=5)
        self.ent_input = ctk.CTkEntry(frame_in, width=300)
        self.ent_input.pack(side="left", padx=5)
        self.ent_input.drop_target_register(DND_ALL)
        self.ent_input.dnd_bind('<<Drop>>', self.on_drop)
        ctk.CTkButton(frame_in, text="Browse", width=60, command=self.browse_input).pack(side="left", padx=5)
        
        # 2. Parameters
        frame_param = ctk.CTkFrame(self)
        frame_param.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Target Duration
        self._add_range_param(frame_param, "TargetTime", 0.5, 2.0, "Time Stretch Target (Range Sec)")
        
        # Attack / Release
        self._add_range_param(frame_param, "AttackRate", 0.0, 1.0, "Attack Env Rate (Max 20%)")
        self._add_range_param(frame_param, "ReleaseRate", 0.0, 1.0, "Release Env Rate (Max 20%)")

        # 3. Actions
        self.btn_run = ctk.CTkButton(self, text="Execute Normalization", 
                                     font=("Arial", 16, "bold"), fg_color="#e04f5f", height=50,
                                     command=self.start_process)
        self.btn_run.pack(fill="x", padx=20, pady=20)
        
        self.lbl_status = ctk.CTkLabel(self, text="Ready.")
        self.lbl_status.pack(pady=5)

    def _add_range_param(self, parent, name, default_min, default_max, label):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5)
        ctk.CTkLabel(frame, text=label, width=180, anchor="w").pack(side="left", padx=5)
        
        v_min = ctk.StringVar(value=str(default_min))
        v_max = ctk.StringVar(value=str(default_max))
        
        ctk.CTkEntry(frame, textvariable=v_min, width=60).pack(side="left", padx=5)
        ctk.CTkLabel(frame, text="~").pack(side="left")
        ctk.CTkEntry(frame, textvariable=v_max, width=60).pack(side="left", padx=5)
        
        if not hasattr(self, "controls"): self.controls = {}
        self.controls[name + "_Min"] = v_min
        self.controls[name + "_Max"] = v_max

    def on_drop(self, event):
        path = event.data
        if path.startswith("{") and path.endswith("}"): path = path[1:-1]
        self.ent_input.delete(0, "end")
        self.ent_input.insert(0, path)
        
    def browse_input(self):
        p = filedialog.askdirectory() # Or file? user said file or folder
        if p:
            self.ent_input.delete(0, "end")
            self.ent_input.insert(0, p)

    def start_process(self):
        inp = self.ent_input.get()
        if not os.path.exists(inp):
            self.lbl_status.configure(text="Invalid Input", text_color="red")
            return
            
        params = {k: float(v.get()) for k, v in self.controls.items()}
        
        self.btn_run.configure(state="disabled")
        self.lbl_status.configure(text="Processing...", text_color="yellow")
        self.save_settings()
        
        threading.Thread(target=lambda: self.process_thread(inp, params)).start()

    def process_thread(self, inp, params):
        import random
        # Collect
        targets = []
        if os.path.isfile(inp):
            targets.append(inp)
            out_dir = os.path.join(os.path.dirname(inp), "Normalized")
        else:
            out_dir = os.path.join(inp, "Normalized")
            exts = ('.wav', '.aiff', '.flac', '.ogg', '.mp3')
            targets = [os.path.join(inp, f) for f in os.listdir(inp) if f.lower().endswith(exts)]
            
        if not os.path.exists(out_dir): os.makedirs(out_dir)
        
        count = 0
        for fpath in targets:
            try:
                # 1. Load & Trim Silence
                data, sr = sf.read(fpath, dtype='float32')
                if len(data.shape) == 1: data = np.stack([data, data], axis=1) # Stereo
                
                # Simple Energy Trim
                # 30dB threshold?
                mag = np.abs(data).mean(axis=1) # Average channels
                mask = mag > 0.001 # approx -60dB
                
                if not np.any(mask): continue # Silent file
                
                # Find valid range
                coords = np.where(mask)[0]
                start, end = coords[0], coords[-1]
                trimmed = data[start:end+1]
                
                # 2. Stretch to Target Range
                dur_min = params["TargetTime_Min"]
                dur_max = params["TargetTime_Max"]
                target_dur = random.uniform(dur_min, dur_max)
                target_len = int(target_dur * sr)
                
                # Resample (Stretch)
                # scipy.signal.resample is Fourier based (High Quality but slow for very long files).
                # Linear interp is faster. Let's use linear for safety/speed.
                # Or scipy.signal.resample_poly?
                # Let's use simple linear interpolation logic (numpy interp)
                curr_len = len(trimmed)
                if curr_len < 10: continue
                
                # Time indices
                src_x = np.linspace(0, 1, curr_len)
                dst_x = np.linspace(0, 1, target_len)
                
                # Interp each channel
                stretched = np.zeros((target_len, 2), dtype=np.float32)
                for ch in range(2):
                    stretched[:, ch] = np.interp(dst_x, src_x, trimmed[:, ch])
                
                # 3. Envelope
                # Attack: 0.0-1.0 (Rate of Max 20%)
                atk_rate = random.uniform(params["AttackRate_Min"], params["AttackRate_Max"])
                rel_rate = random.uniform(params["ReleaseRate_Min"], params["ReleaseRate_Max"])
                
                # 20% of Target Len
                max_env_len = target_len * 0.2
                
                atk_len = int(max_env_len * atk_rate)
                rel_len = int(max_env_len * rel_rate)
                
                # Apply Attack
                if atk_len > 0:
                    curve = np.linspace(0.0, 1.0, atk_len)
                    # Curve shape? User didn't specify. Linear.
                    stretched[:atk_len] *= curve[:, np.newaxis]
                    
                # Apply Release
                if rel_len > 0:
                    curve = np.linspace(1.0, 0.0, rel_len)
                    stretched[-rel_len:] *= curve[:, np.newaxis]
                
                # Save
                pad_num = str(count+1).zfill(3)
                base = os.path.splitext(os.path.basename(fpath))[0]
                out_name = f"{base}_Norm_{pad_num}.wav"
                sf.write(os.path.join(out_dir, out_name), stretched, sr)
                
                count += 1
                
            except Exception as e:
                print(f"Error {fpath}: {e}")
                
        self.after(0, lambda: self.finish(count))

    def finish(self, count):
        self.lbl_status.configure(text=f"Completed {count} files!", text_color="green")
        self.btn_run.configure(state="normal")
        
    def on_close(self):
        self.save_settings()
        self.destroy()

    def save_settings(self):
        data = {"input_path": self.ent_input.get()}
        for k, v in self.controls.items():data[k] = v.get()
        try:
            with open(self.settings_file, "w") as f: json.dump(data, f)
        except: pass
        
    def load_settings(self):
        if not os.path.exists(self.settings_file): return
        try:
            with open(self.settings_file, "r") as f:
                d = json.load(f)
                if "input_path" in d: 
                    self.ent_input.delete(0, "end")
                    self.ent_input.insert(0, d["input_path"])
                for k,v in d.items():
                    if k in self.controls: self.controls[k].set(v)
        except: pass

if __name__ == "__main__":
    app = NormalizerGUI()
    app.mainloop()
