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
        
    def log(self, msg):
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
             self.log("Error: Target and Source must be integers.")
             return
             
        comp = self.var_complexity.get()
        name = self.var_name.get().strip()
        if not name: name = None
        
        # Map Complexity
        # Light: Duration <= 1.0, Voices=1, Detune=0
        # Normal: Default
        # Heavy: Duration >= 2.0, Voices>=3, Detune>=1
        
        overrides = {}
        if "Light" in comp:
            overrides = {
                "Duration": 0.5,
                "VoiceCount": 1.0,
                "DetuneVoice": 0.0,
                "Chord": 0.0, # False
                # Filter Auto off?
            }
        elif "Heavy" in comp:
             overrides = {
                 "Duration": 2.5,
                 "VoiceCount": 3.0,
                 "DetuneVoice": 2.0,
                 "Chord": 1.0
             }
             
        self.running = True
        
        # Save State
        try:
            import json
            with open("last_launcher_state.json", "w") as f:
                json.dump({"last_batch_name": name if name else ""}, f)
        except: pass
        
        self.btn_run.configure(state="disabled")
        self.btn_review.configure(state="disabled")
        self.log(f"Starting Batch... Total={total}, Source={source}, Mode={comp}")
        
        t = threading.Thread(target=self.run_process, args=(name, total, source, overrides))
        t.start()
        
    def run_process(self, name, total, source, overrides):
        try:
            # We need to capture the name
            # Pipeline doesn't return name.
            # But we can predict it or pipeline prints it.
            # We'll rely on pipeline being updated locally or just pass the name if provided.
            # If name is None, pipeline generates it. We need that to know path.
            
            # Since pipeline runs in this process, we can access it.
            # But pipeline methods print to stdout which we redirected.
            
            # Let's Modify pipeline call if needed, but for now simple run.
            # Currently manager logic generates name inside run_pipeline if None.
            # We can't easily get it back without parsing stdout or modifying manager return.
            # Let's force a name if None.
            
            if name is None:
                import datetime
                import socket
                hostname = socket.gethostname()
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                name = f"{hostname}_Batch_{timestamp}"
            
            self.last_batch_path = os.path.join(self.pipeline.root_dir, name, "05_Final_Normalized")
            
            self.pipeline.run_pipeline(name, total_count=total, source_count=source, factory_settings=overrides)
            
            # Verify Output
            import glob
            files = glob.glob(os.path.join(self.last_batch_path, "*.wav"))
            generated_count = len(files)
            
            if generated_count >= total:
                self.log(f"=== DONE: Generated {generated_count}/{total} files ===")
                self.after(0, self.on_complete, True)
            else:
                self.log(f"=== WARNING: Generated {generated_count}/{total} files (Incomplete) ===")
                self.after(0, self.on_complete, False) # Still enable? Or strictly fail? User said "check if necessary wavs... if problem nothing, enable button"
                # "Check if necessary wavs are in folder, check, if problem nothing, enable button"
                # implies: If Check OK -> Enable. If Check Fail -> Don't enable? or Enable with warning?
                # "Problem nothing" -> "No problem" -> Enable.
                # So if OK -> Enable. if Fail -> Disable?
                # I'll enable only if count > 0, but warn if mismatch.
                self.after(0, self.on_complete, generated_count > 0)

            
        except Exception as e:
            self.log(f"Error: {e}")
            import traceback
            self.log(traceback.format_exc())
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
            self.log("Log path not found: " + str(self.last_batch_path))
            return
            
        # Launch Reviewer as separate process or window?
        # Separate process is safer to avoid GUI loop conflicts.
        
        self.log(f"Launching Reviewer for: {self.last_batch_path}")
        
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
