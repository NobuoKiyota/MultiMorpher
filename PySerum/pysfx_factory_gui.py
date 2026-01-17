import customtkinter as ctk
import json
import os
import sys
import threading
import random
from pysfx_factory import PyQuartzFactory

SETTINGS_FILE = "factory_settings.json"

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
    # Dynamic Column Width Config
    COL_WIDTHS = {
        "Param": 140,
        "Rnd": 30,
        "Val": 50,
        "Min": 50,
        "Max": 50
    }

    def __init__(self):
        super().__init__()
        self.title("PyQuartz SFX Factory - Professional Control (Wide Mode)")
        self.geometry("1800x900") # Expanded geometry for breathing room
        
        self.factory = PyQuartzFactory()
        self.is_generating = False
        self.controls = {}
        
        self._init_ui()
        self.load_settings()

    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        # Left-aligned Title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", pady=10, padx=20)
        ctk.CTkLabel(title_frame, text="💎 PyQuartz Advanced Control Panel", font=("Arial", 22, "bold")).pack(side="left")

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
        cw = self.COL_WIDTHS

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

        # Create 4 Columns (Pages 1, 2, 3, 4)
        self.page_frames = {}
        for i in range(1, 5): # Pages 1, 2, 3, 4
            # Frame for column
            col_frame = ctk.CTkFrame(columns_container, fg_color="transparent")
            col_frame.pack(side="left", fill="both", expand=True, padx=2)
            
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
            lbl_name = ctk.CTkLabel(row_frame, text=name, width=cw["Param"], anchor="w")
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
                
            lbl_name.bind("<Enter>", show_doc)
            lbl_name.bind("<Leave>", clear_doc)
            
            row_data = {}

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

                def on_wheel(e, target_var, mode="val"):
                    # Determine current value
                    try: curr = float(target_var.get())
                    except: return

                    # Determine Bounds and Step
                    hard_min, hard_max = v_min, v_max
                    soft_min, soft_max = hard_min, hard_max
                    
                    if mode == "min":
                        # Adjusting Min: Upper bound is 'Max Entry' value
                        if var_max_tk: soft_max = get_f(var_max_tk)
                    elif mode == "max":
                        # Adjusting Max: Lower bound is 'Min Entry' value
                        if var_min_tk: soft_min = get_f(var_min_tk)
                    
                    # Ensure Soft Limits don't exceed Hard Limits (Safety)
                    soft_min = max(hard_min, soft_min)
                    soft_max = min(hard_max, soft_max)

                    # Step Size Calculation
                    step = 0.1
                    if isinstance(hard_min, int) and isinstance(hard_max, int): step = 1
                    elif (hard_max - hard_min) <= 2.0: step = 0.01
                    
                    # Apply
                    if e.delta > 0: curr += step
                    else: curr -= step
                    
                    # Clamp
                    # For Val: Clamp between Hard Limits
                    # For Min: Clamp between HardMin and SoftMax (Max Entry)
                    # For Max: Clamp between SoftMin (Min Entry) and HardMax
                    if mode == "val":
                         curr = max(hard_min, min(hard_max, curr))
                    else:
                         curr = max(soft_min, min(soft_max, curr))
                    
                    # Set
                    if isinstance(hard_min, int): target_var.set(str(int(curr)))
                    else: target_var.set(f"{curr:.2f}")

                # Bindings
                # Note: We use default args to capture current variables
                if "ent_val" in row_data and isinstance(row_data["ent_val"], ctk.CTkEntry):
                    row_data["ent_val"].bind("<MouseWheel>", lambda e, v=var_val: on_wheel(e, v, "val"))
                
                if var_min_tk and var_max_tk:
                    ent_min.bind("<MouseWheel>", lambda e, v=var_min_tk: on_wheel(e, v, "min"))
                    ent_max.bind("<MouseWheel>", lambda e, v=var_max_tk: on_wheel(e, v, "max"))
            
            # Double Click Reset
            def on_reset(e, v=var_val, d=default):
                v.set(str(d))
            lbl_name.bind("<Double-Button-1>", on_reset)
            
            self.controls[name] = row_data
            self.toggle_row(name)


        # 実行コントロール (Compact)
        self.frm_exec = ctk.CTkFrame(self, fg_color="transparent")
        self.frm_exec.pack(pady=5, fill="x", padx=40)
        
        self.btn_reset = ctk.CTkButton(self.frm_exec, text="Default Reset", fg_color="#555", width=100, height=24, command=self.reset_defaults)
        self.btn_reset.pack(side="left", padx=10)

        ctk.CTkLabel(self.frm_exec, text="Qty:").pack(side="left", padx=5)
        self.ent_qty = ctk.CTkEntry(self.frm_exec, width=50)
        self.ent_qty.insert(0, "10")
        self.ent_qty.pack(side="left", padx=5)

        self.btn_run = ctk.CTkButton(self.frm_exec, text="🚀 Start Production", height=32, font=("Arial", 14, "bold"), command=self.start)
        self.btn_run.pack(side="right", expand=True, fill="x", padx=10)

        # ログ出力 (Small)
        self.txt_log = ctk.CTkTextbox(self, height=60)
        self.txt_log.pack(pady=5, padx=10, fill="x")
        sys.stdout = RedirectText(self.txt_log)

    def toggle_row(self, name):
        ctrl = self.controls[name]
        is_rnd = ctrl["random"].get()
        if "ent_val" in ctrl:
            ctrl["ent_val"].configure(state="disabled" if is_rnd else "normal")
        if "ent_min" in ctrl:
            st = "normal" if is_rnd else "disabled"
            ctrl["ent_min"].configure(state=st); ctrl["ent_max"].configure(state=st)

    def save_settings(self):
        data = {name: {k: v.get() for k, v in ctrl.items() if not k.startswith("ent")} 
                for name, ctrl in self.controls.items()}
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f)

    def load_settings(self):
        if not os.path.exists(SETTINGS_FILE): return
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                for name, vals in data.items():
                    if name in self.controls:
                        for k, v in vals.items(): self.controls[name][k].set(v)
                        self.toggle_row(name)
        except: pass

    def reset_defaults(self):
        # 設定ファイルを削除して再起動と同じ状態にするか、手動で初期値をセット
        if os.path.exists(SETTINGS_FILE): os.remove(SETTINGS_FILE)
        print("Settings reset. Please restart application.")

    def start(self):
        if self.is_generating: return
        self.save_settings()
        
        try:
            qty = int(self.ent_qty.get())
        except:
            print("Error: Invalid Quantity")
            return

        config = {name: {k: v.get() for k, v in ctrl.items() if not k.startswith("ent")} 
                  for name, ctrl in self.controls.items()}
        
        self.btn_run.configure(state="disabled", text="Generating...")
        self.is_generating = True
        
        def run_thread():
            self.factory.run_advanced_batch(config, qty)
            self.after(0, self.finish)
            
        threading.Thread(target=run_thread).start()

    def finish(self):
        self.is_generating = False
        self.btn_run.configure(state="normal", text="🚀 Start Production")

if __name__ == "__main__":
    app = FactoryGUI()
    app.mainloop()