
import customtkinter as ctk
import os
import sys
import threading
import time
import glob
import numpy as np
import librosa
import soundfile as sf
import shutil
from tkinterdnd2 import TkinterDnD, DND_ALL
from tkinter import filedialog
from datetime import datetime

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class QuartzSlicer(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title("Quartz Audio Slicer")
        self.geometry("600x550")
        
        self._init_ui()
        
    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # Log expands
        
        # --- Zone 1: Input ---
        fr_inp = ctk.CTkFrame(self)
        fr_inp.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(fr_inp, text="Target Folder:", font=("Arial", 12, "bold")).pack(anchor="w", padx=10, pady=(10,0))
        
        self.ent_input = ctk.CTkEntry(fr_inp, placeholder_text="Drag & Drop Folder Here")
        self.ent_input.pack(fill="x", padx=10, pady=5)
        self.ent_input.drop_target_register(DND_ALL)
        self.ent_input.dnd_bind('<<Drop>>', self.drop_path)
        
        self.btn_browse = ctk.CTkButton(fr_inp, text="Browse", command=self.browse_folder, width=80)
        self.btn_browse.pack(anchor="e", padx=10, pady=(0,10))

        # --- Zone 2: Settings ---
        fr_set = ctk.CTkFrame(self)
        fr_set.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        # Threshold
        ctk.CTkLabel(fr_set, text="Threshold (dB):").grid(row=0, column=0, padx=10, pady=10)
        self.sld_thresh = ctk.CTkSlider(fr_set, from_=-80, to=0, number_of_steps=80, command=self.update_thresh_label)
        self.sld_thresh.set(-30)
        self.sld_thresh.grid(row=0, column=1, sticky="ew", padx=10)
        
        self.lbl_thresh_val = ctk.CTkLabel(fr_set, text="-30 dB", width=60)
        self.lbl_thresh_val.grid(row=0, column=2, padx=10)
        
        # Min Interval (Refractory Period)
        ctk.CTkLabel(fr_set, text="Next Slice Wait (ms):").grid(row=1, column=0, padx=10, pady=10)
        self.ent_min_interval = ctk.CTkEntry(fr_set, width=80)
        self.ent_min_interval.insert(0, "500") # Default 500ms
        self.ent_min_interval.grid(row=1, column=1, sticky="w", padx=10)
        
        # Min Duration
        ctk.CTkLabel(fr_set, text="Min Duration (ms):").grid(row=2, column=0, padx=10, pady=10)
        self.ent_min_dur = ctk.CTkEntry(fr_set, width=80)
        self.ent_min_dur.insert(0, "100") 
        self.ent_min_dur.grid(row=2, column=1, sticky="w", padx=10)

        # Pad (Mergin)
        ctk.CTkLabel(fr_set, text="Pad (ms):").grid(row=3, column=0, padx=10, pady=10)
        self.ent_pad = ctk.CTkEntry(fr_set, width=80)
        self.ent_pad.insert(0, "50")
        self.ent_pad.grid(row=3, column=1, sticky="w", padx=10)

        # Options
        self.chk_recursive = ctk.CTkCheckBox(fr_set, text="Scan Subfolders")
        self.chk_recursive.grid(row=4, column=0, padx=10, pady=5)
        
        self.chk_mono = ctk.CTkCheckBox(fr_set, text="Stereo to Mono")
        self.chk_mono.grid(row=4, column=1, padx=10, pady=5)
        
        self.chk_norm = ctk.CTkCheckBox(fr_set, text="Normalize")
        self.chk_norm.grid(row=4, column=2, padx=10, pady=5)

        # Execute
        self.btn_run = ctk.CTkButton(fr_set, text="RUN SLICER", command=self.start_processing, fg_color="#E53935", font=("Arial", 14, "bold"), height=40)
        self.btn_run.grid(row=5, column=0, columnspan=3, sticky="ew", padx=20, pady=20)
        
        # --- Zone 3: Log ---
        self.txt_log = ctk.CTkTextbox(self)
        self.txt_log.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.log("Ready.")

    def drop_path(self, event):
        path = event.data
        if path.startswith('{') and path.endswith('}'): path = path[1:-1]
        self.ent_input.delete(0, 'end')
        self.ent_input.insert(0, path)

    def browse_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.ent_input.delete(0, 'end')
            self.ent_input.insert(0, p)

    def update_thresh_label(self, val):
        self.lbl_thresh_val.configure(text=f"{int(val)} dB")

    def log(self, msg):
        self.txt_log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.txt_log.see("end")

    def start_processing(self):
        target_dir = self.ent_input.get().strip()
        if not os.path.exists(target_dir):
            self.log("Error: Target folder does not exist.")
            return

        thresh_db = self.sld_thresh.get()
        try:
            min_interval = float(self.ent_min_interval.get()) / 1000.0
            min_dur = float(self.ent_min_dur.get()) / 1000.0
            pad = float(self.ent_pad.get()) / 1000.0
        except ValueError:
            self.log("Error: Invalid numeric parameters.")
            return
            
        opts = {
            "recursive": self.chk_recursive.get(),
            "mono": self.chk_mono.get(),
            "norm": self.chk_norm.get()
        }

        self.btn_run.configure(state="disabled")
        threading.Thread(target=self._process_thread, args=(target_dir, thresh_db, min_interval, min_dur, pad, opts), daemon=True).start()

    def ensure_unique(self, path):
        if not os.path.exists(path): return path
        base, ext = os.path.splitext(path)
        count = 1
        while True:
            new_path = f"{base}_{count}{ext}"
            if not os.path.exists(new_path): return new_path
            count += 1

    def _process_thread(self, target_dir, thresh_db, min_interval, min_dur, pad, opts):
        self.log(f"Start Slicing... T={thresh_db}dB")
        self.log(f"Opts: Rec={opts['recursive']}, Mono={opts['mono']}, Norm={opts['norm']}")
        
        # files
        exts = ['*.wav', '*.mp3', '*.aif', '*.flac']
        files = []
        for e in exts:
            if opts['recursive']:
                files.extend(glob.glob(os.path.join(target_dir, "**", e), recursive=True))
            else:
                files.extend(glob.glob(os.path.join(target_dir, e)))
            
        if not files:
            self.log("No audio files found.")
            self.btn_run.configure(state="normal")
            return

        # Prepare Output Dir
        out_dir = os.path.join(target_dir, "Slice001")
        count = 1
        while os.path.exists(out_dir):
             count += 1
             out_dir = os.path.join(target_dir, f"Slice{count:03d}")
        
        os.makedirs(out_dir, exist_ok=True)
        self.log(f"Output Directory: {os.path.basename(out_dir)}")

        total_slices = 0
        
        for fpath in files:
            fname = os.path.basename(fpath)
            self.log(f"Processing: {fname}")
            
            try:
                # Load (Preserve Stereo)
                y, sr = librosa.load(fpath, sr=None, mono=False) 
                
                # Prepare for detection (Mono mix)
                if y.ndim > 1:
                    y_mono = librosa.to_mono(y)
                else:
                    y_mono = y
                
                # Slicing Logic (using y_mono)
                hop_length = 512
                frame_length = 1024
                rms = librosa.feature.rms(y=y_mono, frame_length=frame_length, hop_length=hop_length)[0]
                db_env = librosa.amplitude_to_db(rms, ref=np.max)
                
                # Mask
                is_over = db_env > thresh_db
                
                slices = []
                in_voice = False
                start_frame = 0
                cooldown_frames = 0
                wait_frames = int(min_interval * sr / hop_length)
                min_frames = int(min_dur * sr / hop_length)
                
                # Scan frames
                for i, active in enumerate(is_over):
                    if cooldown_frames > 0:
                        cooldown_frames -= 1
                        if active: pass 
                        in_voice = False 
                        continue
                    
                    if not in_voice and active:
                        in_voice = True
                        start_frame = max(0, i - int(pad * sr / hop_length)) 
                    elif in_voice and not active:
                        in_voice = False
                        end_frame = i + int(pad * sr / hop_length)
                        dur_frames = end_frame - start_frame
                        if dur_frames >= min_frames:
                            s_samp = max(0, start_frame * hop_length)
                            e_samp = min(y_mono.shape[-1], end_frame * hop_length)
                            slices.append((s_samp, e_samp))
                            cooldown_frames = wait_frames
                
                # Handle end
                if in_voice:
                    end_frame = len(db_env)
                    dur_frames = end_frame - start_frame
                    if dur_frames >= min_frames:
                         s_samp = max(0, start_frame * hop_length)
                         e_samp = y_mono.shape[-1]
                         slices.append((s_samp, e_samp))

                # Export Logic
                save_list = []
                is_full_file_processed = False
                if not slices:
                    # Treat entire file as one slice if no slices found or if processing options are enabled
                    if opts['mono'] or opts['norm']:
                        save_list.append((0, y.shape[-1]))
                        is_full_file_processed = True
                    else:
                        # No slices and no processing, just copy the original file
                        self.log(f"  -> No slices. Copying original.")
                        dest = os.path.join(out_dir, fname)
                        dest = self.ensure_unique(dest)
                        shutil.copy2(fpath, dest)
                        continue
                else:
                    save_list = slices

                for i, (start, end) in enumerate(save_list):
                    # Extract slice (handle stereo)
                    if y.ndim > 1:
                        y_slice = y[:, start:end]
                    else:
                        y_slice = y[start:end]
                    
                    # Peak check (only if actual slicing occurred, not for full file processing)
                    if not is_full_file_processed:
                        if y_slice.ndim > 1:
                             peak = np.max(np.abs(y_slice))
                        else:
                             peak = np.max(np.abs(y_slice))
                        peak_db = librosa.amplitude_to_db(np.array([peak]), ref=np.max)[0]
                        if peak_db < thresh_db: continue
                    
                    # Process (Mono/Norm)
                    if opts['mono'] and y_slice.ndim > 1:
                        y_slice = librosa.to_mono(y_slice)
                        
                    if opts['norm']:
                        max_val = np.max(np.abs(y_slice))
                        if max_val > 0:
                            y_slice = y_slice / max_val * 0.99
                    
                    # Output Name
                    base, ext = os.path.splitext(fname)
                    if is_full_file_processed:
                        out_name = f"{base}{ext}"
                    else:
                        out_name = f"{base}_{i+1:02d}{ext}"
                        
                    out_path = os.path.join(out_dir, out_name)
                    out_path = self.ensure_unique(out_path)
                    
                    # Write (Transpose if stereo for soundfile)
                    if y_slice.ndim > 1: # If still stereo (channels, samples)
                        sf.write(out_path, y_slice.T, sr) # Transpose to (samples, channels)
                    else: # Mono (samples,)
                        sf.write(out_path, y_slice, sr)
                        
                    if not is_full_file_processed: total_slices += 1
                
                if not is_full_file_processed:
                     self.log(f"  -> Generated {len(slices)} slices.")
                else:
                     self.log(f"  -> No slices cut. Copied (Processed).")

            except Exception as e:
                self.log(f"Error processing {fname}: {e}")

        self.log(f"ALL DONE. Total Slices: {total_slices}")
        self.log(f"Saved to: {out_dir}")
        self.btn_run.configure(state="normal")
        # Flash or Sound?
        try: winsound.MessageBeep()
        except: pass

if __name__ == "__main__":
    app = QuartzSlicer()
    app.mainloop()
