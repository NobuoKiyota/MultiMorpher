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
        
        # Buttons
        self.add_btn("SFX Factory\n(Synthesizer)", "pysfx_factory_gui.py", "#e04f5f", "The Generative Synthesizer Engine")
        self.add_btn("WAV Transformer\n(Remixer)", "pysfx_transformer_gui.py", "#4f8fe0", "WAV Morphing & Resynthesis Tool")
        self.add_btn("WAV Extractor\n(Analyzer)", "pysfx_ui_gui.py", "#e0cf4f", "Feature Extraction & Search")
        self.add_btn("Audio Normalizer\n(Post-Process)", "pysfx_normalizer_gui.py", "#4fe08f", "Auto Trim, Stretch & Envelope")
        self.add_btn("Noise Masker\n(Texture Gen)", "pysfx_masker_gui.py", "#a04fe0", "Envelope Following Noise Shaper")
        self.add_btn("Audio Slicer\n(Cutter)", "pysfx_slicer_gui.py", "#FF9800", "Auto Trim & Batch Slice Tool")

        # Footer
        ctk.CTkLabel(self, text="v1.1.0", text_color="#555").pack(side="bottom", pady=10)

    def add_btn(self, text, script_name, color, desc):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=40, pady=10)
        
        # Tooltip logic could be added here, using Label for simplicity now.
        
        btn = ctk.CTkButton(frame, text=text, font=("Arial", 16, "bold"), fg_color=color, height=60,
                            command=lambda s=script_name: self.launch(s))
        btn.pack(fill="x")
        
        ctk.CTkLabel(frame, text=desc, font=("Arial", 11), text_color="#aaa").pack()

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
