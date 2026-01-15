import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import os
import glob
import random
import time
import soundfile as sf
import numpy as np
from audio_engine import AudioEngine

# --- Configuration & Theme ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class LazyBatchGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MultiMorpher - Lazy Batch")
        self.geometry("600x780")
        self.resizable(False, False)

        # State Variables
        self.source_folders = []
        self.is_running = False
        self.stop_event = threading.Event()
        
        # UI Layout
        self._init_ui()

    def _init_ui(self):
        # 1. Source Folders
        self.frame_sources = ctk.CTkFrame(self)
        self.frame_sources.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(self.frame_sources, text="SOURCE FOLDERS", font=("Arial", 12, "bold")).pack(anchor="w", padx=5, pady=5)
        
        self.listbox_folders = tk.Listbox(
            self.frame_sources, 
            height=4, 
            bg="#2b2b2b", 
            fg="#dce4ee", 
            selectbackground="#1f538d",
            highlightthickness=0,
            borderwidth=0
        )
        self.listbox_folders.pack(fill="x", padx=5, pady=5)
        
        self.btn_frame = ctk.CTkFrame(self.frame_sources, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkButton(self.btn_frame, text="Add Folder", width=100, command=self.add_folder).pack(side="left", padx=(0, 5))
        ctk.CTkButton(self.btn_frame, text="Clear", width=80, fg_color="gray", command=self.clear_folders).pack(side="left")

        # 2. Duration & Source Filter
        self.frame_filter = ctk.CTkFrame(self)
        self.frame_filter.pack(fill="x", padx=10, pady=5)
        
        # Row 1: Duration
        self.filter_row1 = ctk.CTkFrame(self.frame_filter, fg_color="transparent")
        self.filter_row1.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(self.filter_row1, text="Duration (s):", width=80).pack(side="left")
        self.entry_min = ctk.CTkEntry(self.filter_row1, width=50)
        self.entry_min.insert(0, "1.0")
        self.entry_min.pack(side="left", padx=2)
        ctk.CTkLabel(self.filter_row1, text="~").pack(side="left")
        self.entry_max = ctk.CTkEntry(self.filter_row1, width=50)
        self.entry_max.insert(0, "10.0")
        self.entry_max.pack(side="left", padx=2)

        # Row 2: Source Count
        self.filter_row2 = ctk.CTkFrame(self.frame_filter, fg_color="transparent")
        self.filter_row2.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(self.filter_row2, text="Sources:", width=80).pack(side="left")
        self.opt_source_count = ctk.CTkOptionMenu(self.filter_row2, values=["Auto (2-4)", "1", "2", "3", "4"], width=110)
        self.opt_source_count.pack(side="left", padx=5)

        # 3. Chaos Level
        self.frame_chaos = ctk.CTkFrame(self)
        self.frame_chaos.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.frame_chaos, text="CHAOS LEVEL", font=("Arial", 12, "bold")).pack(anchor="w", padx=5, pady=(5,0))
        
        self.chaos_row = ctk.CTkFrame(self.frame_chaos, fg_color="transparent")
        self.chaos_row.pack(fill="x")
        
        self.lbl_chaos_val = ctk.CTkLabel(self.chaos_row, text="0.5")
        self.lbl_chaos_val.pack(side="right", padx=10)
        
        self.slider_chaos = ctk.CTkSlider(self.frame_chaos, from_=0.0, to=1.0, number_of_steps=100, command=self.update_chaos_label)
        self.slider_chaos.set(0.5)
        self.slider_chaos.pack(fill="x", padx=10, pady=(0, 10))
        
        self.switch_pitch = ctk.CTkSwitch(self.frame_chaos, text="Randomize Pitch Curve")
        self.switch_pitch.pack(anchor="w", padx=10, pady=(0, 10))

        self.switch_trim = ctk.CTkSwitch(self.frame_chaos, text="Trim Silence")
        self.switch_trim.pack(anchor="w", padx=10, pady=(0, 10))

        # 4. Output Settings
        self.frame_output = ctk.CTkFrame(self)
        self.frame_output.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.frame_output, text="OUTPUT SETTINGS", font=("Arial", 12, "bold")).pack(anchor="w", padx=5, pady=5)
        
        # Path
        self.out_row1 = ctk.CTkFrame(self.frame_output, fg_color="transparent")
        self.out_row1.pack(fill="x", padx=5)
        ctk.CTkLabel(self.out_row1, text="Path:", width=60, anchor="w").pack(side="left")
        self.entry_path = ctk.CTkEntry(self.out_row1)
        self.entry_path.insert(0, "./output")
        self.entry_path.pack(side="left", fill="x", expand=True, padx=5)
        
        # Prefix & Count
        self.out_row2 = ctk.CTkFrame(self.frame_output, fg_color="transparent")
        self.out_row2.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(self.out_row2, text="Prefix:", width=60, anchor="w").pack(side="left")
        self.entry_prefix = ctk.CTkEntry(self.out_row2, width=120)
        self.entry_prefix.insert(0, "creature_")
        self.entry_prefix.pack(side="left", padx=5)
        
        ctk.CTkLabel(self.out_row2, text="Count:", width=60, anchor="e").pack(side="left", padx=5)
        self.entry_count = ctk.CTkEntry(self.out_row2, width=80)
        self.entry_count.insert(0, "10")
        self.entry_count.pack(side="left", padx=5)

        # 5. Execution
        self.frame_exec = ctk.CTkFrame(self)
        self.frame_exec.pack(fill="x", padx=10, pady=10)
        
        self.btn_run = ctk.CTkButton(self.frame_exec, text="▶ Run Lazy Batch", fg_color="green", height=40, command=self.start_batch)
        self.btn_run.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        
        self.btn_stop = ctk.CTkButton(self.frame_exec, text="Stop", fg_color="darkred", height=40, state="disabled", command=self.stop_batch)
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        # 6. Log Console
        self.console = ctk.CTkTextbox(self, height=150)
        self.console.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.log("MultiMorpher Lazy Batch Ready.")

    # --- Actions ---
    def update_chaos_label(self, val):
        self.lbl_chaos_val.configure(text=f"{val:.2f}")

    def add_folder(self):
        path = filedialog.askdirectory()
        if path:
            if path not in self.source_folders:
                self.source_folders.append(path)
                self.listbox_folders.insert(tk.END, path)
                self.log(f"Added source: {path}")

    def clear_folders(self):
        self.source_folders = []
        self.listbox_folders.delete(0, tk.END)
        self.log("Sources cleared.")

    def log(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.console.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.console.see(tk.END)

    def toggle_ui_state(self, running):
        state = "disabled" if running else "normal"
        self.btn_run.configure(state=state)
        self.entry_min.configure(state=state)
        self.entry_max.configure(state=state)
        self.slider_chaos.configure(state=state)
        self.opt_source_count.configure(state=state)
        self.switch_pitch.configure(state=state)
        self.switch_trim.configure(state=state)
        self.entry_path.configure(state=state)
        
        self.btn_stop.configure(state="normal" if running else "disabled")

    # --- Batch Logic ---
    def start_batch(self):
        if not self.source_folders:
            self.log("Error: No source folders selected.")
            return
            
        try:
            d_min = float(self.entry_min.get())
            d_max = float(self.entry_max.get())
            count = int(self.entry_count.get())
            chaos = self.slider_chaos.get()
            out_path = self.entry_path.get()
            prefix = self.entry_prefix.get()
            
            src_mode = self.opt_source_count.get()
            use_pitch = bool(self.switch_pitch.get())
            trim = bool(self.switch_trim.get())
            
        except ValueError:
            self.log("Error: Invalid input parameters.")
            return

        self.is_running = True
        self.stop_event.clear()
        self.toggle_ui_state(True)
        
        # Start Thread
        t = threading.Thread(target=self.batch_worker, args=(d_min, d_max, count, chaos, out_path, prefix, src_mode, use_pitch, trim))
        t.daemon = True
        t.start()

    def stop_batch(self):
        if self.is_running:
            self.log("Stopping... please wait for current process.")
            self.stop_event.set()

    def batch_worker(self, d_min, d_max, count, chaos, out_path, prefix, src_mode, use_pitch, trim):
        # 1. Scan and Filter Files
        self.log("Scanning source folders...")
        valid_files = []
        
        extensions = ['*.wav', '*.mp3', '*.flac', '*.ogg', '*.aiff']
        
        for folder in self.source_folders:
            for ext in extensions:
                files = glob.glob(os.path.join(folder, ext))
                for f in files:
                    if self.stop_event.is_set(): break
                    try:
                        info = sf.info(f)
                        if d_min <= info.duration <= d_max:
                            valid_files.append(f)
                    except Exception as e:
                        print(f"Skipping {f}: {e}")
            if self.stop_event.is_set(): break
            
        if not valid_files:
            self.log(f"No valid files found between {d_min}s and {d_max}s.")
            self.is_running = False
            self.toggle_ui_state(False)
            return

        self.log(f"Found {len(valid_files)} valid source files.")
        
        # Prepare Output Dir
        os.makedirs(out_path, exist_ok=True)
        
        # 2. Main Loop
        for i in range(count):
            if self.stop_event.is_set():
                self.log("Batch cancelled by user.")
                break
                
            self.log(f"Generating {i+1}/{count}...")
            
            # Init Engine per iteration
            engine = AudioEngine()
            
            try:
                # determine num sources
                if "Auto" in src_mode:
                    pick_count = random.randint(2, 4)
                else:
                    pick_count = int(src_mode)
                
                # Ensure we have enough files
                actual_pick = min(pick_count, len(valid_files))
                if actual_pick < 1: 
                     self.log("Error: No files to pick.")
                     break
                     
                sources = random.sample(valid_files, actual_pick)
                
                # Load Sources
                if len(sources) >= 1: engine.load_source_a(sources[0])
                if len(sources) >= 2: engine.load_source_b(sources[1])
                if len(sources) >= 3: engine.load_source_c(sources[2])
                if len(sources) >= 4: engine.load_source_d(sources[3])
                
                # Chaos Mapping
                # Morph X/Y
                morph_x = random.random()
                morph_y = random.random()
                
                # Shape
                if len(sources) == 1:
                    shape = "Static"
                    morph_x = 0.0
                    morph_y = 0.0
                else:
                    # MultiMorpher has more shapes
                    shapes = ["Static", "Circle", "Eight", "Scan", "RandomMovement", "RandomPoint"]
                    shape = random.choice(shapes)
                
                # Morph Speed
                m_speed = 0.5 + random.uniform(-0.4, 3.0 * chaos) 
                
                # Formant
                f_range = chaos * 0.5 
                formant = 1.0 + random.uniform(-f_range, f_range)
                
                # Breath
                breath = random.uniform(0.0, chaos * 1.0) 
                
                # Pitch Curve
                pitch_curve = np.zeros(100)
                if use_pitch and chaos > 0.05:
                    dest_points = max(2, int(10 * chaos))
                    indices = np.linspace(0, 99, dest_points).astype(int)
                    max_semitone = 12 * chaos
                    vals = np.random.uniform(-max_semitone, max_semitone, dest_points)
                    pitch_curve = np.interp(np.arange(100), indices, vals)
                    if dest_points > 5:
                        pitch_curve = np.convolve(pitch_curve, np.ones(5)/5, mode='same')
                
                # --- NEW FX Mapping ---
                # Speed
                speed = 1.0 + random.uniform(-chaos*0.5, chaos*0.5)
                
                # Growl & Tone
                growl = 0.0
                if chaos > 0.1: growl = random.uniform(0, chaos * 0.8)
                
                tone = random.uniform(-chaos, chaos)
                
                # Dist
                dist = 0.0
                if chaos > 0.2: dist = random.uniform(0, chaos * 0.5)
                
                # Bitcrush (Lo-fi)
                bit_depth = 16
                bit_rate_div = 1
                if chaos > 0.4:
                    if random.random() < chaos:
                        bit_depth = int(16 - (chaos * 8)) # Down to 8bit
                        bit_depth = max(4, bit_depth)
                    if random.random() < chaos:
                        bit_rate_div = int(1 + chaos * 10) # up to div 11
                
                # Mod (Ring)
                ring_mix = 0.0
                ring_freq = 30
                if chaos > 0.3 and random.random() < chaos * 0.5:
                     ring_mix = random.uniform(0, chaos * 0.6)
                     ring_freq = random.uniform(20, 400 * chaos)
                
                # Delay
                delay_mix = 0.0
                delay_time = 0.2
                delay_fb = 0.0
                if chaos > 0.2 and random.random() < chaos:
                    delay_mix = random.uniform(0, chaos * 0.5)
                    delay_time = random.uniform(0.05, 0.5)
                    delay_fb = random.uniform(0, 0.6)
                
                # Reverb
                reverb_mix = 0.0
                if random.random() < 0.5 + (chaos * 0.5): # Often on
                     reverb_mix = random.uniform(0, 0.4 + (chaos * 0.3))
                
                # Spacer (Stereo Width)
                # Apply heavy width if chaos is high or just genuinely random
                # BUT user wants "Stereo Output". So let's keep width high by default.
                # If chaos is 0, width=1.0 (Clean Stereo).
                spacer_width = 1.0 
                
                vol = 0.9
                
                # Render
                fname = f"{prefix}{i+1:03d}_{int(time.time())}.wav"
                fpath = os.path.join(out_path, fname)
                
                success, msg = engine.render_batch_sample(
                    fpath, 
                    morph_x, morph_y, shape, m_speed, 
                    formant, breath, pitch_curve, 
                    speed, growl, tone, dist, 
                    bit_depth, bit_rate_div, ring_freq, ring_mix,
                    delay_time, delay_fb, delay_mix, reverb_mix, spacer_width, vol,
                    trim_silence=trim
                )
                
                if success:
                    self.log(f"-> Saved: {fname}")
                else:
                    self.log(f"-> Error: {msg}")

            except Exception as e:
                self.log(f"-> Critical Error: {str(e)}")
        
        self.log("Batch processing finished.")
        self.is_running = False
        self.toggle_ui_state(False)

if __name__ == "__main__":
    app = LazyBatchGUI()
    app.mainloop()
