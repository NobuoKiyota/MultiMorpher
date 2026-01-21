import customtkinter as ctk
import json
import os
import sys
import threading
import random
import datetime
from tkinter import filedialog
from pysfx_factory import PyQuartzFactory

SETTINGS_DIR = "Settings"
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "last_session.json")

class RedirectText:
    """標準出力をGUIのテキストボックスに表示するためのクラス"""
    def __init__(self, text_widget):
        self.output = text_widget

    def write(self, string):
        self.output.configure(state="normal")
        self.output.insert("end", string)
        self.output.see("end")
        self.output.configure(state="disabled")

    def flush(self):
        pass

class FactoryGUI(ctk.CTk):
    # --- Layout Configuration ---
    # Users can edit this directly or create 'layout_config.json' to override.
    DEFAULT_LAYOUT = {
        "window_size": "2100x950",
        "column_widths": {
            "Param": 160, # Increased for better visibility
            "Rnd": 30,
            "Val": 60,
            "Min": 50,
            "Max": 50
        },
        "page_padding": 5
    }

    def __init__(self):
        super().__init__()
        
        # Ensure Settings Directory exists
        if not os.path.exists(SETTINGS_DIR):
            os.makedirs(SETTINGS_DIR)
        
        # Load Layout Config
        self.layout_cfg = self.DEFAULT_LAYOUT.copy()
        try:
            if os.path.exists("layout_config.json"):
                with open("layout_config.json", "r") as f:
                    user_cfg = json.load(f)
                    self.layout_cfg.update(user_cfg)
                    # Deep update for nested dicts if needed, or just assume simple structure
                    if "column_widths" in user_cfg:
                        self.layout_cfg["column_widths"].update(user_cfg["column_widths"])
        except Exception as e:
            print(f"Warning: Failed to load layout_config.json: {e}")

        self.title("PyQuartz SFX Factory - Professional Control (5-Page Layout)")
        self.geometry(self.layout_cfg["window_size"]) 
        
        self.factory = PyQuartzFactory()
        self.is_generating = False
        self.controls = {}
        
        self._init_ui()
        self.load_settings()
        
        # Initialize Visibility
        self.toggle_osc_mode()

    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        # Left-aligned Title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", pady=10, padx=20)
        ctk.CTkLabel(title_frame, text="💎 PyQuartz SFX Factory - Professional Control (5-Page Layout)", font=("Arial", 22, "bold")).pack(side="left")

        # Status Label next to Start Button (Created later in layout? No, Button is in Controls?)
        # Let's check where the Button is. Ah, it's NOT in controls dict. 
        # It's usually created at bottom.
        
        # Description Box (Hover Info) - uses Textbox for rich formatting
        self.txt_desc = ctk.CTkTextbox(self, height=70, fg_color="#2b2b2b", corner_radius=5, font=("Meiryo", 12))
        self.txt_desc.pack(fill="x", padx=20, pady=(0, 5))
        self.txt_desc.configure(state="disabled")
        
        # Tag Configurations for Rich Text (Accessing internal _textbox for full Tkinter support)
        self.txt_desc._textbox.tag_config("title", font=("Meiryo", 14, "bold"), foreground="white")
        self.txt_desc._textbox.tag_config("effect", font=("Meiryo", 12), foreground="#dddddd")
        self.txt_desc._textbox.tag_config("guide", font=("Meiryo", 11, "bold"), foreground="#ff5555") # Red for emphasis

        # Main Columns Container (Wide Layout)
        columns_container = ctk.CTkFrame(self, fg_color="transparent")
        columns_container.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Shortcuts for widths
        cw = self.layout_cfg["column_widths"]

        # Helper to create headers (Dynamic Layout)
        def create_headers(parent):
            header_frame = ctk.CTkFrame(parent, fg_color="transparent")
            header_frame.grid(row=0, column=0, sticky="ew", pady=5, padx=2)
            
            headers_def = [
                ("Param", cw["Param"]),       
                ("Rnd", cw["Rnd"]),         
                ("Val", cw["Val"]),       
                ("Min", cw["Min"]),         
                ("Max", cw["Max"]),         
            ]
            for col, (text, w) in enumerate(headers_def):
                lbl = ctk.CTkLabel(header_frame, text=text, font=("Arial", 12, "bold"), width=w)
                lbl.grid(row=0, column=col, padx=2)
            return header_frame

        # Create 5 Columns (Pages 1, 2, 3, 4, 5)
        self.page_frames = {}
        for i in range(1, 6): # Pages 1 to 5
            # Frame for column
            col_frame = ctk.CTkFrame(columns_container, fg_color="transparent")
            col_frame.pack(side="left", fill="both", expand=True, padx=2)
            
            # Page Title (Optional, but helpful)
            page_titles = {1: "OSC & Voice", 2: "LFOs", 3: "Filters", 4: "Effects", 5: "Advanced"}
            ctk.CTkLabel(col_frame, text=f"Page {i}: {page_titles.get(i,'')}", font=("Arial", 12, "bold")).pack()
            
            # Page 1: Add OSC:A Mode Switch
            if i == 1:
                self.var_osc_a = ctk.BooleanVar(value=False)
                self.sw_osc_a = ctk.CTkSwitch(col_frame, text="OSC:A (Detail)", variable=self.var_osc_a, 
                                              command=self.toggle_osc_mode, font=("Arial", 12, "bold"))
                self.sw_osc_a.pack(pady=5, padx=10, anchor="w")

            # Page 2: Add OSC:B Mode Switch
            if i == 2:
                self.var_osc_b = ctk.BooleanVar(value=False)
                self.sw_osc_b = ctk.CTkSwitch(col_frame, text="OSC:B (Detail)", variable=self.var_osc_b, 
                                              command=self.toggle_osc_mode, font=("Arial", 12, "bold"))
                self.sw_osc_b.pack(pady=5, padx=10, anchor="w")

            # Scrollable Frame inside
            sf = ctk.CTkScrollableFrame(col_frame)
            sf.pack(fill="both", expand=True)
            
            create_headers(sf)
            self.page_frames[str(i)] = sf

        # パラメータ定義 (Centralized Config)
        from pysfx_param_config import PySFXParams
        from pysfx_color_config import PySFXColors
        from pysfx_param_docs import PARAM_DOCS # Import external docs
        sorted_params = PySFXParams.get_sorted_params()
        
        for i, p in enumerate(sorted_params, 1):
            page_id = str(getattr(p, 'page', 1)) # Default to 1 if missing
            
            if page_id not in self.page_frames:
               continue
                
            target_frame = self.page_frames[page_id]
            current_rows = len(target_frame.winfo_children()) 
            
            name = p.name
            v_min = p.min
            v_max = p.max
            default = p.default
            # note = p.desc # Use external docs instead
            
            # Row Color
            bg_color = PySFXColors.get_color(p.group)
            
            row_frame = ctk.CTkFrame(target_frame, fg_color=bg_color, corner_radius=0)
            row_frame.grid(row=current_rows, column=0, sticky="ew", pady=1, padx=2)
            
            # Col 0: Name (Dynamic Width)
            display_name = name.replace("OSC:A:", "").replace("OSC:B:", "") # Strip prefixes for display
            lbl_name = ctk.CTkLabel(row_frame, text=display_name, width=cw["Param"], anchor="w")
            lbl_name.grid(row=0, column=0, padx=5, pady=2)
            
            # Hover Event Binding
            def show_doc(e, n=name):
                doc = PARAM_DOCS.get(n, {"desc": "No description available."})
                
                self.txt_desc.configure(state="normal")
                self.txt_desc.delete("1.0", "end")
                
                # Title Inline
                self.txt_desc.insert("end", f"【 {n} 】：", "title")
                
                # Body (Desc)
                if "desc" in doc:
                    self.txt_desc.insert("end", doc['desc'], "effect")
                    
                # Effect
                if "effect" in doc and doc["effect"]:
                    self.txt_desc.insert("end", " " + doc['effect'], "effect")
                
                # Guide (Red/Bold) - Append inline
                if "guide" in doc and doc["guide"]:
                    self.txt_desc.insert("end", " " + doc['guide'], "guide")
                    
                self.txt_desc.configure(state="disabled")
            
            def clear_doc(e):
                self.txt_desc.configure(state="normal")
                self.txt_desc.delete("1.0", "end")
                self.txt_desc.insert("end", "Hover over a parameter to see details...")
                self.txt_desc.configure(state="disabled")
                
            # Recursively bind hover events to all widgets in the row
            def bind_hover(widget):
                widget.bind("<Enter>", show_doc)
                widget.bind("<Leave>", clear_doc)
                for child in widget.winfo_children():
                    bind_hover(child)
            
            # Initial binding (Label is child, so will be bound)
            # But we create widgets AFTER this block.
            # We should bind AFTER all widgets are created.
            # Or bind row_frame now, and others later?
            # Events bubble? Tkinter events don't bubble nicely for Enter/Leave.
            # We must bind to EACH widget.
            
            # Let's define the binder helper and call it at end of loop iteration.
            
            
            row_data = {
                "frame": row_frame,
                "page": page_id
            }

            # Col 1: Random (Dynamic Width)
            var_rnd = ctk.BooleanVar(value=False)
            chk_rnd = ctk.CTkCheckBox(row_frame, text="", variable=var_rnd, width=cw["Rnd"],
                                      command=lambda n=name: self.toggle_row(n))
            chk_rnd.grid(row=0, column=1, padx=2, pady=2)
            row_data["random"] = var_rnd
            
            # Col 2: Value (Dynamic Width)
            if v_min is None: # Boolean Check
                var_val = ctk.BooleanVar(value=default)
                ent_val = ctk.CTkCheckBox(row_frame, text="ON", variable=var_val, width=cw["Val"])
                chk_rnd.configure(state="disabled")
                row_data["value"] = var_val
            else: # Entry
                var_val = ctk.StringVar(value=str(default))
                ent_val = ctk.CTkEntry(row_frame, textvariable=var_val, width=cw["Val"])
                row_data["value"] = var_val

            ent_val.grid(row=0, column=2, padx=2, pady=2)
            row_data["ent_val"] = ent_val

            # Col 3, 4: Min/Max (Dynamic Width)
            var_min_tk = None
            var_max_tk = None
            
            if v_min is not None:
                var_min_tk = ctk.StringVar(value=str(v_min))
                var_max_tk = ctk.StringVar(value=str(v_max))
                ent_min = ctk.CTkEntry(row_frame, textvariable=var_min_tk, width=cw["Min"])
                ent_max = ctk.CTkEntry(row_frame, textvariable=var_max_tk, width=cw["Max"])
                ent_min.grid(row=0, column=3, padx=2, pady=2)
                ent_max.grid(row=0, column=4, padx=2, pady=2)
                row_data["min"] = var_min_tk
                row_data["max"] = var_max_tk
                row_data["ent_min"] = ent_min
                row_data["ent_max"] = ent_max
            else:
                ctk.CTkLabel(row_frame, text="", width=cw["Min"]).grid(row=0, column=3)
                ctk.CTkLabel(row_frame, text="", width=cw["Max"]).grid(row=0, column=4)

            # --- Wheel Support Logic with Safety ---
            if v_min is not None: # Not boolean
                # Helper to get float from var
                def get_f(v): 
                    try: return float(v.get())
                    except: return 0.0

                def on_wheel(e, target_var, mode="val", h_min=v_min, h_max=v_max):
                    # Determine current value
                    try: curr = float(target_var.get())
                    except: return

                    # Determine Bounds and Step
                    hard_min, hard_max = h_min, h_max
                    
                    # Safety check if somehow None passed
                    if hard_min is None: hard_min = 0.0
                    if hard_max is None: hard_max = 100.0
                    
                    soft_min, soft_max = hard_min, hard_max
                    
                    if mode == "min":
                        # Adjusting Min: Upper bound is 'Max Entry' value
                        if var_max_tk: soft_max = get_f(var_max_tk)
                    elif mode == "max":
                        # Adjusting Max: Lower bound is 'Min Entry' value
                        if var_min_tk: soft_min = get_f(var_min_tk)
                    
                    # Ensure Soft Limits don't exceed Hard Limits (Safety)
                    # soft_min should be >= hard_min
                    if soft_min < hard_min: soft_min = hard_min
                    
                    # soft_max should be <= hard_max
                    if soft_max > hard_max: soft_max = hard_max

                    # Correct Step Logic
                    is_int_param = isinstance(h_min, int) and isinstance(h_max, int)
                    
                    step = 0.1
                    if is_int_param:
                        step = 1.0
                    elif (hard_max - hard_min) <= 2.0:
                        step = 0.01

                    # Apply
                    if e.delta > 0: curr += step
                    else: curr -= step
                    
                    # Clamp
                    if mode == "val":
                         curr = max(hard_min, min(hard_max, curr))
                    else:
                         curr = max(soft_min, min(soft_max, curr))
                    
                    # Format
                    if is_int_param:
                        target_var.set(str(int(curr)))
                    else:
                        target_var.set(f"{curr:.2f}")

                # Bindings
                # Note: We use default args to capture current variables
                # if "ent_val" in row_data and isinstance(row_data["ent_val"], ctk.CTkEntry):
                #     row_data["ent_val"].bind("<MouseWheel>", lambda e, v=var_val: on_wheel(e, v, "val"))
                
                # if var_min_tk and var_max_tk:
                #     ent_min.bind("<MouseWheel>", lambda e, v=var_min_tk: on_wheel(e, v, "min"))
                #     ent_max.bind("<MouseWheel>", lambda e, v=var_max_tk: on_wheel(e, v, "max"))
            
            # Double Click Reset
            def on_reset(e, v=var_val, d=default):
                v.set(str(d))
            lbl_name.bind("<Double-Button-1>", on_reset)
            
            self.controls[name] = row_data
            self.toggle_row(name)
            
            # Bind Hover to EVERYTHING in row_frame
            bind_hover(row_frame)


        # 実行コントロール (Compact)
        # Bottom Controls Frame (Replacing frm_exec)
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=20, pady=10)
        
        # Qty
        ctk.CTkLabel(bottom_frame, text="Qty:", font=("Arial", 14)).pack(side="left", padx=5)
        self.ent_qty = ctk.CTkEntry(bottom_frame, width=60)
        self.ent_qty.insert(0, "10")
        self.ent_qty.pack(side="left", padx=5)
        
        # Run Button
        self.btn_run = ctk.CTkButton(bottom_frame, text="Start Production", command=self.start, 
                                     font=("Arial", 16, "bold"), height=40, fg_color="#e04f5f", hover_color="#c03f4f")
        self.btn_run.pack(side="left", padx=10)
        
        # Random
        self.btn_rnd = ctk.CTkButton(bottom_frame, text="Random Gen", command=self.start_random, 
                                     font=("Arial", 12, "bold"), height=30, width=100, fg_color="#00BCD4")
        self.btn_rnd.pack(side="left", padx=5)
        
        # Similar (Clone)
        self.btn_sim = ctk.CTkButton(bottom_frame, text="Clone High", command=self.start_similar, 
                                     font=("Arial", 12, "bold"), height=30, width=100, fg_color="#FFA000")
        self.btn_sim.pack(side="left", padx=5)
        
        # Mix (Hybrid)
        self.btn_mix = ctk.CTkButton(bottom_frame, text="Mix High", command=self.start_hybrid, 
                                     font=("Arial", 12, "bold"), height=30, width=100, fg_color="#7B1FA2")
        self.btn_mix.pack(side="left", padx=5)
        
        # Status Label (Animation)
        self.lbl_status = ctk.CTkLabel(bottom_frame, text="", font=("Courier New", 16, "bold"), text_color="#00ff00")
        self.lbl_status.pack(side="left", padx=10)
        
        # Right Side Controls (Load/Save/Reset)
        ctk.CTkButton(bottom_frame, text="Load", command=self.load_preset_dialog, fg_color="#444", width=60).pack(side="right", padx=5)
        ctk.CTkButton(bottom_frame, text="Save", command=self.save_preset_dialog, fg_color="#444", width=60).pack(side="right", padx=5)
        
        # Reset Button (Right)
        ctk.CTkButton(bottom_frame, text="Reset", command=self.reset_defaults, 
                      fg_color="#555555", width=60).pack(side="right", padx=5)

        # Reviewer Button (New)
        ctk.CTkButton(bottom_frame, text="Reviewer", command=self.open_reviewer,
                      fg_color="#4CAF50", width=80).pack(side="right", padx=5)

        self.txt_log = ctk.CTkTextbox(self, height=60)
        self.txt_log.pack(pady=5, padx=10, fill="x")
        sys.stdout = RedirectText(self.txt_log)

    def open_reviewer(self):
        # Determine Factory Output Directory
        # By default it is "Output" relative to script
        target_dir = os.path.join(os.getcwd(), "Output")
        reviewer_script = "sfx_reviewer_app.py"
        if not os.path.exists(reviewer_script):
            print("Error: Reviewer script not found in current directory.")
            return
            
        import subprocess
        try:
            # Launch Reviewer pointing to Output
            cmd = f'start cmd /k "python {reviewer_script} "{target_dir}""'
            subprocess.Popen(cmd, shell=True)
            print("Launching Reviewer...")
        except Exception as e:
            print(f"Error launching reviewer: {e}")

    def toggle_row(self, name):
        ctrl = self.controls[name]
        is_rnd = ctrl["random"].get()
        if "ent_val" in ctrl:
            ctrl["ent_val"].configure(state="disabled" if is_rnd else "normal")
        if "ent_min" in ctrl:
            st = "normal" if is_rnd else "disabled"
            ctrl["ent_min"].configure(state=st); ctrl["ent_max"].configure(state=st)

    def toggle_osc_mode(self):
        """Switch between Normal View and OSC Detail Views"""
        is_osc_a = self.var_osc_a.get()
        try: is_osc_b = self.var_osc_b.get()
        except: is_osc_b = False
        
        for name, ctrl in self.controls.items():
            page_id = ctrl.get("page")
            frame = ctrl["frame"]
            
            if page_id == "1":
                # Page 1 Logic (OSC:A vs Basic)
                is_detail_a = name.startswith("OSC:A:")
                if is_detail_a:
                    if is_osc_a: frame.grid()
                    else: frame.grid_remove()
                else:
                    if is_osc_a: frame.grid_remove() # Hide Basic when Detail ON? Or keep Basic? 
                    # User requested 'Back' (ura). Typically means flip.
                    # So Hide parameters that are NOT OSC:A Detail?
                    # But Basic params (Voices, Duration) are important.
                    # Let's hide NON-OSC:A params IF they are obstructing?
                    # Actually, Page 1 has Basic + OSC:A Master.
                    # "OSC:A:" params are HIDDEN by default.
                    # If ON, SHOW "OSC:A:".
                    # Should we HIDE Basic? User didn't specify. 
                    # "裏に配置" implies flip. Let's hide others to save space or just append?
                    # Current logic: Hides Normal params if OSC is ON?
                    # Wait, old logic:
                    # if is_detail: show if osc else hide
                    # else: show if NOT osc else hide.
                    # This means it replaces the view. Correct.
                    if is_osc_a: frame.grid_remove()
                    else: frame.grid()

            elif page_id == "2":
                # Page 2 Logic (OSC:B vs LFOs)
                is_detail_b = name.startswith("OSC:B:")
                if is_detail_b:
                    if is_osc_b: frame.grid()
                    else: frame.grid_remove()
                else:
                    # LFOs are Normal Page 2.
                    if is_osc_b: frame.grid_remove()
                    else: frame.grid()

    def save_settings(self, filepath=SETTINGS_FILE):
        data = {name: {k: v.get() for k, v in ctrl.items() if not k.startswith("ent") and k not in ("frame", "page")} 
                for name, ctrl in self.controls.items()}
        try:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Settings saved to {filepath}")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self, filepath=SETTINGS_FILE):
        if not os.path.exists(filepath): return
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
                self._apply_settings_data(data)
            print(f"Settings loaded from {filepath}")
        except Exception as e:
            print(f"Error loading settings: {e}")

    def _apply_settings_data(self, data):
        for name, vals in data.items():
            if name in self.controls:
                for k, v in vals.items(): 
                    if k in self.controls[name]:
                        # Safety for boolean/string vars
                        try: self.controls[name][k].set(v)
                        except: pass
                self.toggle_row(name)

    def load_preset_dialog(self):
        ftypes = [("JSON Files", "*.json"), ("All Files", "*.*")]
        path = filedialog.askopenfilename(initialdir=SETTINGS_DIR, title="Load Preset", filetypes=ftypes)
        if path:
            self.load_settings(path)

    def save_preset_dialog(self):
        ftypes = [("JSON Files", "*.json"), ("All Files", "*.*")]
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        initial = f"Preset_{timestamp}.json"
        path = filedialog.asksaveasfilename(initialdir=SETTINGS_DIR, initialfile=initial, title="Save Preset", filetypes=ftypes, defaultextension=".json")
        if path:
            self.save_settings(path)

    def reset_defaults(self):
        # 設定ファイルを削除して再起動... ではなく、本来はデフォルト値をリロードすべきだが
        # 簡易的にセッションファイルを消して再起動を促す
        if os.path.exists(SETTINGS_FILE): os.remove(SETTINGS_FILE)
        print("Settings reset. Please restart application.")

    def start(self, override_config=None):
        if self.is_generating: return
        
        # 1. Save Last Session
        self.save_settings(SETTINGS_FILE)
        
        try:
            qty = int(self.ent_qty.get())
        except:
            print("Error: Invalid Quantity")
            return

        if override_config:
             config = override_config
             print("Starting with Override Config (Random/Sim/Mix)")
        else:
             config = {name: {k: v.get() for k, v in ctrl.items() if not k.startswith("ent") and k not in ("frame", "page")} 
                       for name, ctrl in self.controls.items()}
        
        self.btn_run.configure(state="disabled", text="Generating...")
        self.lbl_status.configure(text="Starting...")
        self.is_generating = True
        
        # Animation Frames
        self.anim_frames = [
            "(>-------)", "(->------)", "(-->-----)", "(--->----)", 
            "(---->---)", "(----->--)", "(------>-)", "(-------<)",
            "(------<-)", "(-----<--)", "(----<---)", "(---<----)", 
            "(--<-----)", "(-<------)"
        ]
        self.anim_idx = 0
        self._animate_progress()

        def prog_cb(idx, total):
            pass

        def run_thread():
            self.factory.run_advanced_batch(config, qty, progress_callback=prog_cb)
            self.after(0, self.finish)
            
        threading.Thread(target=run_thread).start()

    def _animate_progress(self):
        if not self.is_generating: return
        
        txt = self.anim_frames[self.anim_idx % len(self.anim_frames)]
        self.lbl_status.configure(text=txt)
        self.anim_idx += 1
        self.after(100, self._animate_progress)

    def finish(self):
        self.is_generating = False
        self.lbl_status.configure(text="Complete!")
        self.btn_run.configure(state="normal", text="Start Production")
        
    def start_random(self):
        cfg = self.factory.get_random_config()
        self.start(override_config=cfg)

    def start_similar(self):
        favs = self.factory.load_favorites(min_score=8)
        if not favs:
            print("No favorites found (Score >= 8)")
            self.lbl_status.configure(text="No High Scores!")
            return
        
        top = favs[:5] if len(favs) > 5 else favs
        entry = random.choice(top)
        
        cfg = self.factory.get_similar_config(entry)
        self.start(override_config=cfg)

    def start_hybrid(self):
        favs = self.factory.load_favorites(min_score=8)
        if len(favs) < 2:
            print("Need at least 2 favorites (Score >= 8)")
            self.lbl_status.configure(text="Need 2+ Favs!")
            return
            
        top = favs[:10] if len(favs) > 10 else favs
        e1, e2 = random.sample(top, 2)
        
        cfg = self.factory.get_hybrid_config(e1, e2)
        self.start(override_config=cfg)

if __name__ == "__main__":
    app = FactoryGUI()
    app.mainloop()