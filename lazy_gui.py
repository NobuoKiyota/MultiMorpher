import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import os
import glob
import random
import time
import datetime
import soundfile as sf
import numpy as np
import json
import shutil
import pandas as pd
from audio_engine import AudioEngine, AudioClassifier

# --- Configuration & Theme ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Ensure we look in the script directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "lazy_config.json")
TAGS_FILE = os.path.join(BASE_DIR, "tags.ods")
HISTORY_DIR = os.path.join(BASE_DIR, "lazy_history")

class LazyBatchGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MultiMorpher - Lazy Batch")
        self.geometry("600x920") # Increased for catalog tool
        self.resizable(False, False)

        # State Variables
        self.source_folders = []
        self.is_running = False
        self.stop_event = threading.Event()
        
        # Configuration Defaults
        self.tag_candidates = ["Monster", "Scream", "Cute", "Impact", "Sci-Fi", "Growl"]
        self.config_source = "Default"
        
        # Ensure history dir exists
        os.makedirs(HISTORY_DIR, exist_ok=True)
        
        # UI Layout
        self._init_ui()

        # Load Tags (ODS Master)
        self.reload_config()
        
        # Load Latest History (UI State)
        self.load_latest_history()
        
    def load_tags_from_ods(self):
        if not os.path.exists(TAGS_FILE):
            return None
        
        try:
            # engine='odf' requires odfpy
            df = pd.read_excel(TAGS_FILE, engine="odf", header=None)
            if df.empty:
                return []
                
            col = df.iloc[:, 0]
            col = col.dropna()
            tags = [str(x).strip() for x in col.tolist() if str(x).strip()]
            
            return tags
        except Exception as e:
            self.log(f"Error loading {os.path.basename(TAGS_FILE)}: {e}")
            return None

    def load_config(self):
        # 1. Try ODS first
        ods_tags = self.load_tags_from_ods()
        
        if ods_tags is not None:
            self.tag_candidates = ods_tags
            self.config_source = os.path.basename(TAGS_FILE)
            self.log(f"Tags loaded from {self.config_source} ({len(self.tag_candidates)} items)")
        else:
            # 2. Fallback JSON
            if os.path.exists(CONFIG_FILE):
                try:
                    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        self.tag_candidates = data.get("tag_candidates", self.tag_candidates)
                        self.config_source = os.path.basename(CONFIG_FILE)
                except Exception as e:
                    self.log(f"Error loading config: {e}")
            else:
                 self.log("No config found, using defaults.")
                 self.config_source = "Default"

    def reload_config(self):
        self.log(f"Reloading tags... Looking for {os.path.basename(TAGS_FILE)}...")
        self.load_config()
        self.update_tag_info()

    def update_tag_info(self):
        if hasattr(self, 'lbl_tag_info'):
            count = len(self.tag_candidates)
            self.lbl_tag_info.configure(text=f"Loaded {count} tags ({self.config_source})")
            
    def open_ods(self):
        if os.path.exists(TAGS_FILE):
            try:
                os.startfile(TAGS_FILE)
            except Exception as e:
                self.log(f"Failed to open {TAGS_FILE}: {e}")
        else:
            self.log(f"{TAGS_FILE} not found. Create it to manage tags via spreadsheet.")

    # --- History & AutoSave ---
    def get_ui_state(self):
        state = {
            "source_folders": self.source_folders,
            "duration_min": self.entry_min.get(),
            "duration_max": self.entry_max.get(),
            "source_count": self.opt_source_count.get(),
            "chaos": self.slider_chaos.get(),
            "pitch": self.switch_pitch.get(),
            "trim": self.switch_trim.get(),
            "autotag": self.switch_autotag.get(),
            "out_path": self.entry_path.get(),
            "prefix": self.entry_prefix.get(),
            "count": self.entry_count.get(),
            "catalog_name": self.entry_catalog_name.get(),
            "catalog_auto": self.switch_catalog_auto.get()
        }
        return state

    def set_ui_state(self, state):
        try:
            # Sources
            self.source_folders = state.get("source_folders", [])
            self.listbox_folders.delete(0, tk.END)
            for f in self.source_folders:
                self.listbox_folders.insert(tk.END, f)
            
            # Filter
            self.entry_min.delete(0, tk.END)
            self.entry_min.insert(0, state.get("duration_min", "1.0"))
            self.entry_max.delete(0, tk.END)
            self.entry_max.insert(0, state.get("duration_max", "10.0"))
            self.opt_source_count.set(state.get("source_count", "Auto (2-4)"))
            
            # Chaos
            chaos_val = state.get("chaos", 0.5)
            self.slider_chaos.set(chaos_val)
            self.update_chaos_label(chaos_val)
            
            if state.get("pitch", 0): self.switch_pitch.select()
            else: self.switch_pitch.deselect()
            
            if state.get("trim", 0): self.switch_trim.select()
            else: self.switch_trim.deselect()
            
            # Tagging
            if state.get("autotag", 0): self.switch_autotag.select()
            else: self.switch_autotag.deselect()
            
            # Output
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, state.get("out_path", "./output"))
            
            self.entry_prefix.delete(0, tk.END)
            self.entry_prefix.insert(0, state.get("prefix", "creature_"))
            
            self.entry_count.delete(0, tk.END)
            self.entry_count.insert(0, state.get("count", "10"))
            
            # Catalog
            self.entry_catalog_name.delete(0, tk.END)
            self.entry_catalog_name.insert(0, state.get("catalog_name", "catalog.ods"))
            if state.get("catalog_auto", 1): self.switch_catalog_auto.select()
            else: self.switch_catalog_auto.deselect()

        except Exception as e:
            self.log(f"Error applying history state: {e}")

    def save_history(self):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"config_{timestamp}.json"
        fpath = os.path.join(HISTORY_DIR, fname)
        
        state = self.get_ui_state()
        try:
            with open(fpath, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
            self.log(f"Auto-saved history: {fname}")
            self.cleanup_history()
            self.refresh_history_menu()
        except Exception as e:
            print(f"Failed to auto-save history: {e}")

    def cleanup_history(self):
        # Keep only latest 30
        files = glob.glob(os.path.join(HISTORY_DIR, "config_*.json"))
        # Sort by name (timestamp is in name)
        files.sort()
        
        if len(files) > 30:
            to_delete = files[:-30] # All except last 30
            for f in to_delete:
                try:
                    os.remove(f)
                    print(f"Deleted old history: {os.path.basename(f)}")
                except: pass

    def get_history_list(self):
        files = glob.glob(os.path.join(HISTORY_DIR, "config_*.json"))
        files.sort(reverse=True) # Newest first
        # Format: config_YYYYMMDD_HHMMSS.json -> YYYYMMDD_HHMMSS
        names = [os.path.basename(f).replace("config_", "").replace(".json", "") for f in files]
        return names

    def refresh_history_menu(self):
        history_items = self.get_history_list()
        if not history_items:
            history_items = ["No History"]
        
        self.opt_history.configure(values=history_items)
        if history_items and history_items[0] != "No History":
             self.opt_history.set(history_items[0])
        else:
             self.opt_history.set("Select History")

    def load_selected_history(self, value):
        if value == "No History" or value == "Select History":
            return
            
        fname = f"config_{value}.json"
        fpath = os.path.join(HISTORY_DIR, fname)
        if os.path.exists(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.set_ui_state(state)
                self.log(f"Restored history: {value}")
            except Exception as e:
                self.log(f"Error loading history {value}: {e}")

    def load_latest_history(self):
        history_items = self.get_history_list()
        if history_items:
            self.load_selected_history(history_items[0])

    # --- Catalog Tool ---
    def generate_catalog_action(self):
        out_path = self.entry_path.get()
        ods_name = self.entry_catalog_name.get()
        if not ods_name.endswith(".ods"):
            ods_name += ".ods"
            
        if not os.path.exists(out_path):
            self.log(f"Output folder not found: {out_path}")
            return
            
        full_ods_path = os.path.join(out_path, ods_name)
        
        # Run in thread so UI doesn't freeze
        t = threading.Thread(target=self.generate_catalog, args=(out_path, full_ods_path))
        t.daemon = True
        t.start()

    def generate_catalog(self, target_folder, ods_filename):
        self.log("Generating catalog...")
        data = []
        
        # Recursive scan
        for root, dirs, files in os.walk(target_folder):
            for f in files:
                if f.lower().endswith(('.wav', '.mp3', '.flac', '.ogg', '.aiff', '.aif', '.aifc', '.au', '.snd')):
                    full_path = os.path.join(root, f)
                    
                    # 1. Filename
                    # 2. Category (Tag) - Parent folder name relative to target_folder?
                    # actually just parent folder name is simple enough
                    category = os.path.basename(root)
                    if category == os.path.basename(target_folder):
                        category = "Root"
                        
                    # 3. Duration
                    try:
                        info = sf.info(full_path)
                        dur = round(info.duration, 2)
                    except:
                        dur = 0.0
                        
                    # 4. Size (KB)
                    try:
                        size_kb = round(os.path.getsize(full_path) / 1024, 1)
                    except:
                        size_kb = 0.0
                        
                    # 5. Date
                    try:
                        mtime = os.path.getmtime(full_path)
                        dt = datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        dt = "-"
                        
                    data.append({
                        "Filename": f,
                        "Category": category,
                        "Duration(s)": dur,
                        "Size(KB)": size_kb,
                        "Date": dt,
                        "Path": full_path
                    })
        
        if not data:
            self.log("No audio files found for catalog.")
            return

        try:
            df = pd.DataFrame(data)
            # engine='odf'
            df.to_excel(ods_filename, engine="odf", index=False)
            self.log(f"Catalog saved to {os.path.basename(ods_filename)} ({len(data)} files)")
        except Exception as e:
            self.log(f"Error saving catalog: {e}")

    # --- UI Init ---
    def _init_ui(self):
        # 0. History Header
        self.frame_history = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_history.pack(fill="x", padx=10, pady=(10, 0))
        
        ctk.CTkLabel(self.frame_history, text="History:", font=("Arial", 11)).pack(side="left")
        self.opt_history = ctk.CTkOptionMenu(self.frame_history, values=["No History"], width=200, command=self.load_selected_history)
        self.opt_history.pack(side="left", padx=5)
        self.refresh_history_menu()

        # 1. Source Folders
        self.frame_sources = ctk.CTkFrame(self)
        self.frame_sources.pack(fill="x", padx=10, pady=(5, 5))
        
        header_frame = ctk.CTkFrame(self.frame_sources, fg_color="transparent")
        header_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(header_frame, text="SOURCE FOLDERS (Right-click to remove)", font=("Arial", 12, "bold")).pack(side="left", anchor="w")
        
        # Container for Listbox + Scrollbar
        list_container = ctk.CTkFrame(self.frame_sources, fg_color="transparent")
        list_container.pack(fill="x", padx=5, pady=0)
        
        scrollbar = tk.Scrollbar(list_container, orient="vertical")
        
        self.listbox_folders = tk.Listbox(
            list_container, 
            height=5, 
            bg="#2b2b2b", 
            fg="#dce4ee", 
            selectbackground="#1f538d",
            highlightthickness=0,
            borderwidth=0,
            yscrollcommand=scrollbar.set,
            font=("Arial", 11) 
        )
        scrollbar.config(command=self.listbox_folders.yview)
        
        scrollbar.pack(side="right", fill="y")
        self.listbox_folders.pack(side="left", fill="both", expand=True)
        
        # Right Click Menu
        self.context_menu = tk.Menu(self.listbox_folders, tearoff=0)
        self.context_menu.add_command(label="Remove Selected", command=self.remove_selected_folder)
        self.listbox_folders.bind("<Button-3>", self.show_context_menu)
        
        self.btn_frame = ctk.CTkFrame(self.frame_sources, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkButton(self.btn_frame, text="Add Folder", width=100, command=self.add_folder).pack(side="left", padx=(0, 5))
        ctk.CTkButton(self.btn_frame, text="Clear All", width=80, fg_color="darkred", command=self.clear_folders).pack(side="left")
        ctk.CTkButton(self.btn_frame, text="Remove Selected", width=100, fg_color="gray", command=self.remove_selected_folder).pack(side="right")

        # 2. Filter Settings (Duration & Sources on ONE LINE)
        self.frame_filter = ctk.CTkFrame(self)
        self.frame_filter.pack(fill="x", padx=10, pady=5)
        
        self.filter_row = ctk.CTkFrame(self.frame_filter, fg_color="transparent")
        self.filter_row.pack(fill="x", padx=5, pady=5)
        
        # Duration
        ctk.CTkLabel(self.filter_row, text="Duration (s):", width=70).pack(side="left")
        self.entry_min = ctk.CTkEntry(self.filter_row, width=40)
        self.entry_min.insert(0, "1.0")
        self.entry_min.pack(side="left", padx=2)
        ctk.CTkLabel(self.filter_row, text="~").pack(side="left")
        self.entry_max = ctk.CTkEntry(self.filter_row, width=40)
        self.entry_max.insert(0, "10.0")
        self.entry_max.pack(side="left", padx=2)
        
        # Spacer
        ctk.CTkLabel(self.filter_row, text="   |   ").pack(side="left")

        # Sources
        ctk.CTkLabel(self.filter_row, text="Sources:", width=60).pack(side="left")
        self.opt_source_count = ctk.CTkOptionMenu(self.filter_row, values=["Auto (2-4)", "1", "2", "3", "4"], width=100)
        self.opt_source_count.pack(side="left", padx=5)

        # 3. Chaos Level (Compact)
        self.frame_chaos = ctk.CTkFrame(self)
        self.frame_chaos.pack(fill="x", padx=10, pady=2) 
        
        self.chaos_header = ctk.CTkFrame(self.frame_chaos, fg_color="transparent")
        self.chaos_header.pack(fill="x", pady=(2, 0))
        
        ctk.CTkLabel(self.chaos_header, text="CHAOS LEVEL", font=("Arial", 12, "bold")).pack(side="left", padx=5)
        self.lbl_chaos_val = ctk.CTkLabel(self.chaos_header, text="0.5")
        self.lbl_chaos_val.pack(side="right", padx=10)
        
        self.slider_chaos = ctk.CTkSlider(self.frame_chaos, from_=0.0, to=1.0, number_of_steps=100, command=self.update_chaos_label)
        self.slider_chaos.set(0.5)
        self.slider_chaos.pack(fill="x", padx=10, pady=(0, 2))
        
        # Toggles Row (Compact)
        self.chaos_toggles = ctk.CTkFrame(self.frame_chaos, fg_color="transparent")
        self.chaos_toggles.pack(fill="x", padx=5, pady=(2, 5))
        
        self.switch_pitch = ctk.CTkSwitch(self.chaos_toggles, text="Random Pitch")
        self.switch_pitch.pack(side="left", padx=5)

        self.switch_trim = ctk.CTkSwitch(self.chaos_toggles, text="Trim Silence")
        self.switch_trim.pack(side="left", padx=15)

        # 4. Auto Tagging Settings
        self.frame_tagging = ctk.CTkFrame(self)
        self.frame_tagging.pack(fill="x", padx=10, pady=5)

        # Header Row
        self.tag_header = ctk.CTkFrame(self.frame_tagging, fg_color="transparent")
        self.tag_header.pack(fill="x", padx=5, pady=(5, 0))
        
        ctk.CTkLabel(self.tag_header, text="AI AUTO TAGGING", font=("Arial", 12, "bold")).pack(side="left")
        self.switch_autotag = ctk.CTkSwitch(self.tag_header, text="Enable", width=50)
        self.switch_autotag.pack(side="left", padx=10)
        
        # Controls Row
        self.tag_controls = ctk.CTkFrame(self.frame_tagging, fg_color="transparent")
        self.tag_controls.pack(fill="x", padx=10, pady=(2, 5))

        self.lbl_tag_info = ctk.CTkLabel(self.tag_controls, text="Loading...", anchor="w")
        self.lbl_tag_info.pack(side="left", fill="x", expand=True)
        
        self.btn_reload = ctk.CTkButton(self.tag_controls, text="Reload", width=70, command=self.reload_config)
        self.btn_reload.pack(side="right", padx=5)
        
        self.btn_edit = ctk.CTkButton(self.tag_controls, text="Edit ODS", width=70, fg_color="#555555", command=self.open_ods)
        self.btn_edit.pack(side="right", padx=5)

        # 5. Output Settings
        self.frame_output = ctk.CTkFrame(self)
        self.frame_output.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(self.frame_output, text="OUTPUT SETTINGS", font=("Arial", 12, "bold")).pack(anchor="w", padx=5, pady=(5, 2))
        
        # Path
        self.out_row1 = ctk.CTkFrame(self.frame_output, fg_color="transparent")
        self.out_row1.pack(fill="x", padx=5)
        ctk.CTkLabel(self.out_row1, text="Path:", width=50, anchor="w").pack(side="left")
        self.entry_path = ctk.CTkEntry(self.out_row1)
        self.entry_path.insert(0, "./output")
        self.entry_path.pack(side="left", fill="x", expand=True, padx=2)
        
        # Prefix & Count
        self.out_row2 = ctk.CTkFrame(self.frame_output, fg_color="transparent")
        self.out_row2.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(self.out_row2, text="Prefix:", width=50, anchor="w").pack(side="left")
        self.entry_prefix = ctk.CTkEntry(self.out_row2, width=120)
        self.entry_prefix.insert(0, "creature_")
        self.entry_prefix.pack(side="left", padx=2)
        
        ctk.CTkLabel(self.out_row2, text="Count:", width=50, anchor="e").pack(side="left", padx=5)
        self.entry_count = ctk.CTkEntry(self.out_row2, width=60)
        self.entry_count.insert(0, "10")
        self.entry_count.pack(side="left", padx=2)

        # 6. Catalog Tool (NEW)
        self.frame_catalog = ctk.CTkFrame(self)
        self.frame_catalog.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(self.frame_catalog, text="CATALOG TOOL", font=("Arial", 12, "bold")).pack(anchor="w", padx=5, pady=(5, 2))

        self.catalog_row = ctk.CTkFrame(self.frame_catalog, fg_color="transparent")
        self.catalog_row.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(self.catalog_row, text="Save Filename:", width=90).pack(side="left")
        self.entry_catalog_name = ctk.CTkEntry(self.catalog_row, width=120)
        self.entry_catalog_name.insert(0, "catalog.ods")
        self.entry_catalog_name.pack(side="left", padx=5)
        
        self.switch_catalog_auto = ctk.CTkSwitch(self.catalog_row, text="Update catalog after batch")
        self.switch_catalog_auto.select()
        self.switch_catalog_auto.pack(side="left", padx=10)
        
        self.btn_gen_catalog = ctk.CTkButton(self.catalog_row, text="📝 Create List Now", width=120, fg_color="#333333", command=self.generate_catalog_action)
        self.btn_gen_catalog.pack(side="right", padx=5)

        # 7. Execution
        self.frame_exec = ctk.CTkFrame(self)
        self.frame_exec.pack(fill="x", padx=10, pady=10)
        
        self.btn_run = ctk.CTkButton(self.frame_exec, text="▶ Run Lazy Batch", fg_color="green", height=40, command=self.start_batch)
        self.btn_run.pack(side="left", fill="x", expand=True, padx=5, pady=5)
        
        self.btn_stop = ctk.CTkButton(self.frame_exec, text="Stop", fg_color="darkred", height=40, state="disabled", command=self.stop_batch)
        self.btn_stop.pack(side="left", fill="x", expand=True, padx=5, pady=5)

        # 8. Log Console
        self.console = ctk.CTkTextbox(self, height=120)
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

    def show_context_menu(self, event):
        try:
            # Select item at click position
            index = self.listbox_folders.nearest(event.y)
            self.listbox_folders.selection_clear(0, tk.END)
            self.listbox_folders.selection_set(index)
            self.listbox_folders.activate(index)
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def remove_selected_folder(self):
        selection = self.listbox_folders.curselection()
        if not selection:
            return
            
        index = selection[0]
        folder = self.listbox_folders.get(index)
        
        if folder in self.source_folders:
            self.source_folders.remove(folder)
            
        self.listbox_folders.delete(index)
        self.log(f"Removed source: {folder}")

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
        self.switch_autotag.configure(state=state)
        self.btn_reload.configure(state=state)
        self.btn_edit.configure(state=state)
        self.opt_history.configure(state=state) # disable history load while running
        self.btn_gen_catalog.configure(state=state)
        
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
            
            use_autotag = bool(self.switch_autotag.get())
            
            # Catalog settings
            update_catalog = bool(self.switch_catalog_auto.get())
            catalog_name = self.entry_catalog_name.get()
            if not catalog_name.endswith(".ods"): catalog_name += ".ods"
            
            # Use loaded list
            tag_list = self.tag_candidates 
            
        except ValueError:
            self.log("Error: Invalid input parameters.")
            return

        self.is_running = True
        self.stop_event.clear()
        self.toggle_ui_state(True)
        
        # Start Thread
        t = threading.Thread(target=self.batch_worker, args=(d_min, d_max, count, chaos, out_path, prefix, src_mode, use_pitch, trim, use_autotag, tag_list, update_catalog, catalog_name))
        t.daemon = True
        t.start()

    def stop_batch(self):
        if self.is_running:
            self.log("Stopping... please wait for current process.")
            self.stop_event.set()

    def batch_worker(self, d_min, d_max, count, chaos, out_path, prefix, src_mode, use_pitch, trim, use_autotag, tag_list, update_catalog, catalog_name):
        # 1. Scan and Filter Files
        self.log("Scanning source folders...")
        valid_files = []
        
        extensions = ['*.wav', '*.mp3', '*.flac', '*.ogg', '*.aiff', '*.aif', '*.aifc', '*.au', '*.snd']
        
        for folder in self.source_folders:
            for ext in extensions:
                # Recursive search (glob ** with recursive=True)
                pattern = os.path.join(folder, "**", ext)
                files = glob.glob(pattern, recursive=True)
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
        
        # Init Classifier if needed
        classifier = None
        if use_autotag:
            self.log(f"Initializing AI Classifier with {len(tag_list)} tags...")
            classifier = AudioClassifier()
            # Trigger load
            classifier.load_model()
            if classifier._pipeline:
                self.log("AI Classifier Ready.")
            else:
                self.log("Failed to load AI Classifier. Proceeding without tagging.")
                use_autotag = False

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
                
                # Spacer
                spacer_width = 1.0 
                
                vol = 0.9
                
                # Render (Phase 1: Temp or Output Root)
                # If tagging, we might move it later. For now save to root of output.
                base_fname = f"{prefix}{i+1:03d}_{int(time.time())}.wav"
                fpath = os.path.join(out_path, base_fname)
                
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
                    final_path = fpath
                    
                    # Phase 2: Classification & Move
                    if use_autotag and classifier:
                        # 2a. Classify
                        tag = classifier.classify(fpath, tag_list)
                        self.log(f"   Classified as: [{tag}]")
                        
                        # 2b. Create Tag Folder
                        tag_dir = os.path.join(out_path, tag)
                        os.makedirs(tag_dir, exist_ok=True)
                        
                        # 2c. Determine new filename based on TAG
                        # Format: TagName_001.wav
                        safe_tag = "".join([c if c.isalnum() else "_" for c in tag])
                        tag_prefix = f"{safe_tag}_"
                        
                        # scan existing in tag_dir using the TAG prefix
                        existing = glob.glob(os.path.join(tag_dir, f"{safe_tag}_*.wav"))
                        
                        max_idx = 0
                        for ef in existing:
                            try:
                                base = os.path.basename(ef)
                                # Expected: Tag_NNN.wav
                                if base.startswith(tag_prefix):
                                    rem = base[len(tag_prefix):]
                                    name_part, _ = os.path.splitext(rem)
                                    if name_part.isdigit():
                                        v = int(name_part)
                                        if v > max_idx: max_idx = v
                            except: pass
                            
                        new_idx = max_idx + 1
                        new_name = f"{safe_tag}_{new_idx:03d}.wav"
                        new_full_path = os.path.join(tag_dir, new_name)
                        
                        # 2d. Move
                        try:
                            shutil.move(fpath, new_full_path)
                            final_path = new_full_path
                            self.log(f"-> Moved to {tag}/{new_name}")
                        except OSError as e:
                            self.log(f"-> Move failed: {e}")
                    else:
                        self.log(f"-> Saved: {base_fname}")

                else:
                    self.log(f"-> Error: {msg}")

            except Exception as e:
                self.log(f"-> Critical Error: {str(e)}")
                
        # --- End of Batch Loop ---
        self.log("Batch processing finished.")
        
        # 3. Catalog Auto-Update
        if update_catalog:
             if not self.stop_event.is_set():
                 full_ods_path = os.path.join(out_path, catalog_name)
                 self.generate_catalog(out_path, full_ods_path)
        
        self.is_running = False
        self.toggle_ui_state(False)

    def on_closing(self):
        # Auto-save before closing
        self.save_history()
        self.destroy()

if __name__ == "__main__":
    app = LazyBatchGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
