import customtkinter as ctk
import subprocess
import sys
import os

class LauncherGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Quartz Suite Launcher")
        self.geometry("400x760")
        
        # Title
        ctk.CTkLabel(self, text="Quartz Audio Suite", font=("Arial", 24, "bold")).pack(pady=(30, 10))
        ctk.CTkLabel(self, text="Select Module to Launch", font=("Arial", 14)).pack(pady=(0, 20))
        
        # Tools List
        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=5, pady=5)
        
        tools = [
            ("SFX Factory\n(Generator)", "pysfx_factory_gui.py", "#e04f5f", "Generative Synthesizer Engine"),
            ("WAV Transformer\n(Remixer)", "pysfx_transformer_gui.py", "#4f8fe0", "WAV Morphing & Resynthesis"),
            ("WAV Extractor\n(Analyzer)", "pysfx_ui_gui.py", "#4CAF50", "Tagging & Feature Extraction"),
            ("Audio Slicer\n(Cutter)", "pysfx_slicer_gui.py", "#FF9800", "Auto Trim & Batch Slice Tool"),
            ("Noise Masker\n(Texture Gen)", "pysfx_masker_gui.py", "#00BCD4", "Envelope Following Noise Shaper"),
            ("Audio Normalizer\n(Post-Process)", "pysfx_normalizer_gui.py", "#4fe08f", "Auto Trim, Stretch & Envelope"),
            ("Voice Translator\n(JP->EN)", "pysfx_translator_gui.py", "#E040FB", "Real-time Voice Translation Helper")
        ]

        for text, script, color, desc in tools:
            self.add_btn(container, text, script, color, desc)

        ctk.CTkLabel(self, text="v1.2.0", text_color="gray").pack(side="bottom", pady=5)

    def add_btn(self, parent, text, script_name, color, desc):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", padx=10, pady=5)
        
        btn = ctk.CTkButton(frame, text=text, font=("Arial", 14, "bold"), fg_color=color, height=50,
                            command=lambda s=script_name: self.launch(s))
        btn.pack(fill="x")
        
        ctk.CTkLabel(frame, text=desc, font=("Arial", 10), text_color="#aaa").pack()

    def launch(self, script_name):
        # run python script non-blocking
        if getattr(sys, 'frozen', False):
            # If exe context (not yet), use subprocess with python
            pass
        
        cmd = [sys.executable, script_name]
        try:
            # Use Popen to allow launcher to stay open or close?
            # User probably wants launcher to stay open or allow multiple tools.
            subprocess.Popen(cmd, cwd=os.getcwd())
        except Exception as e:
            print(f"Error launching {script_name}: {e}")

if __name__ == "__main__":
    app = LauncherGUI()
    app.mainloop()
