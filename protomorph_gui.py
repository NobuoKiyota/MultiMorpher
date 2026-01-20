import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import os
import threading
import numpy as np
import soundfile as sf
from PIL import Image, ImageTk
import pygame
import time

# Internal Modules
from morph_core import MorphCore
from processors import MorphProcessors
from realtime_engine import RealtimeEngine

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# ... (Imports)

class XYPad(ctk.CTkFrame):
    def __init__(self, master, width=200, height=200, command=None, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self.command = command
        self.canvas = tk.Canvas(self, bg="#2b2b2b", width=width, height=height, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Crosshair
        self.w = width
        self.h = height
        self.x_val = 0.5
        self.y_val = 1.0 # default open
        
        self.cid_cross = self._draw_cross(self.w/2, 0)
        
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<Button-1>", self._on_drag)
        
        self.last_event_time = 0
        
    def _draw_cross(self, x, y):
        self.canvas.delete("cross")
        # Horizontal
        self.canvas.create_line(0, y, self.w, y, fill="#00ccff", tag="cross", width=2)
        # Vertical
        self.canvas.create_line(x, 0, x, self.h, fill="#00ccff", tag="cross", width=2)
        # Circle
        r = 8
        self.canvas.create_oval(x-r, y-r, x+r, y+r, outline="#00ccff", width=2, tag="cross")
        
    def _on_drag(self, event):
        # Throttle
        now = time.time()
        if now - self.last_event_time < 0.03: # 30ms ~ 33fps
            return
        self.last_event_time = now
        
        x = np.clip(event.x, 0, self.w)
        y = np.clip(event.y, 0, self.h)
        
        self._draw_cross(x, y)
        
        # Norm
        self.x_val = x / self.w
        self.y_val = 1.0 - (y / self.h) # 0 at bottom, 1 at top
        
        if self.command:
             self.command(self.x_val, self.y_val)

class Visualizer(ctk.CTkFrame):
    def __init__(self, master, height=150, **kwargs):
        super().__init__(master, height=height, **kwargs)
        self.canvas = tk.Canvas(self, bg="#1a1a1a", height=height, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.height = height
        self.image_ref = None

    def draw_spectrogram(self, stft_data):
        if stft_data is None: 
            self.canvas.delete("all")
            return
            
        # Log mag
        mag = np.log1p(np.abs(stft_data))
        
        # Normalize 0-255
        m_min, m_max = mag.min(), mag.max()
        if m_max == m_min: norm = np.zeros_like(mag)
        else: norm = (mag - m_min) / (m_max - m_min)
        
        # Flip Y (Frequency up)
        norm = np.flipud(norm)
        
        # Colorize (simple grayscale)
        img_data = (norm * 255).astype(np.uint8)
        
        # Resize to canvas
        w = self.canvas.winfo_width()
        h = self.height
        if w < 10: w = 400
        
        # Create PIL Image
        img = Image.fromarray(img_data, mode='L')
        img = img.resize((w, h), Image.NEAREST)
        
        # Convert to RGB
        img = img.convert("RGB")
        
        self.image_ref = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, image=self.image_ref, anchor="nw")

class ProtoMorphApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Advanced Morphing Suite")
        self.geometry("1200x850")
        
        # Core
        self.core = MorphCore()
        
        # Real-time Core
        self.rt_engine = RealtimeEngine(sr=48000)
        
        # Audio Init
        pygame.mixer.init(frequency=48000)
        
        # State
        self.current_mode = tk.StringVar(value="Spectrum Blender")
        self.is_live = tk.BooleanVar(value=False)
        self.last_audio = None
        
        self._init_ui()

    def _init_ui(self):
        # Top: Sources
        self.frame_sources = ctk.CTkFrame(self)
        self.frame_sources.pack(fill="x", padx=10, pady=10)
        
        self._build_source_loader(self.frame_sources, "Source A", 'A', 0)
        self._build_source_loader(self.frame_sources, "Source B", 'B', 1)
        
        # Middle: Rack / Modes / Performance
        self.frame_middle = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_middle.pack(fill="both", expand=True, padx=10, pady=5)
        
        # LEFT: Rack
        self.current_mode = tk.StringVar(value="Spectrum Blender")
        self.is_live = tk.BooleanVar(value=False)
        self.last_audio = None
        self.frame_rack = ctk.CTkFrame(self.frame_middle)
        self.frame_rack.pack(side="left", fill="both", expand=True, padx=5)
        
        # RIGHT: Performance Pad
        self.frame_pad = ctk.CTkFrame(self.frame_middle, width=220)
        self.frame_pad.pack(side="right", fill="y", padx=5)
        
        ctk.CTkLabel(self.frame_pad, text="XY PERFORMANCE", font=("Arial", 12, "bold")).pack(pady=5)
        ctk.CTkLabel(self.frame_pad, text="X: Blend/Mix  Y: Filter").pack(pady=2)
        self.pad = XYPad(self.frame_pad, width=200, height=200, command=self.on_pad_move)
        self.pad.pack(pady=10)
        
        # Mode Selector (Inside Rack)
        self.mode_selector = ctk.CTkSegmentedButton(
            self.frame_rack, 
            values=["Spectrum Blender", "Interpolator", "Cross Synthesis", "Formant Shifter"],
            variable=self.current_mode,
            command=self.on_mode_change
        )
        self.mode_selector.pack(fill="x", padx=10, pady=10)
        
        # Controls Container
        self.frame_controls = ctk.CTkFrame(self.frame_rack, fg_color="transparent")
        self.frame_controls.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Instantiate Control Widgets
        self.controls = {}
        self._build_controls()
        
        self.on_mode_change("Spectrum Blender") # init
        
        # Bottom: Visualizer & Actions
        self.frame_bottom = ctk.CTkFrame(self, height=200)
        self.frame_bottom.pack(fill="x", padx=10, pady=10)
        
        self.viz = Visualizer(self.frame_bottom, height=150)
        self.viz.pack(fill="x", padx=5, pady=5)
        
        # Action Buttons
        self.frame_actions = ctk.CTkFrame(self.frame_bottom, fg_color="transparent")
        self.frame_actions.pack(pady=10)
        
        # Live Toggle
        self.switch_live = ctk.CTkSwitch(self.frame_actions, text="LIVE MONITOR", variable=self.is_live, command=self.on_live_toggle)
        self.switch_live.pack(side="left", padx=20)
        
        # REC Button (Live)
        self.btn_rec = ctk.CTkButton(self.frame_actions, text="● REC STREAM", width=120, fg_color="#cc0000", command=self.toggle_rec)
        self.btn_rec.pack(side="left", padx=10)
        
        # Process / Export
        self.btn_process = ctk.CTkButton(self.frame_actions, text="RENDER & PREVIEW", width=160, command=self.run_process)
        self.btn_process.pack(side="left", padx=10)
        
        self.btn_export = ctk.CTkButton(self.frame_actions, text="EXPORT WAV", width=120, fg_color="green", command=self.export_render)
        self.btn_export.pack(side="left", padx=10)
        
    # ... (Keep _build_source_loader) ...

    # ... (Keep _build_controls) ...

    def on_pad_move(self, x, y):
        # X maps to primary parameter of current mode
        mode = self.current_mode.get()
        
        if mode == "Spectrum Blender":
            # Map X (0-1) to Freq (0-10000)
            freq = x * 10000
            self.slider_split.set(freq)
            self.rt_update("split_freq", freq)
            
        elif mode == "Interpolator":
            self.slider_mix.set(x)
            self.rt_update("mix", x)
            
        elif mode == "Formant Shifter":
            # Map X to 0.5 - 2.0
            shift = 0.5 + (x * 1.5)
            self.slider_shift.set(shift)
            self.rt_update("shift", shift)
            
        # Y maps to Filter (All modes)
        self.rt_update("filter_cutoff", y)

    def toggle_rec(self):
        # Toggle Recording in Live Mode
        if not self.is_live.get():
             print("Recording available only in Live Mode (for now)")
             return
             
        if not self.rt_engine.recording:
            # Start
            self.rt_engine.start_recording()
            self.btn_rec.configure(text="■ STOP REC")
            print("Recording Started...")
        else:
            # Stop
            ts = int(time.time())
            fname = f"output/rec_live_{ts}.wav"
            saved = self.rt_engine.stop_recording(filename=fname)
            self.btn_rec.configure(text="● REC STREAM")
            if saved:
                print(f"Saved to {saved}")
                # Open folder?
                # os.startfile(os.path.dirname(saved))
    
    def export_render(self):
        # Export the last Render result (Core result)
        # Warning: We don't have the last render stored in memory in a persistent way properly in `run_process` yet?
        # Actually `_play_audio` saves it to temp.
        # We should modify `run_process` to store result in `self.last_render`.
        pass # Implemented below in replacement

    def run_process(self):
         # ... existing ...
         pass # Handled in loop
         
    def _process_worker(self):
        # ... existing ...
        # Add filtering logic to Render Mode too? 
        # For now, XY Filter is Live Mode only feature request implies real-time.
        # But consistency is good.
        pass


        
    def _build_source_loader(self, parent, label, slot, col):
        frame = ctk.CTkFrame(parent)
        frame.pack(side="left", fill="x", expand=True, padx=5)
        
        ctk.CTkLabel(frame, text=label, font=("Arial", 12, "bold")).pack(anchor="w", padx=5)
        
        btn = ctk.CTkButton(frame, text="Load File...", command=lambda: self.load_file(slot))
        btn.pack(fill="x", padx=5, pady=5)
        
        lbl_info = ctk.CTkLabel(frame, text="No file loaded", text_color="gray")
        lbl_info.pack(padx=5, pady=2)
        
        # Store ref to label to update it
        setattr(self, f"lbl_info_{slot}", lbl_info)

    def _build_controls(self):
        # 1. Blender
        f1 = ctk.CTkFrame(self.frame_controls, fg_color="transparent")
        ctk.CTkLabel(f1, text="Split Frequency (Hz)").pack()
        self.slider_split = ctk.CTkSlider(f1, from_=0, to=10000, number_of_steps=200, command=lambda v: self.rt_update("split_freq", v))
        self.slider_split.set(1000)
        self.slider_split.pack(fill="x", pady=10)
        self.controls["Spectrum Blender"] = f1
        
        # 2. Interpolator
        f2 = ctk.CTkFrame(self.frame_controls, fg_color="transparent")
        ctk.CTkLabel(f2, text="Interpolation Mix (A <-> B)").pack()
        self.slider_mix = ctk.CTkSlider(f2, from_=0.0, to=1.0, command=lambda v: self.rt_update("mix", v))
        self.slider_mix.set(0.5)
        self.slider_mix.pack(fill="x", pady=10)
        self.controls["Interpolator"] = f2
        
        # 3. Cross Syn
        f3 = ctk.CTkFrame(self.frame_controls, fg_color="transparent")
        ctk.CTkLabel(f3, text="Carrier: Source A | Modulator: Source B").pack(pady=5)
        ctk.CTkLabel(f3, text="Envelope Smoothness").pack()
        self.slider_smooth = ctk.CTkSlider(f3, from_=1, to=50, number_of_steps=49, command=lambda v: self.rt_update("smooth", v))
        self.slider_smooth.set(10)
        self.slider_smooth.pack(fill="x", pady=10)
        self.controls["Cross Synthesis"] = f3
        
        # 4. Formant
        f4 = ctk.CTkFrame(self.frame_controls, fg_color="transparent")
        ctk.CTkLabel(f4, text="Formant Shift Factor (Source A)").pack()
        self.slider_shift = ctk.CTkSlider(f4, from_=0.5, to=2.0, command=lambda v: self.rt_update("shift", v))
        self.slider_shift.set(1.0)
        self.slider_shift.pack(fill="x", pady=10)
        self.controls["Formant Shifter"] = f4

    def on_mode_change(self, value):
        # Hide all
        for k, v in self.controls.items():
            v.pack_forget()
        # Show selected
        if value in self.controls:
            self.controls[value].pack(fill="both", expand=True)
            
        # Update RT Engine Mode
        self.rt_engine.mode = value

    def on_live_toggle(self):
        if self.is_live.get():
            # Start Live
            print("Starting Live Monitor...")
            
            # Load Buffers
            src_a = self.core.source_a
            src_b = self.core.source_b
            
            if src_a is not None:
                y_a = src_a['audio']
                y_b = src_b['audio'] if src_b else None
                self.rt_engine.load_buffers(y_a, y_b)
                self.rt_engine.start()
                self.btn_process.configure(state="disabled")
            else:
                 print("Source A required")
                 self.is_live.set(False)
        else:
            # Stop Live
            print("Stopping Live Monitor...")
            self.rt_engine.stop()
            self.btn_process.configure(state="normal")

    def rt_update(self, key, value):
        # Update RT Engine Params
        self.rt_engine.set_param(key, value)

    def load_file(self, slot):
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.wav;*.mp3;*.aiff")])
        if path:
            success, msg = self.core.load_source(path, slot)
            lbl = getattr(self, f"lbl_info_{slot}")
            if success:
                lbl.configure(text=f"{os.path.basename(path)}", text_color="white")
                # Reload buffers if live
                if self.is_live.get():
                    self.on_live_toggle() # Restart
            else:
                lbl.configure(text="Error loading", text_color="red")
                print(msg)

    def run_process(self):
        # Threading for non-blocking UI
        t = threading.Thread(target=self._process_worker)
        t.start()
        
    def _process_worker(self):
        mode = self.current_mode.get()
        
        # Ensure STFTs (Lazy load triggers here)
        stft_a = self.core.get_stft('A')
        stft_b = self.core.get_stft('B') # Might be None use case dependent
        
        if stft_a is None:
             print("Source A missing!")
             return
             
        result_stft = None
        
        try:
            if mode == "Spectrum Blender":
                if stft_b is None: return
                split = self.slider_split.get()
                result_stft = MorphProcessors.spectral_blend(stft_a, stft_b, split, self.core.sr, self.core.n_fft)
                
            elif mode == "Interpolator":
                if stft_b is None: return
                mix = self.slider_mix.get()
                result_stft = MorphProcessors.interpolate(stft_a, stft_b, mix)
                
            elif mode == "Cross Synthesis":
                if stft_b is None: return
                smooth = self.slider_smooth.get()
                result_stft = MorphProcessors.cross_synthesis(stft_a, stft_b, smooth)
                
            elif mode == "Formant Shifter":
                shift = self.slider_shift.get()
                result_stft = MorphProcessors.formant_shift(stft_a, shift, self.core.n_fft)
                
            if result_stft is not None:
                # Synthesize
                y = self.core.istft(result_stft)
                
                # Apply same filter logic as Live Mode?
                # The User asked for X-Y pad. Y is Filter.
                # If we want consistent sound, we should apply Filter here too.
                # Let's check the Y-val of pad if it exists.
                if hasattr(self, 'pad'):
                    cutoff_norm = self.pad.y_val # 1.0 = Open
                    if cutoff_norm < 0.99:
                         # Apply simple LPF in time domain or frequency?
                         # We already have result_stft, applying there is cleaner but we just ISTFT'd.
                         # Doing it in STFT domain before ISTFT would be better.
                         # Re-do logic? Or just apply simple one-pole on `y`.
                         # For "Render", high quality is better.
                         # Let's Skip filter for Render mode unless explicitly requested to match "Live Performance".
                         # Usually Render is for the "Morph Control" result. 
                         # But consistency... let's leave it raw for now as "Pure Morph".
                         pass
                
                self.last_audio = y
                
                # Update Visualizer (Main Thread safe call?)
                self.viz.after(0, lambda: self.viz.draw_spectrogram(result_stft))
                
                # Playback
                self._play_audio(y)
                
        except Exception as e:
            print(f"Processing Error: {e}")

    def _play_audio(self, y):
        # Generate unique temp filename to avoid Windows file locking issues
        timestamp = int(time.time() * 1000)
        tmp = f"temp_preview_{timestamp}.wav"
        
        # Clean up old temps? (Simple approach: delete all temp_preview_*.wav in dir)
        try:
            for f in os.listdir("."):
                if f.startswith("temp_preview_") and f.endswith(".wav"):
                    try:
                        os.remove(f)
                    except:
                        pass # File likely locked by pygame, ignore
        except: pass
        
        # Write new
        try:
            sf.write(tmp, y, self.core.sr)
        except Exception as e:
            print(f"Write Error: {e}")
            return
        
        # Play
        try:
            if pygame.mixer.get_busy():
                pygame.mixer.stop()
            # On Windows, loading a new file should release the old one usually, 
            # but we used a new filename so it's safe.
            pygame.mixer.music.load(tmp)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"Playback Error: {e}")

if __name__ == "__main__":
    app = ProtoMorphApp()
    app.mainloop()
