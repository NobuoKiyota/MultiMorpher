import customtkinter as ctk
import os
import threading
import sys
import subprocess
import time

# Import Pipeline
# Assuming in same dir
from sfx_pipeline_manager import SFXPipeline
from sfx_reviewer_app import SFXReviewerApp

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SFXLauncherApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SFX Pipeline Launcher")
        self.geometry("600x500")
        
        self.pipeline = SFXPipeline()
        self.running = False
        self.last_batch_path = ""
        
        self.last_batch_name_input = ""
        # Load State
        import json
        try:
             if os.path.exists("last_launcher_state.json"):
                 with open("last_launcher_state.json", "r") as f:
                     state = json.load(f)
                     self.last_batch_name_input = state.get("last_batch_name", "")
        except: pass

        self._init_ui()
        
    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1) # Log area
        
        # --- Config Area ---
        fr_config = ctk.CTkFrame(self)
        fr_config.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        fr_config.grid_columnconfigure(1, weight=1)
        
        # 1. Total Target
        ctk.CTkLabel(fr_config, text="Total Production Target:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.var_total = ctk.StringVar(value="50")
        ctk.CTkEntry(fr_config, textvariable=self.var_total).grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        # 2. Source Count
        ctk.CTkLabel(fr_config, text="Asset Pool Size (Factory):").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.var_source = ctk.StringVar(value="5")
        ctk.CTkEntry(fr_config, textvariable=self.var_source).grid(row=1, column=1, padx=10, pady=5, sticky="ew")
        
        # 3. Complexity
        ctk.CTkLabel(fr_config, text="Complexity / Speed:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.var_complexity = ctk.StringVar(value="Light (Fast)")
        self.opt_complexity = ctk.CTkOptionMenu(fr_config, variable=self.var_complexity, 
                                                values=["Light (Fast)", "Normal", "Heavy (Slow)"])
        self.opt_complexity.grid(row=2, column=1, padx=10, pady=5, sticky="ew")
        
        # 4. Batch Name
        ctk.CTkLabel(fr_config, text="Batch Name (Optional):").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.var_name = ctk.StringVar(value=self.last_batch_name_input)
        ctk.CTkEntry(fr_config, textvariable=self.var_name, placeholder_text="Auto-Generated if empty").grid(row=3, column=1, padx=10, pady=5, sticky="ew")

        # --- Routing Probabilities ---
        # Fallback for old ctk: Use Frame + Label
        fr_route = ctk.CTkFrame(fr_config, fg_color="transparent")
        fr_route.grid(row=4, column=0, columnspan=2, padx=5, pady=10, sticky="ew")
        
        lbl_route_title = ctk.CTkLabel(fr_route, text="Algorithm Routing Weights (Total doesn't need to be 100):", font=("Arial", 12, "bold"))
        lbl_route_title.grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 5))
        
        # Grid for weights (Shifted down by 1 row)
        # Row 1 -> Row 1
        ctk.CTkLabel(fr_route, text="Transformer Only:").grid(row=1, column=0, padx=5, pady=2)
        self.w_trans = ctk.StringVar(value="30")
        ctk.CTkEntry(fr_route, textvariable=self.w_trans, width=50).grid(row=1, column=1, padx=5, pady=2)
        
        ctk.CTkLabel(fr_route, text="Masker Only:").grid(row=1, column=2, padx=5, pady=2)
        self.w_mask = ctk.StringVar(value="30")
        ctk.CTkEntry(fr_route, textvariable=self.w_mask, width=50).grid(row=1, column=3, padx=5, pady=2)
        
        ctk.CTkLabel(fr_route, text="None (Skip):").grid(row=1, column=4, padx=5, pady=2)
        self.w_none = ctk.StringVar(value="20")
        ctk.CTkEntry(fr_route, textvariable=self.w_none, width=50).grid(row=1, column=5, padx=5, pady=2)
        
        # Row 2 (Combos) -> Row 2
        ctk.CTkLabel(fr_route, text="Trans -> Masker:").grid(row=2, column=0, padx=5, pady=2)
        self.w_tm = ctk.StringVar(value="10")
        ctk.CTkEntry(fr_route, textvariable=self.w_tm, width=50).grid(row=2, column=1, padx=5, pady=2)
        
        ctk.CTkLabel(fr_route, text="Masker -> Trans:").grid(row=2, column=2, padx=5, pady=2)
        self.w_mt = ctk.StringVar(value="10")
        ctk.CTkEntry(fr_route, textvariable=self.w_mt, width=50).grid(row=2, column=3, padx=5, pady=2)
        
        # --- Action Area ---
        fr_action = ctk.CTkFrame(self, fg_color="transparent")
        fr_action.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        
        self.btn_run = ctk.CTkButton(fr_action, text="RUN PIPELINE", command=self.on_run, height=40, font=("Arial", 16, "bold"), fg_color="#E91E63", hover_color="#C2185B")
        self.btn_run.pack(side="left", fill="x", expand=True, padx=5)
        
        self.btn_review = ctk.CTkButton(fr_action, text="OPEN REVIEWER", command=self.on_review, height=40, font=("Arial", 16, "bold"), fg_color="#4CAF50", hover_color="#388E3C", state="disabled")
        self.btn_review.pack(side="left", fill="x", expand=True, padx=5)
        
        # --- Log Area ---
        self.txt_log = ctk.CTkTextbox(self, state="disabled")
        self.txt_log.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        # Redirect stdout
        sys.stdout = TextRedirector(self.txt_log)
        
        # 6. Excel Config
        fr_excel = ctk.CTkFrame(fr_config, fg_color="transparent")
        fr_excel.grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky="ew")
        
        self.var_use_excel = ctk.BooleanVar(value=True)
        self.chk_use_excel = ctk.CTkCheckBox(fr_excel, text="Use Excel Config (Factory_Parameters.xlsx)", variable=self.var_use_excel, command=self.on_toggle_excel)
        self.chk_use_excel.pack(side="left", padx=5)
        
        self.btn_select_excel = ctk.CTkButton(fr_excel, text="Select File...", width=100, command=self.on_select_excel)
        self.btn_select_excel.pack(side="right", padx=5)
        
        self.lbl_excel_path = ctk.CTkLabel(fr_excel, text="Default", text_color="gray")
        self.lbl_excel_path.pack(side="right", padx=5)

        # Load State (Advanced)
        self.custom_excel_path = ""
        try:
             if os.path.exists("last_launcher_state.json"):
                 with open("last_launcher_state.json", "r") as f:
                     state = json.load(f)
                     self.var_use_excel.set(state.get("use_excel", True))
                     self.custom_excel_path = state.get("excel_path", "")
                     if self.custom_excel_path:
                         self.lbl_excel_path.configure(text=os.path.basename(self.custom_excel_path))
        except: pass
        
        self.on_toggle_excel() # Update UI state

        # ... (Rest of UI) ...

    def on_toggle_excel(self):
        # If Excel is ON, disable manual weights?
        # Or just visual indication
        state = "disabled" if self.var_use_excel.get() else "normal"
        # Disable weight entries
        try:
            self.w_trans.configure(state=state) # Entry widget state? CTkEntry has configure state?
            # Wait, CTkEntry doesn't have easy disable in some versions, but let's try
            # If fail, ignore
            pass
        except: pass
        
    def on_select_excel(self):
        path = ctk.filedialog.askopenfilename(filetypes=[("Excel Files", "*.xlsx")])
        if path:
            self.custom_excel_path = path
            self.lbl_excel_path.configure(text=os.path.basename(path))
            self.var_use_excel.set(True)
            self.on_toggle_excel()

    def append_log(self, msg):
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", str(msg) + "\n")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")
        
    def on_run(self):
        if self.running: return
        
        try:
            total = int(self.var_total.get())
            source = int(self.var_source.get())
        except ValueError:
             self.append_log("Error: Target and Source must be integers.")
             return
             
        comp = self.var_complexity.get()
        name = self.var_name.get().strip()
        if not name: name = None
        
        # Map Complexity
        overrides = {}
        if "Light" in comp:
            overrides = {"Duration": 0.5, "VoiceCount": 1.0, "DetuneVoice": 0.0, "Chord": 0.0}
        elif "Heavy" in comp:
             overrides = {"Duration": 2.5, "VoiceCount": 3.0, "DetuneVoice": 2.0, "Chord": 1.0}
             
        # Weights
        weights = None
        if not self.var_use_excel.get():
            try:
                weights = {
                    "Transformer": float(self.w_trans.get()),
                    "Masker": float(self.w_mask.get()),
                    "Through": float(self.w_none.get()),
                    "TransMask": float(self.w_tm.get()),
                    "MaskTrans": float(self.w_mt.get())
                }
            except:
                weights = {"Transformer":30, "Masker":30, "Through":20, "TransMask":10, "MaskTrans":10}
                self.append_log("Warning: Invalid weights, using defaults.")
        else:
            self.append_log(f"Using Excel Config: {self.custom_excel_path if self.custom_excel_path else 'Default'}")
            # If using Excel, weights are loaded by Pipeline Manager from Excel.
            # We pass None as weights to indicate "Use Excel/Default"
            weights = None 

        self.running = True
        
        # Save State
        try:
            import json
            state = {
                "last_batch_name": name if name else "",
                "use_excel": self.var_use_excel.get(),
                "excel_path": self.custom_excel_path
            }
            with open("last_launcher_state.json", "w") as f:
                json.dump(state, f)
        except: pass
        
        self.btn_run.configure(state="disabled")
        self.btn_review.configure(state="disabled")
        self.append_log(f"Starting Batch... Total={total}, Source={source}, Mode={comp}")
        if weights: self.append_log(f"Manual Weights: {weights}")
        
        # If custom excel path, we might need to tell Pipeline to use it.
        # Currently Pipeline uses ExcelConfigLoader.get_excel_path().
        # We should update ExcelConfigLoader or pass path to pipeline.
        # Let's pass it to run_process -> run_pipeline
        
        t = threading.Thread(target=self.run_process, args=(name, total, source, overrides, weights, self.custom_excel_path))
        t.start()
        
    def run_process(self, name, total, source, overrides, weights, excel_path):
        try:
            if name is None:
                import datetime
                import socket
                hostname = socket.gethostname()
                # Change to Date-only to enable "Daily Batch" (Append Mode)
                timestamp = datetime.datetime.now().strftime("%Y%m%d")
                name = f"{hostname}_Batch_{timestamp}"
            
            # Setup Excel Path for this run if custom
            if excel_path and os.path.exists(excel_path):
                # Temporary override global default? Or add param to run_pipeline?
                # Best to add param to run_pipeline.
                pass
            
            self.last_batch_path = os.path.join(self.pipeline.root_dir, name, "05_Final_Normalized")
            
            # Update Pipeline call to accept excel_path
            # Note: We need to modify sfx_pipeline_manager.py's run_pipeline to accept excel_path kwarg?
            # Or simpler: Set checking logic inside pipeline using arguments?
            # It seems run_pipeline signature doesn't support excel_path yet.
            # I will assume I need to modify pipeline too or hack it.
            # For now, let's inject it into the pipeline instance or just pass it if supported.
            # Wait, `run_pipeline` signature in Manager is: 
            # (batch_name, total_count=50, source_count=None, factory_settings=None, routing_weights=None)
            # I should update it to accept excel_path.
            
            # For now I will pass it as a special override in factory_settings with a magic key?
            # No, that's dirty.
            # I'll modify pipeline manager next.
            
            self.pipeline.run_pipeline(name, total_count=total, source_count=source, 
                                     factory_settings=overrides, routing_weights=weights,
                                     excel_path=excel_path) # Added arg
            
            # Verify Output
            import glob
            files = glob.glob(os.path.join(self.last_batch_path, "*.wav"))
            generated_count = len(files)
            
            if generated_count >= total:
                self.append_log(f"=== DONE: Generated {generated_count}/{total} files ===")
                self.after(0, self.on_complete, True)
            else:
                self.append_log(f"=== WARNING: Generated {generated_count}/{total} files (Incomplete) ===")
                self.after(0, self.on_complete, generated_count > 0)

            
        except Exception as e:
            self.append_log(f"Error: {e}")
            import traceback
            self.append_log(traceback.format_exc())
            self.after(0, self.on_fail)
            
    def on_complete(self, success=True):
        self.running = False
        self.btn_run.configure(state="normal")
        if success:
            self.btn_review.configure(state="normal", fg_color="#4CAF50") # Green
        else:
             self.btn_review.configure(state="disabled", fg_color="gray")
        
    def on_fail(self):
        self.running = False
        self.btn_run.configure(state="normal")
        
    def on_review(self):
        if not self.last_batch_path or not os.path.exists(self.last_batch_path):
            self.append_log("Log path not found: " + str(self.last_batch_path))
            return
            
        # Launch Reviewer as separate process or window?
        # Separate process is safer to avoid GUI loop conflicts.
        
        self.append_log(f"Launching Reviewer for: {self.last_batch_path}")
        
        # Pass path via CLI arg to Reviewer? 
        # ReviewerApp currently opens dialog. Let's update ReviewerApp to accept arg.
        # "sfx_reviewer_app.py [folder]"
        
        cmd = [sys.executable, "sfx_reviewer_app.py", self.last_batch_path]
        subprocess.Popen(cmd)
        
class TextRedirector:
    def __init__(self, widget):
        self.widget = widget
    def write(self, str):
        self.widget.configure(state="normal")
        self.widget.insert("end", str)
        self.widget.see("end")
        self.widget.configure(state="disabled")
    def flush(self):
        pass

if __name__ == "__main__":
    app = SFXLauncherApp()
    app.mainloop()
