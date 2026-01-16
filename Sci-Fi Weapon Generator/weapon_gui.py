import customtkinter as ctk
import threading
import soundfile as sf
import sounddevice as sd
import numpy as np
import os
import time
import random
from weapon_engine import WeaponSynth

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class WeaponGenApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Sci-Fi Weapon & Magic Generator")
        self.geometry("500x750")
        self.resizable(False, False)
        
        self.engine = WeaponSynth()
        self.generated_audio = None
        self.presets = self.engine.get_presets()
        
        self._init_ui()
        
    def _init_ui(self):
        # 1. Top Section: Presets
        self.frame_top = ctk.CTkFrame(self)
        self.frame_top.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(self.frame_top, text="PRESET SELECTION", font=("Arial", 12, "bold")).pack(pady=5)
        
        self.preset_vars = ctk.StringVar(value="Select Preset")
        self.opt_preset = ctk.CTkOptionMenu(
            self.frame_top, 
            values=list(self.presets.keys()),
            command=self.load_preset,
            width=200
        )
        self.opt_preset.pack(pady=5)

        # 2. Middle Section: Parameters
        self.frame_params = ctk.CTkScrollableFrame(self, label_text="SYNTHESIS PARAMETERS")
        self.frame_params.pack(fill="both", expand=True, padx=10, pady=5)
        
        # --- Charge Group ---
        ctk.CTkLabel(self.frame_params, text="[ Charge Phase ]", text_color="cyan").pack(anchor="w", padx=5, pady=(5,0))
        
        self.sl_charge_dur = self._add_slider("Duration (s)", 0.0, 3.0, 1.0)
        self.sl_charge_swell = self._add_slider("Swell (LFO)", 0.0, 1.0, 0.5)
        self.sl_charge_rise = self._add_slider("Pitch Rise", 0.0, 1.0, 0.5)
        
        # Color (Option)
        self.frame_color = ctk.CTkFrame(self.frame_params, fg_color="transparent")
        self.frame_color.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(self.frame_color, text="Tone Color", width=100, anchor="w").pack(side="left")
        self.opt_color = ctk.CTkOptionMenu(self.frame_color, values=["Dark", "Bright"], width=100)
        self.opt_color.pack(side="left")

        # --- Shot Group ---
        ctk.CTkLabel(self.frame_params, text="[ Shot Phase ]", text_color="orange").pack(anchor="w", padx=5, pady=(15,0))
        
        self.sl_shot_impact = self._add_slider("Impact Kick", 0.0, 1.0, 0.5)
        self.sl_shot_tail = self._add_slider("Tail Length (s)", 0.1, 5.0, 1.0)
        self.sl_shot_aggro = self._add_slider("Aggression (Dist)", 0.0, 1.0, 0.5)
        
        # Type (Hidden or derived from preset? Let's make it selectable for fun)
        self.frame_type = ctk.CTkFrame(self.frame_params, fg_color="transparent")
        self.frame_type.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(self.frame_type, text="Core Type", width=100, anchor="w").pack(side="left")
        self.opt_type = ctk.CTkOptionMenu(self.frame_type, values=["Laser", "Plasma", "Magic", "Railgun", "Artillery"], width=100)
        self.opt_type.pack(side="left")

        # 3. Bottom Section: Action
        self.frame_bottom = ctk.CTkFrame(self)
        self.frame_bottom.pack(fill="x", padx=10, pady=10)
        
        self.btn_gen = ctk.CTkButton(self.frame_bottom, text="GENERATE & PLAY", font=("Arial", 14, "bold"), height=50, fg_color="#e63946", command=self.generate)
        self.btn_gen.pack(fill="x", padx=10, pady=5)
        
        self.btn_row = ctk.CTkFrame(self.frame_bottom, fg_color="transparent")
        self.btn_row.pack(fill="x", padx=10, pady=5)
        
        self.btn_rand = ctk.CTkButton(self.btn_row, text="Randomize (Gacha)", fg_color="#457b9d", command=self.randomize)
        self.btn_rand.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_save = ctk.CTkButton(self.btn_row, text="Save WAV", fg_color="#1d3557", command=self.save_wav)
        self.btn_save.pack(side="right", fill="x", expand=True, padx=(5, 0))
        
        self.lbl_status = ctk.CTkLabel(self.frame_bottom, text="Ready.")
        self.lbl_status.pack(pady=2)

    def _add_slider(self, label, vmin, vmax, vdefault):
        frame = ctk.CTkFrame(self.frame_params, fg_color="transparent")
        frame.pack(fill="x", padx=5, pady=2)
        
        lbl = ctk.CTkLabel(frame, text=label, width=100, anchor="w")
        lbl.pack(side="left")
        
        slider = ctk.CTkSlider(frame, from_=vmin, to=vmax, number_of_steps=100)
        slider.set(vdefault)
        slider.pack(side="left", fill="x", expand=True, padx=5)
        
        return slider

    def load_preset(self, preset_name):
        if preset_name not in self.presets: return
        p = self.presets[preset_name]
        
        # Charge
        c = p["charge"]
        self.sl_charge_dur.set(c["duration"])
        self.sl_charge_swell.set(c["swell"])
        self.sl_charge_rise.set(c["rise"])
        self.opt_color.set(c["color"])
        
        # Shot
        s = p["shot"]
        self.sl_shot_impact.set(s["impact"])
        self.sl_shot_tail.set(s["tail"])
        self.sl_shot_aggro.set(s["aggression"])
        self.opt_type.set(s["type"])
        
        self.lbl_status.configure(text=f"Loaded Preset: {preset_name}")

    def get_params(self):
        return {
            "charge": {
                "duration": self.sl_charge_dur.get(),
                "swell": self.sl_charge_swell.get(),
                "rise": self.sl_charge_rise.get(),
                "color": self.opt_color.get()
            },
            "shot": {
                "impact": self.sl_shot_impact.get(),
                "tail": self.sl_shot_tail.get(),
                "aggression": self.sl_shot_aggro.get(),
                "type": self.opt_type.get()
            }
        }

    def generate(self):
        self.lbl_status.configure(text="Generating...")
        self.update()
        
        params = self.get_params()
        
        # Run in thread to allow UI update
        t = threading.Thread(target=self._run_gen, args=(params,))
        t.start()
        
    def _run_gen(self, params):
        try:
            audio = self.engine.generate(params)
            self.generated_audio = audio
            
            # Playback
            sd.play(audio, self.engine.sr)
            # sd.wait() # Don't block thread completely if we want to allow stops, but here it's fine to just trigger
            
            self.lbl_status.configure(text="Generated & Playing.")
        except Exception as e:
            self.lbl_status.configure(text=f"Error: {e}")

    def randomize(self):
        # Base on current preset, drift values slightly
        # Or totally random? "微調整乱数 (Micro-adjustment)"
        # So drift.
        
        def drift(slider, amount=0.2):
            val = slider.get()
            new_val = val + random.uniform(-amount, amount)
            # Clamp in slider logic (it does clamp on set?)
            # Sliders usually clamp visual but logic needs check.
            # CTK Slider limits? let's just clamp manually
            # But we don't know min/max easily from object without storing. 
            # We know defaults.
            # Let's just set() and hope Ctk handles bounds? CTK doesn't always clamp on set.
            # Re-read min/max from my _add_slider? No I didn't store.
            # Hardcode rough limits 0-1 or 0-5.
            if new_val < 0: new_val = 0
            if new_val > 1 and "Length" not in str(slider):
                 if new_val > 1: new_val = 1
            slider.set(new_val)

        drift(self.sl_charge_dur, 0.2)
        drift(self.sl_charge_swell, 0.2)
        drift(self.sl_charge_rise, 0.2)
        drift(self.sl_shot_impact, 0.2)
        drift(self.sl_shot_tail, 0.5)
        drift(self.sl_shot_aggro, 0.2)
        
        self.lbl_status.configure(text="Randomized parameters.")
        self.generate()

    def save_wav(self):
        if self.generated_audio is None:
            self.lbl_status.configure(text="Generate first!")
            return
            
        params = self.get_params()
        prefix = params["shot"]["type"]
        timestamp = int(time.time())
        default_name = f"{prefix}_{timestamp}.wav"
        
        # Save dialog
        # Use simple os path or file dialog
        # Default to ./output
        os.makedirs("output", exist_ok=True)
        path = os.path.join("output", default_name)
        
        sf.write(path, self.generated_audio, self.engine.sr, subtype='PCM_16')
        self.lbl_status.configure(text=f"Saved: {path}")

if __name__ == "__main__":
    app = WeaponGenApp()
    app.mainloop()
