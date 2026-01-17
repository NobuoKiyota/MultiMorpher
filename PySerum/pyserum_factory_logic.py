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
from pyserum_engine import SerumEngine, SR, BLOCK_SIZE, CHANNELS, NUM_FRAMES, TABLE_SIZE, AutomationLane
from pyserum_gui_components import EnvelopeEditor, VirtualKeyboard, RotaryKnob, AutomationEditor, LevelMeter

# --- LAYOUT CONFIGURATION (Step 19: Exact Pixel Match) ---
LAYOUT_CFG = {
    # Window
    "window_size": "1200x840",
    
    # Colors
    "bg_main": "#16181c",
    "bg_panel": "#23262b",
    "color_accent_a": "#00e5ff",
    "color_accent_b": "#ffaa00",
    
    # Structure Dimensions
    "left_w": 1080,
    "right_w": 120,
    "total_h": 680,  # Height of top section (Header+Mod+Auto)
    
    # Row Heights (Left Side)
    "h_header": 120,
    "h_modules": 280,
    "h_auto": 280,
    "h_bottom": 160, # Keyboard
    
    # Column Widths
    "w_col_std": 135,
    "w_indicator": 270,
    "w_curve": 270,
    "w_auto_curve": 540,
    "w_scope": 405,
    
    # Inner Widget Sizes
    "knob_w": 50,
    "knob_h": 70,
    "btn_gen_w": 120,
    "btn_io_w": 80,
}

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

class PySerumApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("PySerum SFX Generator (Step 19: Exact Layout)")
        self.geometry(LAYOUT_CFG["window_size"])
        self.resizable(False, False)
        self.configure(fg_color=LAYOUT_CFG["bg_main"])
        
        # Audio Engine
        self.engine = SerumEngine()
        self.pya = pyaudio.PyAudio()
        self.stream = None
        self.is_running = True
        
        # State
        self.current_waveform = np.zeros(BLOCK_SIZE)
        self.block_buffer = np.zeros(BLOCK_SIZE)
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
        # Root Grid: Top (Main+Side) and Bottom (Keys)
        self.grid_rowconfigure(0, weight=0) # Top Area
        self.grid_rowconfigure(1, weight=0) # Bottom Area
        self.grid_columnconfigure(0, weight=0)
        
        # --- TOP AREA (Left Main + Right Sidebar) ---
        self.frame_top = ctk.CTkFrame(self, width=1200, height=LAYOUT_CFG["total_h"], fg_color="transparent")
        self.frame_top.grid(row=0, column=0, sticky="nw")
        self.frame_top.grid_propagate(False)
        
        # Left Container
        self.frame_left = ctk.CTkFrame(self.frame_top, width=LAYOUT_CFG["left_w"], height=LAYOUT_CFG["total_h"], fg_color="transparent")
        self.frame_left.grid(row=0, column=0, sticky="nw")
        self.frame_left.grid_propagate(False)
        
        # Right Sidebar (Level Meter)
        self.frame_right = ctk.CTkFrame(self.frame_top, width=LAYOUT_CFG["right_w"], height=LAYOUT_CFG["total_h"], fg_color=LAYOUT_CFG["bg_panel"])
        self.frame_right.grid(row=0, column=1, sticky="nw")
        self.frame_right.grid_propagate(False)
        
        self.level_meter = LevelMeter(self.frame_right, width=80, height=660) # Padding accounted
        self.level_meter.pack(fill="both", expand=True, padx=5, pady=10)

        # --- LEFT CONTAINER ROWS ---
        # 1. Header
        self.frame_header = ctk.CTkFrame(self.frame_left, width=LAYOUT_CFG["left_w"], height=LAYOUT_CFG["h_header"], fg_color=LAYOUT_CFG["bg_panel"])
        self.frame_header.grid(row=0, column=0, sticky="nw", pady=(0, 1))
        self.frame_header.grid_propagate(False)
        self._init_header(self.frame_header)
        
        # 2. Modules
        self.frame_modules = ctk.CTkFrame(self.frame_left, width=LAYOUT_CFG["left_w"], height=LAYOUT_CFG["h_modules"], fg_color="transparent")
        self.frame_modules.grid(row=1, column=0, sticky="nw", pady=(0, 1))
        self.frame_modules.grid_propagate(False)
        self._init_modules(self.frame_modules)
        
        # 3. Automation & Scope
        self.frame_auto = ctk.CTkFrame(self.frame_left, width=LAYOUT_CFG["left_w"], height=LAYOUT_CFG["h_auto"], fg_color="transparent")
        self.frame_auto.grid(row=2, column=0, sticky="nw", pady=(0, 0))
        self.frame_auto.grid_propagate(False)
        self._init_automation_scope(self.frame_auto)
        
        # --- BOTTOM AREA (Keyboard) ---
        self.frame_bottom = ctk.CTkFrame(self, width=1200, height=LAYOUT_CFG["h_bottom"], fg_color="#000000")
        self.frame_bottom.grid(row=1, column=0, sticky="nw")
        self.frame_bottom.grid_propagate(False)
        
        self.kb = VirtualKeyboard(self.frame_bottom, start_note=36, num_keys=72, height=LAYOUT_CFG["h_bottom"], 
                                  callback_on=self.kb_note_on, callback_off=self.kb_note_off)
        self.kb.pack(fill="both", expand=True)

        # Init MIDI
        try: ports = mido.get_input_names()
        except: ports = []
        if not ports: ports = ["No Device"]
        self.opt_midi.configure(values=ports)
        if ports[0] != "No Device":
            self.opt_midi.set(ports[0])
            self.change_midi_port(ports[0])

    def _init_header(self, parent):
        # 6 Columns: Logo, MIDI, Gen, Indicator, Master, IO
        w_std = LAYOUT_CFG["w_col_std"]
        
        # Col 1: Logo
        f1 = self._make_fixed_frame(parent, 0, w_std, LAYOUT_CFG["h_header"])
        ctk.CTkLabel(f1, text="PySerum", font=("Arial", 20, "bold"), text_color=LAYOUT_CFG["color_accent_a"]).place(relx=0.5, rely=0.5, anchor="center")
        
        # Col 2: MIDI
        f2 = self._make_fixed_frame(parent, 1, w_std, LAYOUT_CFG["h_header"])
        ctk.CTkLabel(f2, text="MIDI In", font=("Arial", 10)).pack(pady=(20, 5))
        self.opt_midi = ctk.CTkOptionMenu(f2, width=110, command=self.change_midi_port, fg_color="#444")
        self.opt_midi.pack()
        
        # Col 3: Generate
        f3 = self._make_fixed_frame(parent, 2, w_std, LAYOUT_CFG["h_header"])
        self.btn_gen = ctk.CTkButton(f3, text="🎲 Generate", width=110, height=40, fg_color=LAYOUT_CFG["color_accent_a"], 
                                     text_color="black", font=("Arial", 12, "bold"), command=self.generate_random_patch)
        self.btn_gen.place(relx=0.5, rely=0.5, anchor="center")
        
        # Col 4: Indicator (Wide)
        f4 = self._make_fixed_frame(parent, 3, LAYOUT_CFG["w_indicator"], LAYOUT_CFG["h_header"], bg="#111")
        self.lbl_big_val = ctk.CTkLabel(f4, text="INIT PATCH", font=("Arial", 24, "bold"), text_color="white")
        self.lbl_big_val.place(relx=0.5, rely=0.5, anchor="center")
        
        # Col 5: Master Vol
        f5 = self._make_fixed_frame(parent, 4, w_std, LAYOUT_CFG["h_header"])
        self.knob_master = self._add_knob(f5, "Master", 0.0, 1.0, 0.8, self.update_master, color="white")
        self.knob_master.place(relx=0.5, rely=0.5, anchor="center")
        
        # Col 6: Rec / Save / Open (Wide)
        f6 = self._make_fixed_frame(parent, 5, LAYOUT_CFG["w_indicator"], LAYOUT_CFG["h_header"])
        # Grid inside f6
        btn_w = 80
        ctk.CTkButton(f6, text="● Rec", width=btn_w, fg_color="#cc3333", command=self.toggle_rec).place(relx=0.2, rely=0.5, anchor="center")
        ctk.CTkButton(f6, text="Save", width=btn_w, fg_color="#444", command=self.save_preset).place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkButton(f6, text="Open", width=btn_w, fg_color="#444", command=self.load_preset).place(relx=0.8, rely=0.5, anchor="center")

    def _init_modules(self, parent):
        # 5 Modules + Env Split (Total 7 cols of logic, but pixel widths vary)
        w_std = LAYOUT_CFG["w_col_std"]
        h_mod = LAYOUT_CFG["h_modules"]
        
        # OSC A
        self.p_osc_a = self._make_fixed_frame(parent, 0, w_std, h_mod, bg="#1a1a1a") # Darker
        self._init_osc_a_ui(self.p_osc_a)
        
        # OSC B
        self.p_osc_b = self._make_fixed_frame(parent, 1, w_std, h_mod, bg="#111") # Darkest
        self._init_osc_b_ui(self.p_osc_b)
        
        # Filter
        self.p_filter = self._make_fixed_frame(parent, 2, w_std, h_mod, bg=LAYOUT_CFG["bg_panel"])
        self._init_filter_ui(self.p_filter)
        
        # Distort
        self.p_dist = self._make_fixed_frame(parent, 3, w_std, h_mod, bg=LAYOUT_CFG["bg_panel"])
        self._init_dist_ui(self.p_dist)
        
        # Delay
        self.p_delay = self._make_fixed_frame(parent, 4, w_std, h_mod, bg=LAYOUT_CFG["bg_panel"])
        self._init_delay_ui(self.p_delay)
        
        # Env Controls (Split Vertically)
        f_env_ctrl = self._make_fixed_frame(parent, 5, w_std, h_mod, bg="transparent")
        
        # Top: Amp Knobs
        f_amp_k = ctk.CTkFrame(f_env_ctrl, width=w_std, height=h_mod//2, fg_color="#2d332d", corner_radius=0)
        f_amp_k.pack()
        f_amp_k.pack_propagate(False)
        ctk.CTkLabel(f_amp_k, text="Amp Env", font=("Arial", 10, "bold"), text_color="#88ff88").pack(pady=5)
        
        # Bottom: Mod Knobs
        f_mod_k = ctk.CTkFrame(f_env_ctrl, width=w_std, height=h_mod//2, fg_color="#2d2d33", corner_radius=0)
        f_mod_k.pack()
        f_mod_k.pack_propagate(False)
        ctk.CTkLabel(f_mod_k, text="Mod Env", font=("Arial", 10, "bold"), text_color="#8888ff").pack(pady=5)
        self.knob_me_cut = self._add_knob(f_mod_k, "Cut", -1.0, 1.0, 0.0, self.update_mod_env_params, width=40, height=60)
        self.knob_me_cut.place(relx=0.3, rely=0.6, anchor="center")
        self.knob_me_pitch = self._add_knob(f_mod_k, "Ptc", -48, 48, 0, self.update_mod_env_params, width=40, height=60)
        self.knob_me_pitch.place(relx=0.7, rely=0.6, anchor="center")

        # Env Curves (Split Vertically)
        f_env_curve = self._make_fixed_frame(parent, 6, LAYOUT_CFG["w_curve"], h_mod, bg="transparent")
        
        # Top: Amp Curve
        f_amp_c = ctk.CTkFrame(f_env_curve, width=LAYOUT_CFG["w_curve"], height=h_mod//2, fg_color="#1a1a1a", corner_radius=0)
        f_amp_c.pack(); f_amp_c.pack_propagate(False)
        self.env_amp = EnvelopeEditor(f_amp_c, width=LAYOUT_CFG["w_curve"], height=h_mod//2, callback=self.update_adsr_amp,
                                      bg_color="#1a1a1a", line_color="#88ff88", fill_color="#113311")
        self.env_amp.pack()

        # Bottom: Mod Curve
        f_mod_c = ctk.CTkFrame(f_env_curve, width=LAYOUT_CFG["w_curve"], height=h_mod//2, fg_color="#1a1a1a", corner_radius=0)
        f_mod_c.pack(); f_mod_c.pack_propagate(False)
        self.env_mod = EnvelopeEditor(f_mod_c, width=LAYOUT_CFG["w_curve"], height=h_mod//2, callback=self.update_adsr_mod,
                                      bg_color="#1a1a1a", line_color="#8888ff", fill_color="#111133")
        self.env_mod.pack()

    def _init_automation_scope(self, parent):
        h = LAYOUT_CFG["h_auto"]
        
        # Col 1: Auto Control
        f_ctrl = self._make_fixed_frame(parent, 0, LAYOUT_CFG["w_col_std"], h, bg="#2b231a")
        ctk.CTkLabel(f_ctrl, text="Automation", font=("Arial", 11, "bold"), text_color="#ffa500").pack(pady=10)
        
        # Col 2: Auto Curve
        f_curve = self._make_fixed_frame(parent, 1, LAYOUT_CFG["w_auto_curve"], h, bg="#1a1a1a")
        self.auto_editor = AutomationEditor(f_curve, width=LAYOUT_CFG["w_auto_curve"], height=h, update_callback=self.update_automation_from_editor)
        self.auto_editor.pack()
        
        # Col 3: Scope
        f_scope = self._make_fixed_frame(parent, 2, LAYOUT_CFG["w_scope"], h, bg="#000")
        self.scope_canvas = tk.Canvas(f_scope, width=LAYOUT_CFG["w_scope"], height=h, bg="black", highlightthickness=0)
        self.scope_canvas.pack()

    def _make_fixed_frame(self, parent, col_idx, w, h, bg=LAYOUT_CFG["bg_panel"]):
        f = ctk.CTkFrame(parent, width=w, height=h, fg_color=bg, corner_radius=0)
        f.grid(row=0, column=col_idx, sticky="nw", padx=(0, 1)) # 1px gap
        f.grid_propagate(False)
        return f

    # --- UI Helpers (Adapted for fixed layout) ---
    def _init_osc_a_ui(self, parent):
        ctk.CTkLabel(parent, text="OSC A", text_color=LAYOUT_CFG["color_accent_a"], font=("Arial", 11, "bold")).pack(pady=5)
        self.opt_wt_a = ctk.CTkOptionMenu(parent, values=["Classic", "Monster", "Basic Shapes"], command=self.update_osc_a, width=100, height=20)
        self.opt_wt_a.set("Classic"); self.opt_wt_a.pack(pady=5)
        
        g = ctk.CTkFrame(parent, fg_color="transparent")
        g.pack(pady=5)
        self.knob_pos_a = self._add_knob_grid(g, "Pos", 0, 1, 0, self.update_osc_a, 0, 0, LAYOUT_CFG["color_accent_a"], "osc_a_pos")
        self.knob_vol_a = self._add_knob_grid(g, "Vol", 0, 1, 0.8, self.update_osc_a, 0, 1, LAYOUT_CFG["color_accent_a"], "osc_a_vol")
        self.knob_semi_a = self._add_knob_grid(g, "Semi", -12, 12, 0, self.update_osc_a, 1, 0, LAYOUT_CFG["color_accent_a"], "osc_a_semi")
        self.knob_uni_a = self._add_knob_grid(g, "Uni", 0, 7, 0, self.update_osc_a, 1, 1, LAYOUT_CFG["color_accent_a"], "osc_a_uni")
        
        fr = ctk.CTkFrame(parent, fg_color="transparent")
        fr.pack(pady=5)
        self.sw_rand_a = ctk.CTkSwitch(fr, text="Rnd Phs", font=("Arial", 9), width=80, command=self.update_osc_a, progress_color=LAYOUT_CFG["color_accent_a"])
        self.sw_rand_a.pack()
        self.locks[self.sw_rand_a] = ctk.BooleanVar(value=False)

    def _init_osc_b_ui(self, parent):
        ctk.CTkLabel(parent, text="OSC B", text_color=LAYOUT_CFG["color_accent_b"], font=("Arial", 11, "bold")).pack(pady=5)
        self.opt_wt_b = ctk.CTkOptionMenu(parent, values=["Classic", "Monster", "Basic Shapes"], command=self.update_osc_b, width=100, height=20)
        self.opt_wt_b.set("Monster"); self.opt_wt_b.pack(pady=5)
        
        g = ctk.CTkFrame(parent, fg_color="transparent")
        g.pack(pady=5)
        self.knob_pos_b = self._add_knob_grid(g, "Pos", 0, 1, 0, self.update_osc_b, 0, 0, LAYOUT_CFG["color_accent_b"], "osc_b_pos")
        self.knob_vol_b = self._add_knob_grid(g, "Vol", 0, 1, 0, self.update_osc_b, 0, 1, LAYOUT_CFG["color_accent_b"], "osc_b_vol")
        self.knob_semi_b = self._add_knob_grid(g, "Semi", -12, 12, 0, self.update_osc_b, 1, 0, LAYOUT_CFG["color_accent_b"], "osc_b_semi")
        self.knob_uni_b = self._add_knob_grid(g, "Uni", 0, 7, 0, self.update_osc_b, 1, 1, LAYOUT_CFG["color_accent_b"], "osc_b_uni")
        
        fr = ctk.CTkFrame(parent, fg_color="transparent")
        fr.pack(pady=5)
        self.sw_rand_b = ctk.CTkSwitch(fr, text="Rnd Phs", font=("Arial", 9), width=80, command=self.update_osc_b, progress_color=LAYOUT_CFG["color_accent_b"])
        self.sw_rand_b.pack()
        self.locks[self.sw_rand_b] = ctk.BooleanVar(value=False)

    def _init_filter_ui(self, parent):
        ctk.CTkLabel(parent, text="Filter", font=("Arial", 11, "bold")).pack(pady=5)
        self.knob_cutoff = self._add_knob(parent, "Cutoff", 20, 20000, 20000, self.update_filter, param_id="filter_cutoff")
        self.knob_cutoff.pack(pady=10)
        self.sw_filter = ctk.CTkSwitch(parent, text="On", width=50, command=self.update_filter)
        self.sw_filter.pack()

    def _init_dist_ui(self, parent):
        ctk.CTkLabel(parent, text="Distort", font=("Arial", 11, "bold")).pack(pady=5)
        self.knob_drive = self._add_knob(parent, "Drive", 0, 1, 0, self.update_dist, param_id="dist_drive")
        self.knob_drive.pack(pady=10)
        self.sw_dist = ctk.CTkSwitch(parent, text="On", width=50, command=self.update_dist)
        self.sw_dist.pack()

    def _init_delay_ui(self, parent):
        ctk.CTkLabel(parent, text="Delay", font=("Arial", 11, "bold")).pack(pady=5)
        self.knob_d_time = self._add_knob(parent, "Time", 0.01, 1.0, 0.25, self.update_delay, param_id="delay_time")
        self.knob_d_time.pack(pady=5)
        self.knob_d_mix = self._add_knob(parent, "Mix", 0, 1, 0.3, self.update_delay, param_id="delay_mix")
        self.knob_d_mix.pack(pady=5)
        self.sw_delay = ctk.CTkSwitch(parent, text="On", width=50, command=self.update_delay)
        self.sw_delay.pack()

    # Helpers
    def _add_knob(self, parent, text, vmin, vmax, vdef, command, width=None, height=None, color=None, param_id=None):
        w = width if width else LAYOUT_CFG["knob_w"]
        h = height if height else LAYOUT_CFG["knob_h"]
        c = color if color else LAYOUT_CFG["color_accent_a"]
        
        def wrapped(val):
            command(val)
            self.lbl_big_val.configure(text=f"{text}: {val:.2f}")

        k = RotaryKnob(parent, text=text, from_=vmin, to=vmax, start_val=vdef, command=wrapped,
                       width=w, height=h, progress_color=c, track_color="#111", show_value=False,
                       param_id=param_id, focus_callback=self.on_knob_focus)
        
        # Add Lock logic if needed (simplified for layout step)
        if param_id:
            self.locks[k] = ctk.BooleanVar(value=False)
        return k

    def _add_knob_grid(self, parent, text, vmin, vmax, vdef, command, r, c, color, pid):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=r, column=c, padx=2, pady=2)
        k = self._add_knob(f, text, vmin, vmax, vdef, command, color=color, param_id=pid)
        k.pack()
        return k

    # --- Engine Linking ---
    def toggle_rec(self):
        if not self.engine.recorder.active:
            self.engine.start_recording()
            self.lbl_big_val.configure(text="RECORDING...", text_color="red")
        else:
            fname = self.engine.stop_recording()
            self.lbl_big_val.configure(text=f"Saved: {fname}", text_color="white")

    def on_knob_focus(self, param_id):
        name = param_id
        self.lbl_big_val.configure(text=f"EDIT: {name}")
        if param_id in self.engine.automations:
            lane = self.engine.automations[param_id]
            points = lane.points
            dur = lane.duration
        else:
            points = [(0.0, 0.0), (1.0, 0.0)]
            dur = 4.0
        self.auto_editor.set_target(param_id, name, points, dur)

    def update_automation_from_editor(self, param_id, points, duration):
        if param_id not in self.engine.automations:
             self.engine.automations[param_id] = AutomationLane(duration)
        lane = self.engine.automations[param_id]
        lane.points = points
        lane.duration = duration

    # (Audio/Engine Callbacks same as before)
    def _audio_callback(self, in_data, frame_count, time_info, status):
        data = self.engine.generate_block()
        stereo = data.reshape(-1, 2)
        if not self.preview_mode:
            self.current_waveform = stereo[:, 0].copy()
        self.block_buffer = stereo[:, 0].copy()
        return (data.astype(np.float32).tobytes(), pyaudio.paContinue)

    def _start_audio(self):
        self.stream = self.pya.open(format=pyaudio.paFloat32, channels=CHANNELS, rate=SR, output=True, frames_per_buffer=BLOCK_SIZE, stream_callback=self._audio_callback)
        self.stream.start_stream()
        
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
            self.scope_canvas.create_polygon(points, fill="#004044", outline="")
            self.scope_canvas.create_line(points[2:-2], fill="#00e5ff", width=2)
            
        if hasattr(self, "level_meter"):
             self.level_meter.update_meter(self.block_buffer)
        self.after(50, self.update_scope)

    # Param Update Wrappers
    def update_master(self, val): pass 
    def update_osc_a(self, _=None): 
        self.engine.set_osc_a_params(self.opt_wt_a.get(), self.knob_pos_a.get(), self.knob_uni_a.get(), self.knob_vol_a.get(), 
                                     self.knob_semi_a.get(), 0, 0, 0.0, 0.0, self.sw_rand_a.get())
        self.update_preview()
    def update_osc_b(self, _=None): 
        self.engine.set_osc_b_params(self.opt_wt_b.get(), self.knob_pos_b.get(), self.knob_uni_b.get(), self.knob_vol_b.get(), 
                                     self.knob_semi_b.get(), 0, 0, 0.0, 0.0, self.sw_rand_b.get())
        self.update_preview()
    def update_filter(self, _=None): self.engine.set_filter(self.sw_filter.get(), self.knob_cutoff.get())
    def update_dist(self, _=None): self.engine.set_dist(self.sw_dist.get(), self.knob_drive.get())
    def update_delay(self, _=None): self.engine.set_delay(self.sw_delay.get(), self.knob_d_time.get(), 0.4, self.knob_d_mix.get())
    def update_adsr_amp(self, a, d, s, r): self.engine.set_adsr(a, d, s, r)
    def update_adsr_mod(self, a, d, s, r): self.update_mod_env_params()
    def update_mod_env_params(self, _=None): 
        a,d,s,r = self.env_mod.get_params()
        self.engine.set_mod_adsr(a,d,s,r, self.knob_me_cut.get(), self.knob_me_pitch.get())

    def update_preview(self):
        # (Simplified preview logic)
        self.preview_mode = True
        self.after(200, lambda: setattr(self, 'preview_mode', False))

    def generate_random_patch(self):
        # (Simplified random logic to respect locks)
        if not self.locks[self.sw_rand_a].get(): self.knob_pos_a.set(random.random())
        self.update_osc_a(); self.update_osc_b()
        
    def save_preset(self):
        fn = filedialog.asksaveasfilename(initialdir=self.preset_dir, defaultextension=".json")
        if fn: 
            with open(fn, 'w') as f: json.dump(self.engine.get_patch_state(), f)
    def load_preset(self):
        fn = filedialog.askopenfilename(initialdir=self.preset_dir)
        if fn:
            with open(fn, 'r') as f: self.engine.set_patch_state(json.load(f))

    def change_midi_port(self, port):
        if port == "No Device": return
        if self.midi_in: self.midi_in.close()
        try: self.midi_in = mido.open_input(port, callback=self.midi_callback)
        except: pass
    def midi_callback(self, msg):
        if msg.type=='note_on': self.engine.note_on(msg.note)
        elif msg.type=='note_off': self.engine.note_off(msg.note)
    def kb_note_on(self, n): self.engine.note_on(n)
    def kb_note_off(self, n): self.engine.note_off(n)
    def on_close(self):
        self.is_running = False
        if self.stream: self.stream.stop_stream(); self.stream.close()
        self.pya.terminate()
        self.destroy()

if __name__ == "__main__":
    app = PySerumApp()
    app.mainloop()
