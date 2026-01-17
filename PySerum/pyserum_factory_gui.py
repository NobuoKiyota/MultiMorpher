import customtkinter as ctk
import json
import os
import sys
import threading
from pyserum_factory import PySerumFactory

SETTINGS_FILE = "factory_settings.json"

class FactoryGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PySerum Factory - Advanced Control")
        self.geometry("900x850")
        
        self.factory = PySerumFactory()
        self.is_generating = False
        self.controls = {} # 管理用辞書
        
        self._init_ui()
        self.load_settings()

    def _init_ui(self):
        # メインフレーム
        self.grid_columnconfigure(0, weight=1)
        
        # タイトル
        ctk.CTkLabel(self, text="⚙️ Advanced Production Control", font=("Arial", 20, "bold")).pack(pady=10)

        # スクロール可能なテーブルエリア
        self.table_frame = ctk.CTkScrollableFrame(self, width=850, height=500)
        self.table_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # ヘッダー行
        headers = ["Parameter", "Random", "Value", "minValue", "maxValue", "Note"]
        for col, text in enumerate(headers):
            lbl = ctk.CTkLabel(self.table_frame, text=text, font=("Arial", 12, "bold"))
            lbl.grid(row=0, column=col, padx=5, pady=5, sticky="w")

        # パラメータ定義 (設計図通り)
        params = [
            ("Duration", 0, 10, 2, "音の長さ(s)"),
            ("NoteRange", 0, 127, 60, "音程 (0-127)"),
            ("Voices", 1, 8, 1, "和音数"),
            ("Strum", 0, 100, 0, "発音ズレ(ms)"),
            ("Chord", None, None, False, "和音アルゴリズムON"),
            ("Arpeggio", None, None, False, "アルペジオON"),
            ("ArpeggioSplit", 1, 100, 4, "分割数"),
            ("Portament", 0, 100, 0, "ポルタメント(ms)"),
            ("AmpAttack", 0, 10000, 10, "アタック(ms)"),
            ("AmpHold", 0, 10000, 0, "ホールド(ms)"),
            ("AmpDecay", 0, 10000, 100, "ディケイ(ms)"),
            ("AmpSustain", 0, 127, 100, "サスティン(0-127)"),
            ("AmpRelease", 0, 10000, 200, "リリース(ms)"),
            ("ReleaseCurve", 0, 127, 64, "64でリニア"),
            ("PitchRange", 0, 7200, 0, "範囲(cent)"),
            ("PitchCurve", 0, 127, 64, "64でリニア")
        ]

        for i, (name, v_min, v_max, default, note) in enumerate(params, 1):
            # Row Data
            row_data = {}
            
            # Name
            ctk.CTkLabel(self.table_frame, text=name).grid(row=i, column=0, padx=5, pady=2, sticky="w")
            
            # Random Check
            var_rnd = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(self.table_frame, text="", variable=var_rnd, width=20, 
                                  command=lambda n=name: self.toggle_row(n))
            chk.grid(row=i, column=1, padx=5, pady=2)
            row_data["random"] = var_rnd

            # Value Entry
            if isinstance(default, bool): # Checkbox items like Chord
                var_val = ctk.BooleanVar(value=default)
                ent_val = ctk.CTkCheckBox(self.table_frame, text="ON", variable=var_val)
                row_data["value"] = var_val
            else:
                var_val = ctk.StringVar(value=str(default))
                ent_val = ctk.CTkEntry(self.table_frame, textvariable=var_val, width=80)
                row_data["value"] = var_val
            ent_val.grid(row=i, column=2, padx=5, pady=2)
            row_data["ent_val"] = ent_val

            # Min/Max Entries
            if v_min is not None:
                var_min = ctk.StringVar(value=str(v_min))
                var_max = ctk.StringVar(value=str(v_max))
                ent_min = ctk.CTkEntry(self.table_frame, textvariable=var_min, width=80)
                ent_max = ctk.CTkEntry(self.table_frame, textvariable=var_max, width=80)
                ent_min.grid(row=i, column=3, padx=5, pady=2)
                ent_max.grid(row=i, column=4, padx=5, pady=2)
                row_data["min"] = var_min
                row_data["max"] = var_max
                row_data["ent_min"] = ent_min
                row_data["ent_max"] = ent_max
            
            # Note
            ctk.CTkLabel(self.table_frame, text=note, font=("Arial", 10), text_color="gray").grid(row=i, column=5, padx=5, pady=2, sticky="w")
            
            self.controls[name] = row_data
            self.toggle_row(name) # 初期状態適用

        # 操作ボタン
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=20, fill="x", padx=50)

        self.btn_reset = ctk.CTkButton(self.btn_frame, text="Default Reset", fg_color="#555", command=self.reset_to_default)
        self.btn_reset.pack(side="left", padx=10)

        self.btn_run = ctk.CTkButton(self.btn_frame, text="🚀 Start Production", height=45, font=("Arial", 16, "bold"), command=self.start)
        self.btn_run.pack(side="right", expand=True, fill="x", padx=10)

        # ログ
        self.txt_log = ctk.CTkTextbox(self, height=150)
        self.txt_log.pack(pady=10, padx=10, fill="x")
        sys.stdout = self # Redirect

    def write(self, text):
        self.txt_log.insert("end", text)
        self.txt_log.see("end")

    def flush(self): pass

    def toggle_row(self, name):
        ctrl = self.controls[name]
        is_rnd = ctrl["random"].get()
        
        # Random ON -> Value無効, MinMax有効
        if "ent_val" in ctrl:
            ctrl["ent_val"].configure(state="disabled" if is_rnd else "normal", 
                                      fg_color="#333" if is_rnd else "#444")
        if "ent_min" in ctrl:
            ctrl["ent_min"].configure(state="normal" if is_rnd else "disabled",
                                      fg_color="#444" if is_rnd else "#333")
            ctrl["ent_max"].configure(state="normal" if is_rnd else "disabled",
                                      fg_color="#444" if is_rnd else "#333")

    def save_settings(self):
        data = {name: {k: v.get() for k, v in ctrl.items() if not k.startswith("ent")} 
                for name, ctrl in self.controls.items()}
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f)

    def load_settings(self):
        if not os.path.exists(SETTINGS_FILE): return
        with open(SETTINGS_FILE, "r") as f:
            data = json.load(f)
            for name, vals in data.items():
                if name in self.controls:
                    for k, v in vals.items():
                        self.controls[name][k].set(v)
                    self.toggle_row(name)

    def reset_to_default(self):
        # 簡単のためアプリ再起動または手動リセットロジックをここに
        pass

    def start(self):
        self.save_settings()
        # Factoryに値を渡して開始
        config = {name: {k: v.get() for k, v in ctrl.items() if not k.startswith("ent")} 
                  for name, ctrl in self.controls.items()}
        threading.Thread(target=self.factory.run_advanced_batch, args=(config,)).start()

if __name__ == "__main__":
    app = FactoryGUI()
    app.mainloop()