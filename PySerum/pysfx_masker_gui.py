import customtkinter as ctk
import os
import threading
from tkinter import filedialog
import json
import random
from tkinterdnd2 import TkinterDnD, DND_ALL

from pysfx_masker_engine import QuartzMaskerEngine
from pysfx_color_config import PySFXColors

# Param Definitions
MASKER_PARAMS = [
    {"name": "NoiseType", "default": "White", "group": "Distortion", "type": "combo", "values": ["White", "Pink", "Brown", "Random"],
     "desc": "マスキングに使用するノイズの色を選択します。",
     "effect": "White: 全帯域均一。Pink: 自然な減衰。Brown: 低域重視。Random: ファイル毎にランダム。",
     "guide": "通常はPinkが自然な質感に適しています。大量バリエーション作成にはRandom推奨。"},
    {"name": "MaskAmount", "default": 0.5, "min": 0.0, "max": 1.0, "group": "Envelope", "type": "float", 
     "desc": "原音とノイズのクロスフェード比率。",
     "effect": "0.0: 原音のみ。 1.0: ノイズのみ（エンベロープ追従）。 0.5: 均等ミックス。",
     "guide": "値を上げると音程感が失われ、リズムと抑揚のみが残ります。"},
    {"name": "FadeLen", "default": 0.1, "min": 0.0, "max": 0.5, "group": "Reverb", "type": "float", 
     "desc": "フェードイン/アウトの長さ。",
     "effect": "全体長に対する比率。0.1なら前後10%ずつフェードがかかります。",
     "guide": "Reverseモード時のクリックノイズ防止に必須です。"},
    {"name": "InvertProb", "default": 0.0, "min": 0.0, "max": 1.0, "group": "Stereo", "type": "float", 
     "desc": "位相の反転確率 (0.0-1.0)。",
     "effect": "設定した確率で、ソースの位相を反転させてからミックスします。",
     "guide": "ノイズとの位相干渉による音質変化をランダムに生み出します。"},
    {"name": "ReverseProb", "default": 0.0, "min": 0.0, "max": 1.0, "group": "Stereo", "type": "float", 
     "desc": "スマートリバース処理の発生確率 (0.0-1.0)。",
     "effect": "設定した確率で、ミックス全体を逆再生します。",
     "guide": "吸い込み音や爆発の収縮など、SFX的な動きをランダムに追加します。"},
    {"name": "FilterLinkProb", "default": 0.0, "min": 0.0, "max": 1.0, "group": "Stereo", "type": "float", 
     "desc": "実験的スペクトラルトラッキングの発生確率 (0.0-1.0)。",
     "effect": "設定した確率で、入力の強弱に応じてノイズの明るさを動的に変化させます。",
     "guide": "現在エンジンの実装は簡易的/WIPです。"}
]

class MaskerGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("Quartz Noise Masker - Texture Generator")
        self.geometry("480x600")
        
        self.engine = QuartzMaskerEngine()
        self.settings_file = "masker_settings.json"
        
        self.controls = {} # {name: {val: var, min: var, max: var, rnd: var}}
        self.is_generating = False
        self._hover_job = None
        
        self._init_ui()
        self.load_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def _init_ui(self):
        # 1. Input
        frame_in = ctk.CTkFrame(self)
        frame_in.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame_in, text="Input:").pack(side="left", padx=5)
        
        self.ent_input = ctk.CTkEntry(frame_in, width=200) # Slightly narrower for 400px width
        self.ent_input.pack(side="left", padx=5, fill="x", expand=True)
        self.ent_input.drop_target_register(DND_ALL)
        self.ent_input.dnd_bind('<<Drop>>', self.on_drop)
        
        ctk.CTkButton(frame_in, text="...", width=40, command=self.browse_input).pack(side="left", padx=5)
        
        # 2. Params Header
        self.frame_params = ctk.CTkScrollableFrame(self, label_text="Parameters")
        self.frame_params.pack(fill="both", expand=True, padx=10, pady=5)
        
        self._create_headers()
        
        # 3. Create Rows
        for p in MASKER_PARAMS:
            self._create_row(p)
            
        # Description Box
        self.txt_desc = ctk.CTkTextbox(self, height=110, fg_color="transparent", text_color="#aaa")
        self.txt_desc.pack(fill="x", padx=10, pady=5)
        self.txt_desc.insert("1.0", "Hover over parameters for details...")
        
        self.txt_desc.tag_config("title", foreground="#ffffff")
        self.txt_desc.tag_config("desc", foreground="#dddddd")
        self.txt_desc.tag_config("effect", foreground="#a0a0ff")
        self.txt_desc.tag_config("guide", foreground="#ffaaaa")
        
        self.txt_desc.configure(state="disabled")

        # 4. Action
        self.btn_run = ctk.CTkButton(self, text="Execute Masking", 
                                     font=("Arial", 16, "bold"), fg_color="#a04fe0", height=50,
                                     command=self.start_process)
        self.btn_run.pack(fill="x", padx=20, pady=20)
        
        self.lbl_status = ctk.CTkLabel(self, text="Ready.")
        self.lbl_status.pack(pady=5)

    def _create_headers(self):
        h_frame = ctk.CTkFrame(self.frame_params, fg_color="transparent")
        h_frame.pack(fill="x")
        ctk.CTkLabel(h_frame, text="Param", width=120, anchor="w", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=5) # Narrower
        ctk.CTkLabel(h_frame, text="Rnd", width=30, font=("Arial", 12, "bold")).grid(row=0, column=1, padx=2)
        ctk.CTkLabel(h_frame, text="Val", width=60, font=("Arial", 12, "bold")).grid(row=0, column=2, padx=2)
        ctk.CTkLabel(h_frame, text="Min", width=50, font=("Arial", 12, "bold")).grid(row=0, column=3, padx=2)
        ctk.CTkLabel(h_frame, text="Max", width=50, font=("Arial", 12, "bold")).grid(row=0, column=4, padx=2)
    def _create_row(self, p):
        name = p["name"]
        color = PySFXColors.get_color(p["group"])
        
        row = ctk.CTkFrame(self.frame_params, fg_color=color)
        row.pack(fill="x", pady=1)
        
        # Col 0: Name
        lbl = ctk.CTkLabel(row, text=name, width=150, anchor="w")
        lbl.grid(row=0, column=0, padx=5, pady=2)
        
        data = {}
        
        # Col 1: Rnd
        var_rnd = ctk.BooleanVar(value=False)
        chk_rnd = ctk.CTkCheckBox(row, text="", variable=var_rnd, width=30, command=lambda n=name: self._toggle_row(n))
        chk_rnd.grid(row=0, column=1, padx=2)
        data["rnd"] = var_rnd
        
        # Col 2: Val
        # Use StringVar for all to match Transformer GUI stability
        if p["type"] == "combo":
            var_val = ctk.StringVar(value=str(p["default"]))
            widget_val = ctk.CTkComboBox(row, values=p["values"], variable=var_val, width=80)
            chk_rnd.configure(state="disabled") 
        elif p["type"] == "int":
             var_val = ctk.StringVar(value=str(p["default"]))
             widget_val = ctk.CTkEntry(row, textvariable=var_val, width=80)
             # If strictly int param, handle Rnd if applicable
        else: # float
            var_val = ctk.StringVar(value=str(p["default"]))
            widget_val = ctk.CTkEntry(row, textvariable=var_val, width=80)
            widget_val.bind("<MouseWheel>", lambda e, v=var_val: self._on_wheel(e, v))
            
        widget_val.grid(row=0, column=2, padx=2)
        data["val"] = var_val
        
        # Col 3, 4: Min/Max
        if p["type"] in ["float", "int"]:
            var_min = ctk.StringVar(value=str(p.get("min", 0.0)))
            var_max = ctk.StringVar(value=str(p.get("max", 1.0)))
            ent_min = ctk.CTkEntry(row, textvariable=var_min, width=60)
            ent_max = ctk.CTkEntry(row, textvariable=var_max, width=60)
            ent_min.grid(row=0, column=3, padx=2)
            ent_max.grid(row=0, column=4, padx=2)
            
            ent_min.bind("<MouseWheel>", lambda e, v=var_min: self._on_wheel(e, v))
            ent_max.bind("<MouseWheel>", lambda e, v=var_max: self._on_wheel(e, v))
            
            data["min"] = var_min
            data["max"] = var_max
            data["widget_val"] = widget_val # To disable
            data["widget_min"] = ent_min
            data["widget_max"] = ent_max
            
        else:
            # Empty for Combo
            ctk.CTkLabel(row, text="", width=60).grid(row=0, column=3)
            ctk.CTkLabel(row, text="", width=60).grid(row=0, column=4)
            
        self.controls[name] = data
        self._toggle_row(name) # Init state
        
        # Bind Hover to Row and *ALL* children for continuous coverage
        self._bind_hover(row, p)
        for child in row.winfo_children():
            self._bind_hover(child, p)

    def _toggle_row(self, name):
        # Enable/Disable based on Rnd
        ctrl = self.controls[name]
        is_rnd = ctrl["rnd"].get()
        
        if "widget_min" in ctrl: # Float param
            state_range = "normal" if is_rnd else "disabled"
            state_val = "disabled" if is_rnd else "normal"
            
            ctrl["widget_min"].configure(state=state_range)
            ctrl["widget_max"].configure(state=state_range)
            ctrl["widget_val"].configure(state=state_val)

    def _on_wheel(self, event, var):
        try:
            val_str = var.get()
            if not val_str: val = 0.0
            else: val = float(val_str)
            
            step = 0.01 if abs(event.delta) < 120 else 0.05
            if event.delta < 0: step *= -1
            
            new_val = round(val + step, 3)
            var.set(str(new_val))
        except: pass

    def _bind_hover(self, widget, p_data):
        widget.bind("<Enter>", lambda e: self._show_desc(p_data))
        widget.bind("<Leave>", lambda e: self._clear_desc())

    def _show_desc(self, p_data):
        if self._hover_job:
            self.after_cancel(self._hover_job)
            self._hover_job = None
            
        self.txt_desc.configure(state="normal")
        self.txt_desc.delete("1.0", "end")
        
        # Insert Rich Text
        name = p_data.get("name", "Param")
        self.txt_desc.insert("end", f"【 {name} 】\n", "title")
        
        if "desc" in p_data:
            self.txt_desc.insert("end", f"{p_data['desc']}\n", "desc")
            
        if "effect" in p_data:
            self.txt_desc.insert("end", f"Effect: {p_data['effect']}\n", "effect")
            
        if "guide" in p_data:
            self.txt_desc.insert("end", f"Guide: {p_data['guide']}", "guide")
            
        self.txt_desc.configure(state="disabled")
        
    def _clear_desc(self):
        # Debounce to prevent flicker when moving between children
        if self._hover_job:
            self.after_cancel(self._hover_job)
        self._hover_job = self.after(50, self._perform_clear_desc)

    def _perform_clear_desc(self):
        self.txt_desc.configure(state="normal")
        self.txt_desc.delete("1.0", "end")
        self.txt_desc.insert("1.0", "Hover over parameters for details...")
        self.txt_desc.configure(state="disabled")
    def on_drop(self, event):
        path = event.data
        if path.startswith("{") and path.endswith("}"): path = path[1:-1]
        self.ent_input.delete(0, "end")
        self.ent_input.insert(0, path)

    def browse_input(self):
        p = filedialog.askdirectory()
        if p:
            self.ent_input.delete(0, "end")
            self.ent_input.insert(0, p)

    def start_process(self):
        inp = self.ent_input.get()
        if not os.path.exists(inp):
            self.lbl_status.configure(text="Invalid Input", text_color="red")
            return
            
        dst = os.path.join(inp if os.path.isdir(inp) else os.path.dirname(inp), "MaskOut")
        
        # Serialize Params for Engine
        # Structure: {Name: val, Name_Rnd: bool, Name_Min: float, Name_Max: float}
        params = {}
        for name, ctrl in self.controls.items():
            
            def safe_get(var):
                v = var.get()
                if isinstance(v, str):
                    if not v: return 0.0
                    try: return float(v)
                    except ValueError: return v # Return string if not float
                    except: return 0.0
                return v

            params[name] = safe_get(ctrl["val"])
            
            if "rnd" in ctrl:
                params[f"{name}_Rnd"] = ctrl["rnd"].get()
            if "min" in ctrl:
                params[f"{name}_Min"] = safe_get(ctrl["min"])
            if "max" in ctrl:
                params[f"{name}_Max"] = safe_get(ctrl["max"])
        
        self.save_settings()
        self.btn_run.configure(state="disabled", text="Processing...")
        
        # Start Animation
        self.is_generating = True
        self.anim_frames = [
            "(>-------)", "(->------)", "(-->-----)", "(--->----)", 
            "(---->---)", "(----->--)", "(------>-)", "(-------<)",
            "(------<-)", "(-----<--)", "(----<---)", "(---<----)", 
            "(--<-----)", "(-<------)"
        ]
        self.anim_idx = 0
        self._animate_progress()
        
        threading.Thread(target=lambda: self.run_thread(inp, dst, params)).start()

    def _animate_progress(self):
        if not self.is_generating: return
        
        txt = self.anim_frames[self.anim_idx % len(self.anim_frames)]
        self.lbl_status.configure(text=txt, text_color="#ffff00")
        self.anim_idx += 1
        self.after(100, self._animate_progress)

    def run_thread(self, src, dst, params):
        self.engine.process(src, dst, params, progress_cb=self.update_prog)
        self.after(0, self.finish)
    
    def update_prog(self, i, total): pass
    
    def finish(self):
        self.is_generating = False
        self.lbl_status.configure(text="Complete!", text_color="green")
        self.btn_run.configure(state="normal", text="Execute Masking")

    def on_close(self):
        self.save_settings()
        self.destroy()

    def save_settings(self):
        # Safety check for ent_input
        input_val = ""
        if hasattr(self, 'ent_input'):
            input_val = self.ent_input.get()
            
        data = {"input": input_val, "params": {}}
        for name, ctrl in self.controls.items():
            # Save raw string values (loading will handle them)
            if "val" in ctrl:
                p_data = {"val": ctrl["val"].get()}
                if "rnd" in ctrl: p_data["rnd"] = ctrl["rnd"].get()
                if "min" in ctrl: p_data["min"] = ctrl["min"].get()
                if "max" in ctrl: p_data["max"] = ctrl["max"].get()
                data["params"][name] = p_data
                
        try:
            with open(self.settings_file, "w") as f: json.dump(data, f, indent=4)
        except: pass

        
    def load_settings(self):
        if not os.path.exists(self.settings_file): return
        try:
            with open(self.settings_file, "r") as f:
                d = json.load(f)
                if "input" in d: 
                    self.ent_input.delete(0, "end")
                    self.ent_input.insert(0, d["input"])
                if "params" in d:
                    for name, p_data in d["params"].items():
                        if name in self.controls:
                            c = self.controls[name]
                            if "val" in p_data: 
                                try: c["val"].set(p_data["val"]) 
                                except: pass
                            if "rnd" in p_data and "rnd" in c: c["rnd"].set(p_data["rnd"])
                            if "min" in p_data and "min" in c: c["min"].set(p_data["min"])
                            if "max" in p_data and "max" in c: c["max"].set(p_data["max"])
                            self._toggle_row(name)
        except Exception as e: print(e)

if __name__ == "__main__":
    app = MaskerGUI()
    app.mainloop()
