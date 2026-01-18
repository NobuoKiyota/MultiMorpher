
import customtkinter as ctk
import os
import threading
from tkinter import filedialog
import json
import random
from tkinterdnd2 import TkinterDnD, DND_ALL

from pysfx_transformer_engine import QuartzTransformerEngine
from pysfx_image_tracer import ImageTracer
from pysfx_color_config import PySFXColors

# Param Definitions
TRANSFORM_PARAMS = [
    # Group: Generation
    {"name": "Iteration", "default": 10, "min": 1, "max": 100, "group": "Generator", "type": "int",
     "desc": "生成するファイルの総数。",
     "effect": "指定された回数分、ミキシングと変換処理を繰り返します。",
     "guide": "バリエーションを大量に作る場合は50〜100程度に設定します。"},
    
    {"name": "MixCount", "default": 2, "min": 1, "max": 4, "group": "Generator", "type": "int", 
     "desc": "合成に使用するファイルの数 (1-4)。",
     "effect": "1:単体加工(Single), 2-4:複数ファイルをブレンドします。",
     "guide": "Min=1, Max=4にしてRndをONにすると、単発と複雑な合成音がランダムに生成されます。"},
     
    {"name": "MorphStartOffset", "default": 0.0, "min": 0.0, "max": 1.0, "group": "Generator", "type": "float",
     "desc": "モーフィング波形の開始位置オフセット (0.0-1.0)。",
     "effect": "LFOの開始位相をずらします。例: 0.5なら逆相から開始。",
     "guide": "Rndを使うと、毎回異なる混ぜ合わせ状態から音が始まり、アタック感に変化が出ます。"},

    {"name": "MorphFreq", "default": 0.5, "min": 0.1, "max": 10.0, "group": "Generator", "type": "float",
     "desc": "モーフィング（LFO）の速度 (Hz)。",
     "effect": "2つの音を行き来する周期の速さを決定します。",
     "guide": "遅い(0.5Hz)とゆっくり変化し、速い(5Hz~)とトレモロのようになります。"},

    {"name": "ReverseProb", "default": 0.5, "min": 0.0, "max": 1.0, "group": "Generator", "type": "float", 
     "desc": "リバース（逆再生）の発生確率 (0.0-1.0)。",
     "effect": "設定した確率で、生成された波形を時間軸反転させます。",
     "guide": "0.0=無効、1.0=常時反転、0.5=ランダム。Rnd有効時は確率自体が変動します。"},

    # Group: Image Tracer
    {"name": "ScratchProb", "default": 0.0, "min": 0.0, "max": 1.0, "group": "Modulation", "type": "float",
     "desc": "画像ラインによるスクラッチ効果の発生確率 (0.0-1.0)。",
     "effect": "設定した確率で、画像の曲線を読み取り再生位置をスクラッチ操作します。",
     "guide": "0.5にすると50%の確率でグリッチ感のある効果が発生します。"},

    {"name": "StretchProb", "default": 0.0, "min": 0.0, "max": 1.0, "group": "Modulation", "type": "float",
     "desc": "画像ラインによる可変タイムストレッチの発生確率 (0.0-1.0)。",
     "effect": "設定した確率で、画像の曲線に基づいて再生速度を劇的に変化させます。",
     "guide": "エンジンの加速音のような「うねり」をランダムに混ぜるのに適しています。"},

    {"name": "FlutterProb", "default": 0.0, "min": 0.0, "max": 1.0, "group": "Modulation", "type": "float",
     "desc": "画像ラインによるフラッターの発生確率 (0.0-1.0)。",
     "effect": "設定した確率で、音量やピッチを細かく振動させるトレモロ効果を付与します。",
     "guide": "金管のフラッタータンギングのような質感を時折混ぜたい場合に使用します。"},

    # Group: Effects (Space)
    {"name": "ReverbTime", "default": 3.0, "min": 0.1, "max": 10.0, "group": "Reverb", "type": "float",
     "desc": "リバーブの減衰時間 (秒)。",
     "effect": "空間の広さや残響の長さを決定します。",
     "guide": "SFXでは長め(3s~)に設定してTailを作ることが多いです。"},

    {"name": "ReverbWet", "default": 0.0, "min": 0.0, "max": 1.0, "group": "Reverb", "type": "float",
     "desc": "リバーブ音の混入量 (0.0 - 1.0)。",
     "effect": "1.0に近づくほど原音が遠くなり、空間音のみになります。",
     "guide": "完全にWetのみにするとドローンサウンドが作れます。"},
     
    {"name": "DelayTime", "default": 0.5, "min": 0.01, "max": 1.0, "group": "Delay", "type": "float",
     "desc": "ディレイ（やまびこ）の間隔 (秒)。",
     "effect": "音が繰り返されるタイミングを決定します。",
     "guide": "短く(0.05s)してダブリング効果、長く(0.5s)してエコー効果を作ります。"},
     
    {"name": "DelayFeedback", "default": 0.5, "min": 0.0, "max": 0.95, "group": "Delay", "type": "float",
     "desc": "ディレイの繰り返し回数（フィードバック）。",
     "effect": "値を上げると音がいつまでも繰り返されます。",
     "guide": "0.9以上にすると発振（Oscillation）の危険があるので注意してください。"},
     
    {"name": "DelayWet", "default": 0.0, "min": 0.0, "max": 1.0, "group": "Delay", "type": "float",
     "desc": "ディレイ音の混入量。",
     "effect": "やまびこ音の音量を決定します。",
     "guide": "リズミカルなテクスチャを作る場合に上げてください。"}
]

class TransformerGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("Quartz Transformer - WAV Re-Synthesis")
        self.geometry("480x820") 
        
        self.engine = QuartzTransformerEngine()
        self.settings_file = "transformer_settings.json"
        self.controls = {}
        self.is_generating = False
        self._hover_job = None
        
        self._init_ui()
        self.load_settings()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def _init_ui(self):
        # 1. Input Area
        frame_io = ctk.CTkFrame(self)
        frame_io.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(frame_io, text="Source Folder (WAVs):").pack(side="left", padx=5)
        self.ent_input = ctk.CTkEntry(frame_io, width=250) # Reduced width for 480px
        self.ent_input.pack(side="left", padx=5)
        
        # DnD
        try:
            self.ent_input.drop_target_register(DND_ALL)
            self.ent_input.dnd_bind('<<Drop>>', self.on_drop)
        except Exception as e:
            print(f"DnD Error: {e}")
            
        ctk.CTkButton(frame_io, text="Browse", width=60, command=self.browse_input).pack(side="left", padx=5)
        
        # 2. Parameters Scroll Area
        self.frame_params = ctk.CTkScrollableFrame(self, label_text="Transformation Parameters")
        self.frame_params.pack(fill="both", expand=True, padx=10, pady=5)
        
        self._create_headers()
        
        for p in TRANSFORM_PARAMS:
            self._create_row(p)
            
        # Description Box
        self.txt_desc = ctk.CTkTextbox(self, height=110, fg_color="transparent", text_color="#aaa")
        self.txt_desc.pack(fill="x", padx=10, pady=5)
        self.txt_desc.insert("1.0", "Hover over parameters for details...")
        
        # Tags for Rich Text
        self.txt_desc.tag_config("title", foreground="#ffffff")
        self.txt_desc.tag_config("desc", foreground="#dddddd")
        self.txt_desc.tag_config("effect", foreground="#a0a0ff")
        self.txt_desc.tag_config("guide", foreground="#ffaaaa")
        self.txt_desc.configure(state="disabled")

        # 3. Actions
        self.btn_run = ctk.CTkButton(self, text="Start Transformation", command=self.start_process, 
                                     font=("Arial", 16, "bold"), fg_color="#e04f5f", height=50)
        self.btn_run.pack(fill="x", padx=20, pady=10)
        
        self.lbl_status = ctk.CTkLabel(self, text="Ready.", font=("Consolas", 12))
        self.lbl_status.pack(pady=5)

    def _create_headers(self):
        h_frame = ctk.CTkFrame(self.frame_params, fg_color="transparent")
        h_frame.pack(fill="x")
        # Optimized widths for 480px width
        ctk.CTkLabel(h_frame, text="Param", width=130, anchor="w", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=2)
        ctk.CTkLabel(h_frame, text="Rnd", width=30, font=("Arial", 12, "bold")).grid(row=0, column=1, padx=2)
        ctk.CTkLabel(h_frame, text="Val", width=70, font=("Arial", 12, "bold")).grid(row=0, column=2, padx=2)
        ctk.CTkLabel(h_frame, text="Min", width=50, font=("Arial", 12, "bold")).grid(row=0, column=3, padx=2)
        ctk.CTkLabel(h_frame, text="Max", width=50, font=("Arial", 12, "bold")).grid(row=0, column=4, padx=2)

    def _create_row(self, p):
        name = p["name"]
        color = PySFXColors.get_color(p["group"])
        
        row = ctk.CTkFrame(self.frame_params, fg_color=color)
        row.pack(fill="x", pady=1)
        
        # Name
        lbl = ctk.CTkLabel(row, text=name, width=130, anchor="w")
        lbl.grid(row=0, column=0, padx=2, pady=2)
        
        data = {}
        
        # Rnd Check
        var_rnd = ctk.BooleanVar(value=False)
        chk_rnd = ctk.CTkCheckBox(row, text="", variable=var_rnd, width=30, command=lambda n=name: self._toggle_row(n))
        chk_rnd.grid(row=0, column=1, padx=2)
        data["rnd"] = var_rnd
        
        # Value Widget (Use StringVar to prevent crash on empty)
        if p["type"] == "combo":
            var_val = ctk.StringVar(value=str(p["default"]))
            widget_val = ctk.CTkComboBox(row, values=p["values"], variable=var_val, width=70)
            chk_rnd.configure(state="disabled")
        elif p["type"] == "bool":
            var_val = ctk.BooleanVar(value=p["default"])
            widget_val = ctk.CTkCheckBox(row, text="On", variable=var_val, width=70)
            chk_rnd.configure(state="disabled")
        elif p["type"] == "int":
            var_val = ctk.StringVar(value=str(p["default"]))
            widget_val = ctk.CTkEntry(row, textvariable=var_val, width=70)
            # Only disable Rnd for Iteration (Loop count shouldn't be random per loop)
            if p["name"] == "Iteration":
                chk_rnd.configure(state="disabled")
        else: # float
            var_val = ctk.StringVar(value=str(p["default"]))
            widget_val = ctk.CTkEntry(row, textvariable=var_val, width=70)
            widget_val.bind("<MouseWheel>", lambda e, v=var_val: self._on_wheel(e, v))
            
        widget_val.grid(row=0, column=2, padx=2)
        data["val"] = var_val
        
        # Min/Max Widgets
        # Show for float and int, BUT skip Iteration param
        if p["type"] in ["float", "int"] and p["name"] != "Iteration":
            var_min = ctk.StringVar(value=str(p.get("min", 0.0)))
            var_max = ctk.StringVar(value=str(p.get("max", 1.0)))
            ent_min = ctk.CTkEntry(row, textvariable=var_min, width=50)
            ent_max = ctk.CTkEntry(row, textvariable=var_max, width=50)
            ent_min.grid(row=0, column=3, padx=2)
            ent_max.grid(row=0, column=4, padx=2)
            
            ent_min.bind("<MouseWheel>", lambda e, v=var_min, t=p["type"]: self._on_wheel(e, v, t))
            ent_max.bind("<MouseWheel>", lambda e, v=var_max, t=p["type"]: self._on_wheel(e, v, t))
            
            data["min"] = var_min
            data["max"] = var_max
            data["widget_val"] = widget_val
            data["widget_min"] = ent_min
            data["widget_max"] = ent_max
        else:
            ctk.CTkLabel(row, text="", width=50).grid(row=0, column=3)
            ctk.CTkLabel(row, text="", width=50).grid(row=0, column=4)
            
        self.controls[name] = data
        self._toggle_row(name)
        
        # Bind Hover to Row and *ALL* children for continuous coverage
        self._bind_hover(row, p)
        for child in row.winfo_children():
            self._bind_hover(child, p)

    def _toggle_row(self, name):
        ctrl = self.controls[name]
        is_rnd = ctrl["rnd"].get()
        if "widget_min" in ctrl:
            state_range = "normal" if is_rnd else "disabled"
            state_val = "disabled" if is_rnd else "normal"
            ctrl["widget_min"].configure(state=state_range)
            ctrl["widget_max"].configure(state=state_range)
            ctrl["widget_val"].configure(state=state_val)

    def _on_wheel(self, event, var, p_type="float"):
        try:
            val_str = var.get()
            if not val_str: val = 0.0
            else: val = float(val_str)
            
            if p_type == "int":
                step = 1
                if event.delta < 0: step = -1
                new_val = int(val + step)
                var.set(str(new_val))
            else:
                step = 0.05 if abs(event.delta) < 120 else 0.1
                if event.delta < 0: step *= -1
                new_val = round(val + step, 2)
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
        name = p_data.get("name", "Param")
        self.txt_desc.insert("end", f"【 {name} 】\n", "title")
        if "desc" in p_data: self.txt_desc.insert("end", f"{p_data['desc']}\n", "desc")
        if "effect" in p_data: self.txt_desc.insert("end", f"Effect: {p_data['effect']}\n", "effect")
        if "guide" in p_data: self.txt_desc.insert("end", f"Guide: {p_data['guide']}", "guide")
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

    def browse_input(self):
        p = filedialog.askdirectory()
        if p:
            self.ent_input.delete(0, "end")
            self.ent_input.insert(0, p)

    def on_drop(self, event):
        path = event.data
        if path.startswith("{") and path.endswith("}"): path = path[1:-1]
        self.ent_input.delete(0, "end")
        self.ent_input.insert(0, path)

    def start_process(self):
        src = self.ent_input.get()
        if not os.path.exists(src):
            self.lbl_status.configure(text="Invalid Source Folder", text_color="red")
            return
            
        dst = os.path.join(src, "Transformed")
        self.save_settings()
        
        # Build Params (Safe Convert)
        params = {}
        for name, ctrl in self.controls.items():
            # Handle Rnd
            if "rnd" in ctrl: params[f"{name}_Rnd"] = ctrl["rnd"].get()
            
            # Handle Val, Min, Max (Convert str to float/int)
            def safe_get(var):
                v = var.get()
                if isinstance(v, str):
                    if not v: return 0.0
                    try: return float(v)
                    except: return 0.0
                return v

            params[name] = safe_get(ctrl["val"])
            if "min" in ctrl: params[f"{name}_Min"] = safe_get(ctrl["min"])
            if "max" in ctrl: params[f"{name}_Max"] = safe_get(ctrl["max"])

        self.btn_run.configure(state="disabled", text="Processing...")
        self.is_generating = True
        self.anim_frames = [
            "(>-------)", "(->------)", "(-->-----)", "(--->----)", 
            "(---->---)", "(----->--)", "(------>-)", "(-------<)",
            "(------<-)", "(-----<--)", "(----<---)", "(---<----)", 
            "(--<-----)", "(-<------)"
        ]
        self.anim_idx = 0
        self._animate_progress()
        
        threading.Thread(target=lambda: self.run_thread(src, dst, params)).start()

    def _animate_progress(self):
        if not self.is_generating: return
        txt = self.anim_frames[self.anim_idx % len(self.anim_frames)]
        self.lbl_status.configure(text=f"Generating... {txt}", text_color="#ffff00")
        self.anim_idx += 1
        self.after(100, self._animate_progress)

    def run_thread(self, src, dst, params):
        self.engine.process(src, dst, params, progress_cb=self.update_prog)
        self.after(0, self.finish)

    def update_prog(self, i, total):
        pass # Animation handles visual feedback

    def finish(self):
        self.is_generating = False
        self.lbl_status.configure(text="Complete!", text_color="green")
        self.btn_run.configure(state="normal", text="Start Transformation")

    def save_settings(self):
        data = {"input": self.ent_input.get(), "params": {}}
        for name, ctrl in self.controls.items():
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

    def on_close(self):
        self.save_settings()
        self.destroy()

if __name__ == "__main__":
    app = TransformerGUI()
    app.mainloop()
