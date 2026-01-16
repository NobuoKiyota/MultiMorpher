import customtkinter as ctk
import pyaudio
import numpy as np
import threading
import time
import mido
import tkinter as tk
import random
import json
import os
from tkinter import messagebox, filedialog
from pyserum_engine import SerumEngine, SR, BLOCK_SIZE, CHANNELS, NUM_FRAMES, TABLE_SIZE
from pyserum_gui_components import EnvelopeEditor, VirtualKeyboard, RotaryKnob

# --- COLOR PALETTE ---
COLOR_BG_MAIN = "#16181c"
COLOR_BG_PANEL = "#23262b"
COLOR_ACCENT_A = "#00e5ff" 
COLOR_ACCENT_B = "#ffaa00" 
COLOR_TEXT = "#eeeeee"
COLOR_KNOB_TRACK = "#111111"
COLOR_SCOPE_LINE = "#00e5ff"
COLOR_SCOPE_FILL = "#004044" 

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green") 

class PySerumApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("PySerum SFX Generator (Step 11: Oscillator Deep Dive)")
        self.geometry("900x950") 
        self.resizable(True, True)
        self.configure(fg_color=COLOR_BG_MAIN) 
        
        # Audio Engine
        self.engine = SerumEngine()
        self.pya = pyaudio.PyAudio()
        self.stream = None
        self.is_running = True
        
        # State
        self.current_waveform = np.zeros(BLOCK_SIZE)
        self.lock = threading.Lock()
        self.locks = {} 
        self.preview_mode = False
        
        self.preset_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets")
        if not os.path.exists(self.preset_dir): os.makedirs(self.preset_dir)

        # MIDI
        self.midi_in = None
        self.midi_port_name = None
        
        self._init_ui()
        self._start_audio()
        
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(50, self.update_scope)

    def _init_ui(self):
        # --- HEADER ---
        self.frame_top = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_top.pack(fill="x", padx=5, pady=5)
        
        ctk.CTkLabel(self.frame_top, text="PySerum", font=("Arial", 20, "bold"), text_color=COLOR_TEXT).pack(side="left", padx=10)
        
        # MIDI
        try: ports = mido.get_input_names()
        except: ports = []
        if not ports: ports = ["No MIDI Devices"]
        self.opt_midi = ctk.CTkOptionMenu(self.frame_top, values=ports, command=self.change_midi_port, width=150, fg_color=COLOR_BG_PANEL)
        self.opt_midi.pack(side="left", padx=10)
        
        # GENERATE
        self.btn_gen = ctk.CTkButton(self.frame_top, text="🎲 Generate", fg_color=COLOR_ACCENT_A, text_color="black", hover_color="#88ffff", 
                                     width=100, font=("Arial", 12, "bold"), command=self.generate_random_patch)
        self.btn_gen.pack(side="left", padx=15)
        
        # Right Side Header
        self.knob_master = self._add_knob(self.frame_top, "Master", 0.0, 1.0, 0.8, command=self.update_master, side="right", color=COLOR_ACCENT_A)
        
        # Level Meter Canvas
        self.meter_canvas = tk.Canvas(self.frame_top, width=15, height=80, bg="#222", highlightthickness=0)
        self.meter_canvas.pack(side="right", padx=5)
        
        self.btn_open = ctk.CTkButton(self.frame_top, text="Open", fg_color=COLOR_BG_PANEL, hover_color="#444", width=60, command=self.load_preset)
        self.btn_open.pack(side="right", padx=5)
        self.btn_save = ctk.CTkButton(self.frame_top, text="Save", fg_color=COLOR_BG_PANEL, hover_color="#444", width=60, command=self.save_preset)
        self.btn_save.pack(side="right", padx=5)

        # --- SCOPE ---
        self.frame_scope = ctk.CTkFrame(self, fg_color="black", height=100, corner_radius=0)
        self.frame_scope.pack(fill="x", padx=5, pady=2)
        self.scope_canvas = tk.Canvas(self.frame_scope, bg="black", height=100, highlightthickness=0)
        self.scope_canvas.pack(fill="x", expand=True)

        # --- MIDDLE SECTION (OSC / FX) ---
        self.tab_view = ctk.CTkTabview(self, height=380, fg_color=COLOR_BG_PANEL, segmented_button_fg_color=COLOR_BG_MAIN, segmented_button_selected_color=COLOR_BG_PANEL)
        self.tab_view.pack(fill="x", padx=5, pady=5)
        self.tab_osc = self.tab_view.add("OSC")
        self.tab_fx = self.tab_view.add("FX")
        
        self._init_osc_tab()
        self._init_fx_tab()

        # --- BOTTOM SECTION (LFO & ENV) ---
        self.frame_bottom = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_bottom.pack(fill="both", expand=True, padx=5, pady=5)
        self.frame_bottom.grid_columnconfigure(0, weight=1)
        self.frame_bottom.grid_columnconfigure(1, weight=1)
        self.frame_bottom.grid_columnconfigure(2, weight=1)
        
        # Panel 1: Amp Env
        p_amp = ctk.CTkFrame(self.frame_bottom, fg_color=COLOR_BG_PANEL)
        p_amp.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        ctk.CTkLabel(p_amp, text="Amp Env", font=("Arial", 12, "bold"), text_color=COLOR_TEXT).pack(pady=2)
        self.env_amp = EnvelopeEditor(p_amp, height=140, callback=self.update_adsr_amp, 
                                      bg_color=COLOR_BG_PANEL, line_color=COLOR_ACCENT_A, fill_color="#003333")
        self.env_amp.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Panel 2: Mod Env
        p_mod = ctk.CTkFrame(self.frame_bottom, fg_color=COLOR_BG_PANEL)
        p_mod.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        ctk.CTkLabel(p_mod, text="Mod Env", font=("Arial", 12, "bold"), text_color=COLOR_TEXT).pack(pady=2)
        f_me_main = ctk.CTkFrame(p_mod, fg_color="transparent")
        f_me_main.pack(fill="both", expand=True)
        f_me_k = ctk.CTkFrame(f_me_main, fg_color="transparent")
        f_me_k.pack(side="left", padx=2)
        self.knob_me_cut = self._add_knob_with_lock(f_me_k, "Cut", -1.0, 1.0, 0.0, self.update_mod_env_params, color=COLOR_ACCENT_A)
        self.knob_me_pitch = self._add_knob_with_lock(f_me_k, "Pitch", -48, 48, 0, self.update_mod_env_params, color=COLOR_ACCENT_A)
        self.env_mod = EnvelopeEditor(f_me_main, height=140, callback=self.update_adsr_mod,
                                      bg_color=COLOR_BG_PANEL, line_color=COLOR_ACCENT_A, fill_color="#003333")
        self.env_mod.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        
        # Panel 3: LFO
        p_lfo = ctk.CTkFrame(self.frame_bottom, fg_color=COLOR_BG_PANEL)
        p_lfo.grid(row=0, column=2, sticky="nsew", padx=2, pady=2)
        ctk.CTkLabel(p_lfo, text="LFO 1", font=("Arial", 12, "bold"), text_color=COLOR_ACCENT_A).pack(pady=2)
        self.opt_lfo_shape = ctk.CTkOptionMenu(p_lfo, values=["Sine", "Tri", "Saw"], width=80, command=self.update_lfo, fg_color="#333")
        self.opt_lfo_shape.pack(pady=5)
        f_lfo_k = ctk.CTkFrame(p_lfo, fg_color="transparent")
        f_lfo_k.pack(pady=5)
        self.knob_lfo_rate = self._add_knob_with_lock(f_lfo_k, "Rate", 0.1, 20.0, 1.0, self.update_lfo, grid=(0, 0), color=COLOR_ACCENT_A)
        self.knob_lfo_cut = self._add_knob_with_lock(f_lfo_k, "To Cut", 0.0, 1.0, 0.0, self.update_lfo, grid=(0, 1), color=COLOR_ACCENT_A)
        self.knob_lfo_wt = self._add_knob_with_lock(f_lfo_k, "To WT", 0.0, 1.0, 0.0, self.update_lfo, grid=(0, 2), color=COLOR_ACCENT_A)

        self.kb = VirtualKeyboard(self, start_note=36, num_keys=49, height=80, callback_on=self.kb_note_on, callback_off=self.kb_note_off)
        self.kb.pack(fill="x", padx=5, pady=5)
        
        if ports[0] != "No MIDI Devices":
            self.opt_midi.set(ports[0])
            self.change_midi_port(ports[0])

    def _init_osc_tab(self):
        self.tab_osc.grid_columnconfigure(0, weight=1)
        self.tab_osc.grid_columnconfigure(1, weight=1)
        
        # --- OSC A ---
        fa = ctk.CTkFrame(self.tab_osc, fg_color=COLOR_BG_PANEL)
        fa.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        ctk.CTkLabel(fa, text="OSC A", font=("Arial", 14, "bold"), text_color=COLOR_ACCENT_A).pack(pady=5)
        self.opt_wt_a = ctk.CTkOptionMenu(fa, values=["Classic", "Monster", "Basic Shapes"], command=self.update_osc_a, fg_color="#333", button_color="#444")
        self.opt_wt_a.set("Classic")
        self.opt_wt_a.pack(pady=5)
        
        fk_a = ctk.CTkFrame(fa, fg_color="transparent")
        fk_a.pack(pady=5)
        
        # Row 1: Oct, Semi, Fine, Pan, Level
        self.knob_oct_a = self._add_knob_with_lock(fk_a, "Oct", -3, 3, 0, self.update_osc_a, grid=(0,0), color=COLOR_ACCENT_A)
        self.knob_semi_a = self._add_knob_with_lock(fk_a, "Semi", -12, 12, 0, self.update_osc_a, grid=(0,1), color=COLOR_ACCENT_A)
        self.knob_fine_a = self._add_knob_with_lock(fk_a, "Fine", -100, 100, 0, self.update_osc_a, grid=(0,2), color=COLOR_ACCENT_A)
        self.knob_pan_a = self._add_knob_with_lock(fk_a, "Pan", -1.0, 1.0, 0.0, self.update_osc_a, grid=(0,3), color=COLOR_ACCENT_A)
        self.knob_vol_a = self._add_knob_with_lock(fk_a, "Level", 0.0, 1.0, 0.8, self.update_osc_a, grid=(0,4), color=COLOR_ACCENT_A)

        # Row 2: WT Pos, Unison, Detune, Phase, Rand(Switch)
        self.knob_pos_a = self._add_knob_with_lock(fk_a, "WT Pos", 0.0, 1.0, 0.0, self.update_osc_a, grid=(1,0), color=COLOR_ACCENT_A)
        self.knob_uni_a = self._add_knob_with_lock(fk_a, "Unison", 0, 7, 0, self.update_osc_a, grid=(1,1), color=COLOR_ACCENT_A)
        # We reused "Unison" knob for Detune/Spread previously. Now we have explicit Unison count?
        # Engine supports 7 fixed voices, active via Unison spread > 0.
        # "Unison" usually means Count. "Detune" means Spread.
        # pyserum_engine just has `unison_a` (spread/detune amt).
        # We should call this "Detune".
        # Let's keep existing engine mapping: `knob_uni_a` controls spread/detune amount.
        # So label it "Detune".
        self.knob_uni_a.lbl_text.configure(text="Detune") # Rename existing logic
        self.knob_uni_a.configure(height=80) 
        
        # New Phase controls
        self.knob_phase_a = self._add_knob_with_lock(fk_a, "Phase", 0.0, 1.0, 0.0, self.update_osc_a, grid=(1,2), color=COLOR_ACCENT_A)
        
        # Rand Phase Switch
        f_r_a = ctk.CTkFrame(fk_a, fg_color="transparent")
        f_r_a.grid(row=1, column=3, padx=2)
        ctk.CTkLabel(f_r_a, text="Rand", font=("Arial", 9), text_color="#aaaaaa").pack()
        self.sw_rand_a = ctk.CTkSwitch(f_r_a, text="", width=40, command=self.update_osc_a, progress_color=COLOR_ACCENT_A)
        self.sw_rand_a.pack()
        # Add lock for rand?
        self.locks[self.sw_rand_a] = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(f_r_a, text="", variable=self.locks[self.sw_rand_a], width=16, height=16, corner_radius=3, fg_color=COLOR_ACCENT_A).pack()

        # --- OSC B ---
        fb = ctk.CTkFrame(self.tab_osc, fg_color=COLOR_BG_PANEL)
        fb.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        ctk.CTkLabel(fb, text="OSC B", font=("Arial", 14, "bold"), text_color=COLOR_ACCENT_B).pack(pady=5)
        self.opt_wt_b = ctk.CTkOptionMenu(fb, values=["Classic", "Monster", "Basic Shapes"], command=self.update_osc_b, fg_color="#333", button_color="#444")
        self.opt_wt_b.set("Monster")
        self.opt_wt_b.pack(pady=5)
        
        fk_b = ctk.CTkFrame(fb, fg_color="transparent")
        fk_b.pack(pady=5)
        
        self.knob_oct_b = self._add_knob_with_lock(fk_b, "Oct", -3, 3, 0, self.update_osc_b, grid=(0,0), color=COLOR_ACCENT_B)
        self.knob_semi_b = self._add_knob_with_lock(fk_b, "Semi", -12, 12, 0, self.update_osc_b, grid=(0,1), color=COLOR_ACCENT_B)
        self.knob_fine_b = self._add_knob_with_lock(fk_b, "Fine", -100, 100, 0, self.update_osc_b, grid=(0,2), color=COLOR_ACCENT_B)
        self.knob_pan_b = self._add_knob_with_lock(fk_b, "Pan", -1.0, 1.0, 0.0, self.update_osc_b, grid=(0,3), color=COLOR_ACCENT_B)
        self.knob_vol_b = self._add_knob_with_lock(fk_b, "Level", 0.0, 1.0, 0.0, self.update_osc_b, grid=(0,4), color=COLOR_ACCENT_B)
        
        self.knob_pos_b = self._add_knob_with_lock(fk_b, "WT Pos", 0.0, 1.0, 0.0, self.update_osc_b, grid=(1,0), color=COLOR_ACCENT_B)
        self.knob_uni_b = self._add_knob_with_lock(fk_b, "Detune", 0, 7, 0, self.update_osc_b, grid=(1,1), color=COLOR_ACCENT_B)
        self.knob_uni_b.lbl_text.configure(text="Detune")
        
        self.knob_phase_b = self._add_knob_with_lock(fk_b, "Phase", 0.0, 1.0, 0.0, self.update_osc_b, grid=(1,2), color=COLOR_ACCENT_B)
        
        f_r_b = ctk.CTkFrame(fk_b, fg_color="transparent")
        f_r_b.grid(row=1, column=3, padx=2)
        ctk.CTkLabel(f_r_b, text="Rand", font=("Arial", 9), text_color="#aaaaaa").pack()
        self.sw_rand_b = ctk.CTkSwitch(f_r_b, text="", width=40, command=self.update_osc_b, progress_color=COLOR_ACCENT_B)
        self.sw_rand_b.pack()
        self.locks[self.sw_rand_b] = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(f_r_b, text="", variable=self.locks[self.sw_rand_b], width=16, height=16, corner_radius=3, fg_color=COLOR_ACCENT_B).pack()

    def _init_fx_tab(self):
        f = ctk.CTkFrame(self.tab_fx, fg_color="transparent")
        f.pack(fill="both", expand=True, padx=2, pady=2)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)
        f.grid_columnconfigure(2, weight=1)
        
        c1 = ctk.CTkFrame(f, fg_color=COLOR_BG_PANEL)
        c1.grid(row=0, column=0, sticky="nsew", padx=2)
        self.sw_filter = ctk.CTkSwitch(c1, text="Filter", command=self.update_filter, progress_color=COLOR_ACCENT_A)
        self.sw_filter.pack(pady=10)
        self.knob_cutoff = self._add_knob_with_lock(c1, "Cutoff", 20, 20000, 20000, self.update_filter, color=COLOR_ACCENT_A)
        self.knob_cutoff.pack()
        
        c2 = ctk.CTkFrame(f, fg_color=COLOR_BG_PANEL)
        c2.grid(row=0, column=1, sticky="nsew", padx=2)
        self.sw_dist = ctk.CTkSwitch(c2, text="Distort", command=self.update_dist, progress_color=COLOR_ACCENT_A)
        self.sw_dist.pack(pady=10)
        self.knob_drive = self._add_knob_with_lock(c2, "Drive", 0.0, 1.0, 0.0, self.update_dist, color=COLOR_ACCENT_A)
        self.knob_drive.pack()
        
        c3 = ctk.CTkFrame(f, fg_color=COLOR_BG_PANEL)
        c3.grid(row=0, column=2, sticky="nsew", padx=2)
        self.sw_delay = ctk.CTkSwitch(c3, text="Delay", command=self.update_delay, progress_color=COLOR_ACCENT_A)
        self.sw_delay.pack(pady=10)
        
        dk = ctk.CTkFrame(c3, fg_color="transparent")
        dk.pack()
        self.knob_d_time = self._add_knob_with_lock(dk, "Time", 0.01, 1.0, 0.25, self.update_delay, grid=(0,0), color=COLOR_ACCENT_A)
        self.knob_d_fb = self._add_knob_with_lock(dk, "Fdbk", 0.0, 0.9, 0.4, self.update_delay, grid=(0,1), color=COLOR_ACCENT_A)
        self.knob_d_mix = self._add_knob_with_lock(dk, "Mix", 0.0, 1.0, 0.3, self.update_delay, grid=(0,2), color=COLOR_ACCENT_A)

    def _add_knob(self, parent, text, vmin, vmax, vdef, command, side="left", color=COLOR_ACCENT_A):
        k = RotaryKnob(parent, text=text, from_=vmin, to=vmax, start_val=vdef, command=command, progress_color=color, track_color=COLOR_KNOB_TRACK)
        k.pack(side=side, padx=5)
        return k

    def _add_knob_with_lock(self, parent, text, vmin, vmax, vdef, command, grid=None, color=COLOR_ACCENT_A):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        if grid: f.grid(row=grid[0], column=grid[1], padx=1, pady=1)
        else: f.pack(side="left", padx=2, pady=2)
            
        k = RotaryKnob(f, text=text, from_=vmin, to=vmax, start_val=vdef, command=command, width=50, height=70, 
                       progress_color=color, track_color=COLOR_KNOB_TRACK)
        k.pack()
        var = ctk.BooleanVar(value=False)
        self.locks[k] = var
        ctk.CTkCheckBox(f, text="", variable=var, width=16, height=16, corner_radius=3, fg_color=color, hover_color="#555").pack()
        return k

    def save_preset(self):
        filename = filedialog.asksaveasfilename(initialdir=self.preset_dir, title="Save Preset", filetypes=(("JSON", "*.json"),), defaultextension=".json")
        if not filename: return
        state = self.engine.get_patch_state()
        state["osc_a"]["table_name"] = self.opt_wt_a.get()
        state["osc_b"]["table_name"] = self.opt_wt_b.get()
        try:
            with open(filename, 'w') as f: json.dump(state, f, indent=4)
            messagebox.showinfo("Saved", f"Saved:\n{os.path.basename(filename)}")
        except Exception as e: messagebox.showerror("Error", str(e))

    def load_preset(self):
        filename = filedialog.askopenfilename(initialdir=self.preset_dir, title="Open Preset", filetypes=(("JSON", "*.json"),))
        if not filename: return
        try:
            with open(filename, 'r') as f: state = json.load(f)
            self.engine.set_patch_state(state)
            self.opt_wt_a.set(state.get("osc_a", {}).get("table_name", "Classic"))
            self.opt_wt_b.set(state.get("osc_b", {}).get("table_name", "Monster"))
            self.sync_gui_from_engine()
        except Exception as e: messagebox.showerror("Error", str(e))

    def sync_gui_from_engine(self):
        self.knob_pos_a.set(self.engine.pos_a); self.knob_uni_a.set(self.engine.unison_a); self.knob_vol_a.set(self.engine.vol_a);
        self.knob_semi_a.set(self.engine.semi_a); self.knob_oct_a.set(self.engine.oct_a); self.knob_fine_a.set(self.engine.fine_a)
        self.knob_pan_a.set(self.engine.pan_a); self.knob_phase_a.set(self.engine.phase_val_a); 
        if self.engine.phase_rand_a: self.sw_rand_a.select() 
        else: self.sw_rand_a.deselect()
        
        self.knob_pos_b.set(self.engine.pos_b); self.knob_uni_b.set(self.engine.unison_b); self.knob_vol_b.set(self.engine.vol_b); 
        self.knob_semi_b.set(self.engine.semi_b); self.knob_oct_b.set(self.engine.oct_b); self.knob_fine_b.set(self.engine.fine_b)
        self.knob_pan_b.set(self.engine.pan_b); self.knob_phase_b.set(self.engine.phase_val_b); 
        if self.engine.phase_rand_b: self.sw_rand_b.select() 
        else: self.sw_rand_b.deselect()

        if self.engine.fx_filter.enabled: self.sw_filter.select()
        else: self.sw_filter.deselect()
        self.knob_cutoff.set(self.engine.base_cutoff)
        
        self.knob_lfo_rate.set(self.engine.lfo.rate); self.opt_lfo_shape.set(self.engine.lfo.shape)
        self.knob_lfo_cut.set(self.engine.mod_cutoff); self.knob_lfo_wt.set(self.engine.mod_wt)
        
        if self.engine.fx_dist.enabled: self.sw_dist.select() 
        else: self.sw_dist.deselect()
        self.knob_drive.set(self.engine.fx_dist.drive)
        
        if self.engine.fx_delay.enabled: self.sw_delay.select()
        else: self.sw_delay.deselect()
        self.knob_d_time.set(self.engine.fx_delay.time); self.knob_d_fb.set(self.engine.fx_delay.feedback); self.knob_d_mix.set(self.engine.fx_delay.mix)
        
        v0 = self.engine.voices[0]
        self.env_amp.set_params(v0.adsr.attack_time, v0.adsr.decay_time, v0.adsr.sustain_level, v0.adsr.release_time)
        self.env_mod.set_params(v0.adsr_mod.attack_time, v0.adsr_mod.decay_time, v0.adsr_mod.sustain_level, v0.adsr_mod.release_time)
        self.knob_me_cut.set(self.engine.mod_env_amt_cutoff); self.knob_me_pitch.set(self.engine.mod_env_amt_pitch)
        
        self.update_osc_a(); self.update_osc_b() # Ensure preview 

    def update_master(self, _=None): pass
    def _audio_callback(self, in_data, frame_count, time_info, status):
        data = self.engine.generate_block()
        vol = self.knob_master.get()
        data *= vol
        stereo = data.reshape(-1, 2)
        if not self.preview_mode:
            self.current_waveform = stereo[:, 0].copy()
        return (data.astype(np.float32).tobytes(), pyaudio.paContinue)
    def _start_audio(self):
        self.stream = self.pya.open(format=pyaudio.paFloat32, channels=CHANNELS, rate=SR, output=True, frames_per_buffer=BLOCK_SIZE, stream_callback=self._audio_callback)
        self.stream.start_stream()

    def update_osc_a(self, _=None): 
        self.engine.set_osc_a_params(self.opt_wt_a.get(), self.knob_pos_a.get(), self.knob_uni_a.get(), self.knob_vol_a.get(), self.knob_semi_a.get(), 
                                     self.knob_oct_a.get(), self.knob_fine_a.get(), self.knob_pan_a.get(), self.knob_phase_a.get(), bool(self.sw_rand_a.get()))
        self.update_preview()
    
    def update_osc_b(self, _=None): 
        self.engine.set_osc_b_params(self.opt_wt_b.get(), self.knob_pos_b.get(), self.knob_uni_b.get(), self.knob_vol_b.get(), self.knob_semi_b.get(),
                                     self.knob_oct_b.get(), self.knob_fine_b.get(), self.knob_pan_b.get(), self.knob_phase_b.get(), bool(self.sw_rand_b.get()))
        self.update_preview()

    def update_adsr_amp(self, a, d, s, r): self.engine.set_adsr(a, d, s, r)
    def update_adsr_mod(self, a, d, s, r): self.update_mod_env_params()
    def update_mod_env_params(self, _=None): a,d,s,r=self.env_mod.get_params(); self.engine.set_mod_adsr(a,d,s,r, self.knob_me_cut.get(), self.knob_me_pitch.get())
    def update_filter(self, _=None): self.engine.set_filter(self.sw_filter.get(), self.knob_cutoff.get())
    def update_dist(self, _=None): self.engine.set_dist(self.sw_dist.get(), self.knob_drive.get())
    def update_delay(self, _=None): self.engine.set_delay(self.sw_delay.get(), self.knob_d_time.get(), self.knob_d_fb.get(), self.knob_d_mix.get())
    def update_lfo(self, _=None): self.engine.set_lfo(self.knob_lfo_rate.get(), self.opt_lfo_shape.get(), self.knob_lfo_cut.get(), self.knob_lfo_wt.get())

    def update_preview(self):
        # Render current Wavetable shape for preview in scope
        # Priority: OSC A if active, else OSC B. Or just OSC A for now.
        # Ideally, mix both if both active, but they are mixed by voices in realtime.
        # Here we just want to see the shape of the table at current position.
        
        # We need to access the table frame manually
        # Engine has table_a_frames
        
        pos_idx = self.engine.pos_a * (NUM_FRAMES - 1)
        idx0 = int(pos_idx); idx1 = min(idx0 + 1, NUM_FRAMES - 1)
        alpha = pos_idx - idx0
        wave = (1.0 - alpha) * self.engine.table_a_frames[idx0] + alpha * self.engine.table_a_frames[idx1]
        
        # Resample for scope (2048 samples -> 512 samples)
        step = max(1, len(wave) // BLOCK_SIZE)
        # Actually scope updates at its own rate. We can just set current_waveform to this static wave if engine is idle?
        # But engine is always running.
        # User wants preview "when knob moved".
        # Let's override current_waveform for a brief moment or just update it permanently if not playing?
        # Better: if no voice is playing, show preview.
        # But voice playing state is internal.
        # Let's enable "Preview Mode" for 1 sec after knob move?
        self.current_waveform = wave[:BLOCK_SIZE] # Just take first chunk or resample?
        # Table size 2048. Block 512.
        # Just resampling is better.
        indices = np.linspace(0, TABLE_SIZE-1, BLOCK_SIZE).astype(int)
        self.current_waveform = wave[indices]
        self.preview_mode = True # Flag to stop callback from overwriting?
        # But callback runs 100 times a second.
        # Callback overwrites `self.current_waveform`.
        # I added check `if not self.preview_mode` in callback.
        
        # Let's force preview mode, but handle the cancel safely.
        self.preview_mode = True
        
        # Handle cancel safely
        reset_id = getattr(self, "_preview_reset_id", None)
        if reset_id:
            try:
                self.after_cancel(reset_id)
            except ValueError:
                pass
        
        self._preview_reset_id = self.after(500, lambda: setattr(self, 'preview_mode', False))


    def generate_random_patch(self):
        if not self._is_locked(self.knob_pos_a): self.knob_pos_a.set(random.random())
        if not self._is_locked(self.knob_uni_a): self.knob_uni_a.set(random.choice([0, 0, random.randint(1, 7)]))
        if not self._is_locked(self.knob_vol_a): self.knob_vol_a.set(random.uniform(0.5, 1.0))
        if not self._is_locked(self.knob_semi_a): self.knob_semi_a.set(random.choice([-12, -5, 0, 7, 12]))
        if not self._is_locked(self.knob_oct_a): self.knob_oct_a.set(random.randint(-2, 2))
        
        # OSC B 50% chance
        if random.random() < 0.5:
             if not self._is_locked(self.knob_pos_b): self.knob_pos_b.set(random.random())
             if not self._is_locked(self.knob_uni_b): self.knob_uni_b.set(random.choice([0, random.randint(1, 7)]))
             if not self._is_locked(self.knob_vol_b): self.knob_vol_b.set(random.uniform(0.3, 0.7))
             if not self._is_locked(self.knob_oct_b): self.knob_oct_b.set(random.randint(-2, 2))
             if not self._is_locked(self.knob_semi_b): self.knob_semi_b.set(random.choice([-12, 0, 7, 12]))
        else:
             if not self._is_locked(self.knob_vol_b): self.knob_vol_b.set(0.0)
             
        if not self._is_locked(self.knob_pan_a): self.knob_pan_a.set(random.uniform(-0.5, 0.5))
        if not self._is_locked(self.knob_pan_b): self.knob_pan_b.set(random.uniform(-0.5, 0.5))

        if random.random() < 0.7:
             self.sw_filter.select(); 
             if not self._is_locked(self.knob_cutoff): self.knob_cutoff.set(random.uniform(500, 20000))
        else: self.sw_filter.deselect()

        if not self._is_locked(self.knob_lfo_rate): self.knob_lfo_rate.set(random.uniform(0.1, 12.0))
        if not self._is_locked(self.knob_lfo_cut): self.knob_lfo_cut.set(random.choice([0.0, random.uniform(0.0, 1.0)]))
        if not self._is_locked(self.knob_lfo_wt): self.knob_lfo_wt.set(random.choice([0.0, random.uniform(0.0, 1.0)]))
        self.opt_lfo_shape.set(random.choice(["Sine", "Tri", "Saw"]))
        
        self.opt_wt_a.set(random.choice(["Classic", "Monster", "Basic Shapes"]))
        self.opt_wt_b.set(random.choice(["Classic", "Monster", "Basic Shapes"]))
        
        if not self._is_locked(self.knob_me_cut): self.knob_me_cut.set(random.choice([0.0, random.uniform(-1.0, 1.0)]))
        if not self._is_locked(self.knob_me_pitch): self.knob_me_pitch.set(random.choice([0.0, random.uniform(-24, 24)]))

        self.env_amp.set_params(random.uniform(0.001, 0.5), random.uniform(0.1, 2.0), random.uniform(0.0, 1.0), random.uniform(0.1, 2.0))
        self.env_mod.set_params(random.uniform(0.001, 1.0), random.uniform(0.1, 2.0), random.uniform(0.0, 1.0), random.uniform(0.1, 2.0))

        if random.random() < 0.3: self.sw_dist.select()
        else: self.sw_dist.deselect()
        if not self._is_locked(self.knob_drive): self.knob_drive.set(random.uniform(0.0, 0.6))
        
        if random.random() < 0.4: self.sw_delay.select()
        else: self.sw_delay.deselect()
        if not self._is_locked(self.knob_d_time): self.knob_d_time.set(random.uniform(0.1, 0.8))
        if not self._is_locked(self.knob_d_fb): self.knob_d_fb.set(random.uniform(0.0, 0.6))
        if not self._is_locked(self.knob_d_mix): self.knob_d_mix.set(random.uniform(0.1, 0.5))
        
        self.update_osc_a(); self.update_osc_b(); self.update_filter(); self.update_lfo()
        self.update_mod_env_params(); self.update_dist(); self.update_delay()
        a,d,s,r = self.env_amp.get_params(); self.update_adsr_amp(a,d,s,r)
        a,d,s,r = self.env_mod.get_params(); self.update_adsr_mod(a,d,s,r)
        
    def _is_locked(self, knob_widget): return self.locks[knob_widget].get() if knob_widget in self.locks else False

    def kb_note_on(self, note): self.engine.note_on(note)
    def kb_note_off(self, note): self.engine.note_off(note)

    def change_midi_port(self, port_name):
        if port_name == "No MIDI Devices" or (self.midi_port_name == port_name and self.midi_in): return
        if self.midi_in: self.midi_in.close()
        try:
            self.midi_in = mido.open_input(port_name, callback=self.midi_callback)
            self.midi_port_name = port_name
            print(f"Connected: {port_name}")
        except Exception as e: print(f"MIDI Error: {e}")
    def midi_callback(self, msg):
        if msg.type == 'note_on': self.engine.note_on(msg.note) if msg.velocity > 0 else self.engine.note_off(msg.note)
        elif msg.type == 'note_off': self.engine.note_off(msg.note)

    def update_scope(self):
        if not self.is_running: return
        w = max(10, self.scope_canvas.winfo_width())
        h = max(10, self.scope_canvas.winfo_height())
        mid_y = h / 2
        data = self.current_waveform
        step = max(1, len(data) // w)
        plot = data[::step]
        points = [0, h] 
        for i, val in enumerate(plot):
            x = i
            y = mid_y - (val * mid_y * 0.9)
            points.extend([x, y])
        points.extend([len(plot), h])
        
        self.scope_canvas.delete("all")
        if len(points) > 4:
            self.scope_canvas.create_polygon(points, fill=COLOR_SCOPE_FILL, outline="")
            self.scope_canvas.create_line(points[2:-2], fill=COLOR_SCOPE_LINE, width=2)
            
        self.after(50, self.update_scope)
        self.update_meter()

    def update_meter(self):
        if len(self.current_waveform) > 0:
             peak = np.max(np.abs(self.current_waveform))
        else: peak = 0.0
        
        if hasattr(self, "meter_canvas"):
            self.meter_canvas.delete("all")
            w = self.meter_canvas.winfo_width()
            h = self.meter_canvas.winfo_height()
            
            self.meter_canvas.create_rectangle(0, 0, w, h, fill="#333", outline="")
            
            meter_h = h * peak
            if meter_h > h: meter_h = h
            
            c = "#00ff00"
            if peak > 0.8: c = "#ffff00"
            if peak > 0.95: c = "#ff0000"
            
            self.meter_canvas.create_rectangle(0, h-meter_h, w, h, fill=c, outline="")

    def on_close(self):
        self.is_running = False
        if self.stream: self.stream.stop_stream(); self.stream.close()
        self.pya.terminate()
        if self.midi_in: self.midi_in.close()
        self.destroy()

if __name__ == "__main__":
    app = PySerumApp()
    app.mainloop()
