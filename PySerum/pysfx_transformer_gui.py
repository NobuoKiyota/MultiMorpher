import customtkinter as ctk
import os
import threading
from tkinter import filedialog
import json
from tkinterdnd2 import TkinterDnD, DND_ALL

from pysfx_transformer_engine import QuartzTransformerEngine
from pysfx_image_tracer import ImageTracer
from pysfx_param_config import PySFXParams

class TransformerGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("Quartz Transformer - WAV Re-Synthesis")
        
        # Load Layout
        self.layout_file = "transformer_layout.json"
        geom = "1000x800"
        if os.path.exists(self.layout_file):
            try:
                with open(self.layout_file, "r") as f:
                    d = json.load(f)
                    geom = d.get("window_size", geom)
            except: pass
        self.geometry(geom)
        
        self.engine = QuartzTransformerEngine()
        self.tracer = ImageTracer()
        self.img_count = self.tracer.get_curve_count()
        self.controls = {}
        
        # Settings File
        self.settings_file = "transformer_settings.json"
        
        self._init_ui()
        self.load_settings()
        
        # Bind Close Event
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def _init_ui(self):
        # 1. Input/Output Area
        frame_io = ctk.CTkFrame(self)
        frame_io.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame_io, text="Source Folder (WAVs):").pack(side="left", padx=5)
        self.ent_input = ctk.CTkEntry(frame_io, width=400)
        self.ent_input.pack(side="left", padx=5)
        
        # DnD Support
        try:
            self.ent_input.drop_target_register(DND_ALL)
            self.ent_input.dnd_bind('<<Drop>>', self.on_drop)
            # Fallback for internal entry if wrapper fails (common in CTk)
            # self.ent_input._entry.drop_target_register(DND_ALL)
            # self.ent_input._entry.dnd_bind('<<Drop>>', self.on_drop)
        except Exception as e:
            print(f"DnD Setup Error: {e}")
            
        ctk.CTkButton(frame_io, text="Browse", command=self.browse_input).pack(side="left", padx=5)
        
        # 2. Parameters
        self.frame_params = ctk.CTkScrollableFrame(self, label_text="Transformation Parameters")
        self.frame_params.pack(fill="both", expand=True, padx=10, pady=5)
        
        self._add_param("Iteration", 1, 50, 10, "生成数")
        self._add_combo("MixMode", ["Random Mix 2", "Single File", "Random Mix 3", "Random Mix 4"], "Mix/Source Mode")
        self._add_param("MorphFreq", 0.1, 10.0, 0.5, "Morphing Speed (Hz)")
        
        self._add_combo("ReverseMode", ["None", "Always", "Random"], "Reverse Mode")
        
        # Image Controlled Params
        # Image Controlled Params (Checkboxes for Random Logic)
        self._add_check("ScratchEnable", False, "Scratch (Random Curve)")
        self._add_check("StretchEnable", False, "TimeStretch (Random Curve)")
        self._add_check("FlutterEnable", False, "Flutter (Random Curve)")
        
        # Effect Params (Reuse names from Factory)
        self._add_param("ReverbTime", 0.1, 10.0, 3.0, "Reverb Time")
        self._add_param("ReverbWet", 0.0, 1.0, 0.0, "Reverb Wet")
        self._add_param("DelayTime", 0.01, 1.0, 0.5, "Delay Time")
        self._add_param("DelayFeedback", 0.0, 0.9, 0.5, "Delay FB")
        self._add_param("DelayWet", 0.0, 1.0, 0.0, "Delay Wet")

        # 3. Actions
        frame_act = ctk.CTkFrame(self)
        frame_act.pack(fill="x", padx=10, pady=10)
        
        self.btn_run = ctk.CTkButton(frame_act, text="Start Transformation", command=self.start_process, 
                                     font=("Arial", 16, "bold"), fg_color="#e04f5f")
        self.btn_run.pack(fill="x", padx=20, pady=10)
        
        self.lbl_status = ctk.CTkLabel(frame_act, text="Ready.")
        self.lbl_status.pack()

    def _add_param(self, name, vmin, vmax, default, label):
        row = ctk.CTkFrame(self.frame_params, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=150, anchor="w").pack(side="left")
        
        var = ctk.StringVar(value=str(default))
        ctk.CTkEntry(row, textvariable=var, width=80).pack(side="left", padx=5)
        # Mousewheel could be added here
        self.controls[name] = var
        
    def _add_combo(self, name, values, label):
        row = ctk.CTkFrame(self.frame_params, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=150, anchor="w").pack(side="left")
        
        var = ctk.StringVar(value=values[0])
        comb = ctk.CTkComboBox(row, values=values, variable=var)
        comb.pack(side="left", padx=5)
        self.controls[name] = var

    def _add_check(self, name, default, label):
        row = ctk.CTkFrame(self.frame_params, fg_color="transparent")
        row.pack(fill="x", pady=2)
        
        var = ctk.BooleanVar(value=default)
        chk = ctk.CTkCheckBox(row, text=label, variable=var)
        chk.pack(side="left", padx=5)
        self.controls[name] = var

    def browse_input(self):
        p = filedialog.askdirectory()
        if p:
            self.ent_input.delete(0, "end")
            self.ent_input.insert(0, p)

    def on_drop(self, event):
        path = event.data
        # Windows DnD often returns {C:/Path With Spaces} or C:/Path
        if path.startswith("{") and path.endswith("}"):
            path = path[1:-1]
        
        self.ent_input.delete(0, "end")
        self.ent_input.insert(0, path)

    def start_process(self):
        src = self.ent_input.get()
        if not os.path.exists(src):
            self.lbl_status.configure(text="Invalid Source Folder", text_color="red")
            return
            
        dst = os.path.join(src, "Transformed")
        
        # Save Settings
        self.save_settings()
        
        # Gather Params
        params = {}
        for k, var in self.controls.items():
            val = var.get()
            # Try float/int/bool
            try: 
                if isinstance(val, bool): pass # Keep bool
                elif "." in val: val = float(val)
                else: val = int(val)
            except: pass
            
            # (Deleted combo parsing logic)
            
            params[k] = val
            
            params[k] = val
            
        self.btn_run.configure(state="disabled")
        self.lbl_status.configure(text="Processing...", text_color="yellow")
        
        def run_t():
            self.engine.process(src, dst, params, progress_cb=self.update_prog)
            self.after(0, self.finish)
            
        threading.Thread(target=run_t).start()

    def update_prog(self, i, total):
        # Thread safe update?
        # CTk usually handles it, but better use after?
        # print(f"{i}/{total}")
        pass

    def finish(self):
        self.lbl_status.configure(text="Complete!", text_color="green")
        self.btn_run.configure(state="normal")

    def save_settings(self):
        data = {}
        # Input Path
        data["input_path"] = self.ent_input.get()
        # Params
        for k, var in self.controls.items():
            data[k] = var.get()
            
        try:
            with open(self.settings_file, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self):
        if not os.path.exists(self.settings_file): return
        try:
            with open(self.settings_file, "r") as f:
                data = json.load(f)
                
            if "input_path" in data:
                self.ent_input.delete(0, "end")
                self.ent_input.insert(0, data["input_path"])
                
            for k, val in data.items():
                if k in self.controls:
                    try: self.controls[k].set(val)
                    except: pass
        except Exception as e:
            print(f"Error loading settings: {e}")

    def on_close(self):
        self.save_settings()
        self.destroy()

if __name__ == "__main__":
    app = TransformerGUI()
    app.mainloop()
