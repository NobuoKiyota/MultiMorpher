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
    def __init__(self):
        super().__init__()
        self.title("PyQuartz SFX Factory - Professional Control")
        self.geometry("950x950")
        
        self.factory = PyQuartzFactory()
        self.is_generating = False
        self.controls = {}
        
        self._init_ui()
        self.load_settings()

    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="💎 PyQuartz Advanced Control Panel", font=("Arial", 22, "bold")).pack(pady=10)

        # スクロール可能な設定テーブル
        self.table_frame = ctk.CTkScrollableFrame(self, width=900, height=580)
        self.table_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # ヘッダー (Use Frame + Grid to match rows)
        header_frame = ctk.CTkFrame(self.table_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=5, padx=2)
        
        headers = [
            ("Parameter", 150), 
            ("Random", 40), 
            ("Value", 100), 
            ("minValue", 80), 
            ("maxValue", 80), 
            ("Note", 200)
        ]
        
        for col, (text, width) in enumerate(headers):
            lbl = ctk.CTkLabel(header_frame, text=text, font=("Arial", 12, "bold"), width=width)
            lbl.grid(row=0, column=col, padx=2)

        # パラメータ定義 (Centralized Config)
        from pysfx_param_config import PySFXParams
        from pysfx_color_config import PySFXColors
        sorted_params = PySFXParams.get_sorted_params()

        for i, p in enumerate(sorted_params, 1):
            name = p.name
            v_min = p.min
            v_max = p.max
            default = p.default
            note = p.desc
            order = p.order # Keep reading order for sorting, but don't display
            
            # Row Color
            bg_color = PySFXColors.get_color(p.group)
            
            row_frame = ctk.CTkFrame(self.table_frame, fg_color=bg_color, corner_radius=0)
            row_frame.grid(row=i, column=0, sticky="ew", pady=1, padx=2)
            
            # Col 0: Name
            ctk.CTkLabel(row_frame, text=name, width=150, anchor="w").grid(row=0, column=0, padx=5, pady=2)
            
            row_data = {}
            
            # Col 1: Random
            var_rnd = ctk.BooleanVar(value=False)
            chk_rnd = ctk.CTkCheckBox(row_frame, text="", variable=var_rnd, width=40,
                                      command=lambda n=name: self.toggle_row(n))
            chk_rnd.grid(row=0, column=1, padx=2, pady=2)
            row_data["random"] = var_rnd

            # Col 2: Value
            if v_min is None: # Boolean Check
                var_val = ctk.BooleanVar(value=default)
                ent_val = ctk.CTkCheckBox(row_frame, text="ENABLE", variable=var_val, width=100)
                chk_rnd.configure(state="disabled")
                row_data["value"] = var_val
            else: # Entry
                var_val = ctk.StringVar(value=str(default))
                ent_val = ctk.CTkEntry(row_frame, textvariable=var_val, width=100)
                row_data["value"] = var_val
            
            ent_val.grid(row=0, column=2, padx=2, pady=2)
            row_data["ent_val"] = ent_val

            # Col 3, 4: Min/Max
            if v_min is not None:
                var_min = ctk.StringVar(value=str(v_min))
                var_max = ctk.StringVar(value=str(v_max))
                ent_min = ctk.CTkEntry(row_frame, textvariable=var_min, width=80)
                ent_max = ctk.CTkEntry(row_frame, textvariable=var_max, width=80)
                ent_min.grid(row=0, column=3, padx=2, pady=2)
                ent_max.grid(row=0, column=4, padx=2, pady=2)
                row_data["min"] = var_min
                row_data["max"] = var_max
                row_data["ent_min"] = ent_min
                row_data["ent_max"] = ent_max
            else:
                ctk.CTkLabel(row_frame, text="", width=80).grid(row=0, column=3)
                ctk.CTkLabel(row_frame, text="", width=80).grid(row=0, column=4)
            
            # Col 5: Note (Was Col 6)
            ctk.CTkLabel(row_frame, text=note, width=200, anchor="w", text_color="gray").grid(row=0, column=5, padx=5)

            self.controls[name] = row_data
            self.toggle_row(name)


        # 実行コントロール
        self.frm_exec = ctk.CTkFrame(self, fg_color="transparent")
        self.frm_exec.pack(pady=20, fill="x", padx=40)
        
        self.btn_reset = ctk.CTkButton(self.frm_exec, text="Default Reset", fg_color="#555", width=120, command=self.reset_defaults)
        self.btn_reset.pack(side="left", padx=10)

        ctk.CTkLabel(self.frm_exec, text="Quantity:").pack(side="left", padx=5)
        self.ent_qty = ctk.CTkEntry(self.frm_exec, width=60)
        self.ent_qty.insert(0, "10")
        self.ent_qty.pack(side="left", padx=5)

        self.btn_run = ctk.CTkButton(self.frm_exec, text="🚀 Start Production", height=50, font=("Arial", 16, "bold"), command=self.start)
        self.btn_run.pack(side="right", expand=True, fill="x", padx=10)

        # ログ出力
        self.txt_log = ctk.CTkTextbox(self, height=180)
        self.txt_log.pack(pady=10, padx=10, fill="x")
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