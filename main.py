import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import pygame
import os
import random
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from tkinterdnd2 import DND_FILES, TkinterDnD
from audio_engine import AudioEngine
from scipy.interpolate import CubicSpline
import time
import json

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title("Animal Voice Morpher Ultimate - Explorer Edition")
        self.geometry("1800x950")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        
        self.engine = AudioEngine()
        pygame.mixer.init()
        
        self.pitch_curve_y = np.zeros(100)
        self.is_drawing_pitch = False
        self.autoplay_morph = False
        self.is_morphing_busy = False
        self.is_batch_running = False
        self.morph_x = 0.5
        self.morph_y = 0.5
        self.is_animating = False
        
        # Explorer State
        self.current_dir = os.getcwd()
        self.pins = []
        self.load_pins()
        
        # Layout: 4 Columns
        # Col 0: Explorer (width around 250)
        # Col 1: Source (width around 250)
        # Col 2: Editor (Flexible)
        # Col 3: Batch (width around 300)
        self.grid_columnconfigure(0, weight=0, minsize=280) 
        self.grid_columnconfigure(1, weight=0, minsize=280) 
        self.grid_columnconfigure(2, weight=1) 
        self.grid_columnconfigure(3, weight=0, minsize=320) 
        self.grid_rowconfigure(0, weight=1)
        
        # Frames
        self.col_explorer = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.col_explorer.grid(row=0, column=0, sticky="nsew", padx=1)
        
        self.col_source = ctk.CTkFrame(self, corner_radius=0, fg_color="#222222")
        self.col_source.grid(row=0, column=1, sticky="nsew", padx=1)
        
        self.col_center = ctk.CTkFrame(self, corner_radius=0)
        self.col_center.grid(row=0, column=2, sticky="nsew", padx=1)
        
        self.col_batch = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.col_batch.grid(row=0, column=3, sticky="nsew", padx=1)
        
        self.lbl_status = ctk.CTkLabel(self, text="Ready", text_color="gray", fg_color="#111")
        self.lbl_status.grid(row=1, column=0, columnspan=4, sticky="ew")

        # Shortcuts
        self.key_map = {}
        self.load_keybindings()
        
        self.bind(self.key_map.get("MORPH", "1"), lambda e: self.trigger_morph(False))
        self.bind(self.key_map.get("MORPH_AND_AUTO", "!"), lambda e: self.trigger_morph(True))
        self.bind(self.key_map.get("APPLY_FX", "2"), lambda e: self.apply_pitch_thread())
        self.bind(self.key_map.get("PLAY_STOP", "<space>"), self.toggle_playback)
        
        if self.key_map.get("SAVE"): self.bind(self.key_map["SAVE"], lambda e: self.save_file())
        if self.key_map.get("RESET_PITCH"): self.bind(self.key_map["RESET_PITCH"], lambda e: self.reset_pitch_curve_action())
        if self.key_map.get("RUN_BATCH"): self.bind(self.key_map["RUN_BATCH"], lambda e: self.run_batch())
        if self.key_map.get("TOGGLE_AUTOPLAY"): self.bind(self.key_map["TOGGLE_AUTOPLAY"], lambda e: self.toggle_autoplay_var())

        self._init_explorer()
        self._init_source()
        self._init_editor()
        self._init_batch()
        
        self.refresh_file_list()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.after(200, self.load_last_state)

    def load_keybindings(self):
        default_keys = {
            "MORPH": "1",
            "MORPH_AND_AUTO": "!",
            "APPLY_FX": "2",
            "PLAY_STOP": "<space>",
            "SAVE": "",
            "RESET_PITCH": "",
            "RUN_BATCH": "",
            "TOGGLE_AUTOPLAY": ""
        }
        try:
            if os.path.exists("keybindings.json"):
                with open("keybindings.json", "r") as f:
                    self.key_map = json.load(f)
            else:
                self.key_map = default_keys
                with open("keybindings.json", "w") as f:
                    json.dump(default_keys, f, indent=4)
        except:
            self.key_map = default_keys
            
        # Ensure Settings directory exists
        if not os.path.exists("Settings"):
            try: os.makedirs("Settings")
            except: pass
            
    def toggle_autoplay_var(self):
        self.var_autoplay.set(not self.var_autoplay.get())
            
    def open_help(self):
        try:
            if os.path.exists("MANUAL.md"):
                os.startfile("MANUAL.md")
            else:
                messagebox.showinfo("Help", "Manual file not found.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open help: {e}")

    # ================= COL 0: EXPLORER =================
    def _init_explorer(self):
        f_head = ctk.CTkFrame(self.col_explorer, fg_color="transparent")
        f_head.pack(fill="x", pady=(10,5), padx=5)
        
        ctk.CTkLabel(f_head, text="EXPLORER", font=("Roboto", 14, "bold"), text_color="#aaa").pack(side="left", expand=True)
        ctk.CTkButton(f_head, text="?", width=24, height=24, command=self.open_help, fg_color="#444", hover_color="#666").pack(side="right")
        
        # Drive Selector
        self.drives = self.get_drives()
        self.cmb_drive = ctk.CTkOptionMenu(self.col_explorer, values=self.drives, command=self.on_drive_change, width=200)
        self.cmb_drive.set(os.path.splitdrive(os.getcwd())[0])
        self.cmb_drive.pack(pady=5)
        
        # Pins
        self.frame_pins = ctk.CTkFrame(self.col_explorer, fg_color="transparent")
        self.frame_pins.pack(fill="x", padx=5)
        self.btn_pin_add = ctk.CTkButton(self.frame_pins, text="+ Pin Current", command=self.add_pin, height=24, fg_color="#444", hover_color="#555")
        self.btn_pin_add.pack(fill="x", pady=2)
        
        self.frame_pin_list = ctk.CTkScrollableFrame(self.col_explorer, height=120, fg_color="transparent")
        self.frame_pin_list.pack(fill="x", padx=5, pady=5)
        self.update_pin_list_ui()
        
        # Path Bar
        frame_nav = ctk.CTkFrame(self.col_explorer, fg_color="transparent")
        frame_nav.pack(fill="x", padx=5, pady=(5,0))
        ctk.CTkButton(frame_nav, text="⬆", width=30, command=self.go_up, fg_color="#444").pack(side="left")
        self.lbl_path = ctk.CTkLabel(frame_nav, text=".", text_color="gray", anchor="w")
        self.lbl_path.pack(side="left", padx=5, fill="x")

        # Preview Controls
        frame_prev = ctk.CTkFrame(self.col_explorer, fg_color="transparent")
        frame_prev.pack(fill="x", padx=5, pady=5)
        
        self.var_autoplay = tk.BooleanVar(value=True)
        self.chk_autoplay = ctk.CTkCheckBox(frame_prev, text="Auto", variable=self.var_autoplay, width=50, font=("Roboto",11))
        self.chk_autoplay.pack(side="left", padx=(0,5))
        
        ctk.CTkButton(frame_prev, text="■", width=30, command=self.stop_preview, fg_color="#C62828", hover_color="#B71C1C").pack(side="left", padx=2)
        
        self.sl_exp_vol = ctk.CTkSlider(frame_prev, from_=0, to=1, width=80, command=self.set_vol_preview)
        self.sl_exp_vol.set(0.5); self.sl_exp_vol.pack(side="left", padx=5)
        
        # File List
        self.listbox = tk.Listbox(self.col_explorer, bg="#202020", fg="white", selectbackground="#4da6ff", borderwidth=0, highlightthickness=0, font=("Consolas", 10))
        self.listbox.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.listbox.bind("<Double-Button-1>", self.on_list_double_click)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)
        self.listbox.bind("<Button-3>", self.on_list_right_click)
        
        # Drag Source
        self.listbox.drag_source_register(1, DND_FILES)
        self.listbox.dnd_bind('<<DragInitCmd>>', self.on_drag_init)
        
    def get_drives(self):
        import string
        drives = []
        for d in string.ascii_uppercase:
            if os.path.exists(f"{d}:"):
                drives.append(f"{d}:")
        return drives
        
    def on_drive_change(self, choice):
        if os.path.exists(choice):
             self.current_dir = choice + "\\"
             self.refresh_file_list()
        
    def get_file_list(self):
        try:
            items = os.listdir(self.current_dir)
            dirs = sorted([d for d in items if os.path.isdir(os.path.join(self.current_dir, d))])
            files = sorted([f for f in items if os.path.isfile(os.path.join(self.current_dir, f)) and f.lower().endswith(('.wav','.mp3','.flac','.ogg','.aif','.aiff'))])
            return dirs, files
        except: return [], []

    def refresh_file_list(self):
        self.listbox.delete(0, tk.END)
        self.lbl_path.configure(text=os.path.basename(self.current_dir) or self.current_dir)
        
        dirs, files = self.get_file_list()
        for d in dirs: self.listbox.insert(tk.END, f"📁 {d}")
        for f in files: self.listbox.insert(tk.END, f"🎵 {f}")

    def on_list_double_click(self, e):
        sel = self.listbox.curselection()
        if not sel: return
        txt = self.listbox.get(sel[0])
        if txt.startswith("📁 "):
             name = txt[2:]
             self.current_dir = os.path.join(self.current_dir, name)
             self.refresh_file_list()

    def on_list_right_click(self, e):
        # Select item under cursor first
        idx = self.listbox.nearest(e.y)
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        self.listbox.activate(idx)
        
        # Check if file
        txt = self.listbox.get(idx)
        if not txt.startswith("🎵 "): return
        
        # Show Menu
        path = os.path.join(self.current_dir, txt[2:])
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Load into Source A (Master)", command=lambda: self.load_a(path))
        m.add_command(label="Load into Source B", command=lambda: self.load_b(path))
        m.add_command(label="Load into Source C", command=lambda: self.load_c(path))
        m.add_command(label="Load into Source D", command=lambda: self.load_d(path))
        m.tk_popup(e.x_root, e.y_root)

    def on_list_select(self, e):
        if not self.var_autoplay.get(): return
        sel = self.listbox.curselection()
        if not sel: return
        txt = self.listbox.get(sel[0])
        if txt.startswith("🎵 "):
            path = os.path.join(self.current_dir, txt[2:])
            self.play_explorer_preview(path)

    def stop_preview(self):
        if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()

    def set_vol_preview(self, val):
        pygame.mixer.music.set_volume(float(val))

    def go_up(self):
        self.current_dir = os.path.dirname(self.current_dir)
        self.refresh_file_list()
        
    def add_pin(self):
        if self.current_dir not in self.pins:
            self.pins.append(self.current_dir)
            self.save_pins()
            self.update_pin_list_ui()
            
    def load_pins(self):
        try:
            if os.path.exists("favs.json"):
                with open("favs.json","r") as f: self.pins = json.load(f)
        except: pass
        
    def save_pins(self):
        try:
            with open("favs.json","w") as f: json.dump(self.pins, f)
        except: pass
        
    def update_pin_list_ui(self):
        for w in self.frame_pin_list.winfo_children(): w.destroy()
        for i, p in enumerate(self.pins):
            f = ctk.CTkFrame(self.frame_pin_list, fg_color="transparent")
            f.pack(fill="x", pady=1)
            
            btn_go = ctk.CTkButton(f, text=os.path.basename(p) or p, command=lambda x=p: self.go_to_pin(x), 
                                height=20, fg_color="transparent", border_width=1, border_color="#444", text_color="#ccc", anchor="w")
            btn_go.pack(side="left", fill="x", expand=True, padx=(0,2))
            
            btn_del = ctk.CTkButton(f, text="x", command=lambda x=i: self.delete_pin(x), width=20, height=20, fg_color="#552222", hover_color="#883333")
            btn_del.pack(side="right")
            
    def delete_pin(self, index):
        if 0 <= index < len(self.pins):
            self.pins.pop(index)
            self.save_pins()
            self.update_pin_list_ui()

    def go_to_pin(self, path):
        if os.path.exists(path):
            self.current_dir = path
            self.refresh_file_list()

    def on_drag_init(self, event):
        sel = self.listbox.curselection()
        if not sel: return
        txt = self.listbox.get(sel[0])
        if txt.startswith("🎵 "):
             path = os.path.join(self.current_dir, txt[2:])
             return ((map, DND_FILES, path),) # Standard TkinterDnD return
        return None
        
    # on_list_select removed

    def play_explorer_preview(self, path):
        try:
            if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
        except: pass

    # ================= COL 1: SOURCE & MOTION =================
    def _init_source(self):
        ctk.CTkLabel(self.col_source, text="SOURCES (DnD)", font=("Roboto", 14, "bold"), text_color="#4da6ff").pack(pady=10)
        
        def make(t, c):
            b = ctk.CTkButton(self.col_source, text=t, command=c, height=40, fg_color="#333", border_color="#4da6ff", border_width=1)
            b.pack(pady=5, padx=10, fill="x")
            b.drop_target_register(DND_FILES); b.dnd_bind('<<Drop>>', lambda e: self.on_drop(e, c))
            return b
            
        self.btn_a = make("Load A (Master)", self.load_a)
        self.btn_b = make("Load B", self.load_b)
        self.btn_c = make("Load C", self.load_c)
        self.btn_d = make("Load D", self.load_d)
        
        ctk.CTkLabel(self.col_source, text="MORPH PAD", font=("Roboto", 14, "bold"), text_color="#4da6ff").pack(pady=(30,5))
        
        self.canvas_xy = tk.Canvas(self.col_source, width=240, height=240, bg="#1a1a1a", highlightthickness=0)
        self.canvas_xy.pack()
        self.canvas_xy.create_text(10,10,text="A",fill="#888",anchor="nw")
        self.canvas_xy.create_text(230,10,text="B",fill="#888",anchor="ne")
        self.canvas_xy.create_text(10,230,text="C",fill="#888",anchor="sw")
        self.canvas_xy.create_text(230,230,text="D",fill="#888",anchor="se")
        self.xy_handle = self.canvas_xy.create_oval(0,0,16,16, fill="#4da6ff", outline="white")
        self.update_xy_visuals()
        self.canvas_xy.bind("<Button-1>", self.on_xy_click)
        self.canvas_xy.bind("<B1-Motion>", self.on_xy_drag)
        self.canvas_xy.bind("<ButtonRelease-1>", self.on_xy_release)
        
        ctk.CTkLabel(self.col_source, text="MOTION", font=("Roboto", 12)).pack(pady=(15,0))
        self.cmb_shape = ctk.CTkOptionMenu(self.col_source, values=["Static", "Circle", "Eight", "Scan", "Random"])
        self.cmb_shape.set("Static"); self.cmb_shape.pack(pady=5)
        self.slider_mspeed = ctk.CTkSlider(self.col_source, from_=0.1, to=5.0); self.slider_mspeed.set(1.0); self.slider_mspeed.pack(pady=5)
        ctk.CTkLabel(self.col_source, text="Speed (Hz)", text_color="gray", font=("Roboto",10)).pack()

    # ================= COL 2: EDITOR =================
    def _init_editor(self):
        ctk.CTkLabel(self.col_center, text="EDITOR", font=("Roboto", 16, "bold"), text_color="#eee").pack(pady=10)
        
        # Plot
        fp = ctk.CTkFrame(self.col_center, fg_color="#1a1a1a")
        fp.pack(fill="both", expand=True, padx=20, pady=10)
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(6,3))
        self.fig.patch.set_facecolor('#1a1a1a')
        self.ax.set_facecolor('#222')
        self.line, = self.ax.plot([],[], color='#4da6ff', linewidth=2)
        self.point_scatter, = self.ax.plot([], [], 'o', color='white', markeredgecolor='#4da6ff')
        self.ax.set_ylim(-6,6); self.ax.set_xlim(0,100); self.ax.grid(alpha=0.2)
        self.canvas = FigureCanvasTkAgg(self.fig, master=fp)
        self.canvas.draw(); self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.canvas.mpl_connect('button_press_event', self.on_chart_click)
        self.canvas.mpl_connect('motion_notify_event', self.on_chart_drag)
        self.canvas.mpl_connect('button_release_event', self.on_chart_release)
        
        self.pitch_points = [] # List of [x, y]
        self.drag_point_idx = None
        self.reset_pitch_curve_action()
        
        ctk.CTkButton(self.col_center, text="Reset Pitch", command=self.reset_pitch_curve_action, width=120, height=24, fg_color="#333").pack(pady=5)
        
        # FX
        f_fx = ctk.CTkFrame(self.col_center, fg_color="transparent")
        f_fx.pack(fill="x", padx=20, pady=20)
        for i in range(4): f_fx.grid_columnconfigure(i, weight=1)
        
        def sl(p,r,c,t,mn,mx,df):
            f=ctk.CTkFrame(p, fg_color="transparent")
            f.grid(row=r,column=c,padx=10,pady=10,sticky="ew")
            ctk.CTkLabel(f,text=t,font=("Roboto",11),text_color="#ccc").pack()
            s=ctk.CTkSlider(f,from_=mn,to=mx,width=140); s.set(df); s.pack()
            return s
            
        self.sl_breath = sl(f_fx,0,0,"Breath (Noise)",0,1,0)
        self.sl_formant = sl(f_fx,0,1,"Formant (Size)",0.5,2,1)
        self.sl_growl = sl(f_fx,0,2,"Growl (AM)",0,1,0)
        self.sl_tone = sl(f_fx,0,3,"Tone (Filt)",-1,1,0)
        
        self.sl_speed = sl(f_fx,1,0,"Speed (Time)",0.5,2,1)
        self.sl_dist = sl(f_fx,1,1,"Distortion",0,1,0)
        self.sl_vol = sl(f_fx,1,2,"Volume",0,1.5,1)
        
        # Action Buttons
        f_act = ctk.CTkFrame(self.col_center, fg_color="transparent")
        f_act.pack(side="bottom", fill="x", padx=20, pady=20)
        
        self.btn_morph = ctk.CTkButton(f_act, text="1. MORPH", command=lambda: self.trigger_morph(False), fg_color="#E53935", height=45, font=("Roboto",14,"bold"))
        self.btn_morph.pack(side="left", fill="x", expand=True, padx=5)
        
        self.btn_apply = ctk.CTkButton(f_act, text="2. APPLY FX", command=self.apply_pitch_thread, state="disabled", fg_color="#1976D2", height=45, font=("Roboto",14))
        self.btn_apply.pack(side="left", fill="x", expand=True, padx=5)
        
        self.btn_preview = ctk.CTkButton(f_act, text="▶ PLAY", command=self.play_preview, state="disabled", fg_color="#43A047", height=45, font=("Roboto",14))
        self.btn_preview.pack(side="left", fill="x", expand=True, padx=5)
        
        ctk.CTkButton(f_act, text="SAVE", command=self.save_file, height=45, fg_color="#555").pack(side="left", fill="x", expand=True, padx=5)

        # Settings
        f_sets = ctk.CTkFrame(self.col_center, fg_color="transparent")
        f_sets.pack(side="bottom", fill="x", padx=20, pady=(0, 5))
        ctk.CTkButton(f_sets, text="💾 Save Settings", command=self.save_settings, width=100, fg_color="#333", hover_color="#444").pack(side="left", padx=5, expand=True, fill="x")
        ctk.CTkButton(f_sets, text="📂 Load Settings", command=self.load_settings, width=100, fg_color="#333", hover_color="#444").pack(side="left", padx=5, expand=True, fill="x")

    # ================= COL 3: BATCH =================
    def _init_batch(self):
        ctk.CTkLabel(self.col_batch, text="BATCH FACTORY 🏭", font=("Roboto", 16, "bold"), text_color="#FFA726").pack(pady=10)
        
        # Config
        fc = ctk.CTkFrame(self.col_batch, fg_color="#222")
        fc.pack(fill="x", padx=10, pady=5)
        
        def ent(l,d,r):
            ctk.CTkLabel(fc,text=l).grid(row=r,column=0,sticky="e",padx=5)
            e=ctk.CTkEntry(fc,width=100); e.insert(0,d); e.grid(row=r,column=1,sticky="w",pady=2)
            return e
        self.b_cnt = ent("Count:", "30", 0)
        self.b_pre = ent("Prefix:", "Monster", 1)
        self.outdir = os.getcwd()
        
        f_od = ctk.CTkFrame(self.col_batch, fg_color="transparent")
        f_od.pack(fill="x", padx=10)
        ctk.CTkButton(f_od, text="Output Directory", command=self.sel_outdir, height=24, width=120, fg_color="#444").pack(side="left", padx=2)
        ctk.CTkButton(f_od, text="📂 Open", command=self.open_outdir, height=24, width=60, fg_color="#444").pack(side="left", padx=2)
        
        # Random
        ctk.CTkLabel(self.col_batch, text="RANDOM RANGES", font=("Roboto", 12)).pack(pady=(20,5))
        
        self.r_motion = self._add_rnd("Motion X/Y/Shp")
        self.r_mspeed = self._add_rnd("Motion Speed")
        self.r_breath = self._add_rnd("Breath Var")
        self.r_formant = self._add_rnd("Formant Var")
        self.r_growl = self._add_rnd("Growl Var")
        self.r_tone = self._add_rnd("Tone Var")
        self.r_pitch = self._add_rnd("Pitch Curve")
        self.r_speed = self._add_rnd("TimeSpeed Var")
        self.r_dist = self._add_rnd("Distortion Var")
        self.r_vol = self._add_rnd("Volume Var")
        
        self.prog_batch = ctk.CTkProgressBar(self.col_batch, progress_color="#FFA726"); self.prog_batch.set(0); self.prog_batch.pack(fill="x", padx=10, pady=(30,5))
        self.btn_batch = ctk.CTkButton(self.col_batch, text="🚀 RUN BATCH", command=self.run_batch, height=50, font=("Roboto", 14, "bold"), fg_color="#FFA726", text_color="black", hover_color="#F57C00")
        self.btn_batch.pack(fill="x", padx=10, pady=10)

    def _add_rnd(self, t):
        f = ctk.CTkFrame(self.col_batch, fg_color="transparent", height=28)
        f.pack(fill="x", padx=10)
        v = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(f, text=t, variable=v, width=20, font=("Roboto", 11), text_color="#ccc").pack(side="left")
        s = ctk.CTkSlider(f, from_=0, to=1, width=80); s.set(0.5); s.pack(side="right")
        return (v, s)

    # --- Handlers ---
    def on_drop(self, event, func):
        path = event.data
        if path.startswith('{') and path.endswith('}'): path = path[1:-1]
        try:
             func(path)
             self.lbl_status.configure(text=f"Loaded {os.path.basename(path)}")
        except Exception as e: messagebox.showerror("Err", str(e))
    
    def load_generic(self, f, btn):
        p = filedialog.askopenfilename()
        if p: f(p); btn.configure(text=os.path.basename(p))
    def load_a(self, p=None): 
        if p: self.engine.load_source_a(p); self.btn_a.configure(text=os.path.basename(p))
        else: self.load_generic(self.engine.load_source_a, self.btn_a)
    def load_b(self, p=None): 
        if p: self.engine.load_source_b(p); self.btn_b.configure(text=os.path.basename(p))
        else: self.load_generic(self.engine.load_source_b, self.btn_b)
    def load_c(self, p=None): 
        if p: self.engine.load_source_c(p); self.btn_c.configure(text=os.path.basename(p))
        else: self.load_generic(self.engine.load_source_c, self.btn_c)
    def load_d(self, p=None): 
        if p: self.engine.load_source_d(p); self.btn_d.configure(text=os.path.basename(p))
        else: self.load_generic(self.engine.load_source_d, self.btn_d)

    # --- XY ---
    def update_xy_visuals(self):
        w = 240
        self.canvas_xy.coords(self.xy_handle, self.morph_x*w-8, self.morph_y*w-8, self.morph_x*w+8, self.morph_y*w+8)
    def set_xy(self, e):
        self.morph_x = max(0.0, min(1.0, e.x/240))
        self.morph_y = max(0.0, min(1.0, e.y/240))
        self.update_xy_visuals(); self.cmb_shape.set("Static")
    def on_xy_click(self, e): self.set_xy(e)
    def on_xy_drag(self, e): self.set_xy(e); self.trigger_morph(False, True)
    def on_xy_release(self, e): self.trigger_morph(False, False)

    # --- Morph ---
    def trigger_morph(self, autoplay=False, from_drag=False):
        if self.engine.y_a is None: return
        if from_drag and self.is_morphing_busy: return
        self.is_morphing_busy = True; self.autoplay_morph = autoplay
        self.btn_morph.configure(text="...", state="disabled")
        threading.Thread(target=self.run_morph, args=(self.cmb_shape.get(), self.slider_mspeed.get(), self.sl_formant.get(), self.sl_breath.get()), daemon=True).start()
        
    def run_morph(self, shp, spd, fmt, brt):
        try:
            self.engine.morph(self.morph_x, self.morph_y, shape=shp, speed=spd, formant_shift=fmt, breath=brt)
            self.after(0, self.morph_complete)
        except Exception as e:
             self.after(0, lambda: messagebox.showerror("Err", str(e)))
             self.after(0, self.morph_complete)

    def morph_complete(self):
        self.is_morphing_busy = False
        self.btn_apply.configure(state="normal"); self.btn_preview.configure(state="normal"); self.btn_morph.configure(text="1. MORPH", state="normal")
        self.lbl_status.configure(text="Morph Done.")
        if self.engine.generated_audio is not None:
             dur = len(self.engine.generated_audio)/self.engine.sr
             self.ax.set_xlabel(f"Time ({dur:.2f}s)"); self.canvas.draw()
        if self.autoplay_morph: self.apply_pitch_thread()

    # --- Apply ---
    def apply_pitch_thread(self):
        if self.engine.generated_audio is None: return
        self.btn_apply.configure(state="disabled")
        threading.Thread(target=self.run_apply, daemon=True).start()
    def run_apply(self):
        try:
            self.engine.process_pipeline(self.pitch_curve_y, self.sl_speed.get(), self.sl_growl.get(), self.sl_tone.get(), self.sl_dist.get(), self.sl_vol.get())
            self.after(0, self.apply_done)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Err", str(e))); self.after(0, self.apply_done)
    def apply_done(self):
        self.btn_apply.configure(state="normal"); self.lbl_status.configure(text="Applied FX.")
        if self.autoplay_morph: self.play_preview(); self.autoplay_morph = False

    # --- Play ---
    def play_preview(self):
         if self.engine.generated_audio is None: return
         if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
         pygame.mixer.music.unload()
         t = self.engine.processed_audio if self.engine.processed_audio is not None else self.engine.generated_audio
         import soundfile as sf; sf.write("prev.wav", t, self.engine.sr)
         pygame.mixer.music.load("prev.wav"); pygame.mixer.music.play()
         self.is_animating=True; self.anim_loop()
    def anim_loop(self):
        if not self.is_animating or not pygame.mixer.music.get_busy(): self.is_animating=False; return
        pos = pygame.mixer.music.get_pos(); spd = self.sl_speed.get()
        if pos >= 0 and self.engine.last_trajectory_x is not None:
            idx = int(pos * spd / 5.0)
            if idx < len(self.engine.last_trajectory_x):
                self.morph_x = self.engine.last_trajectory_x[idx]; self.morph_y = self.engine.last_trajectory_y[idx]
                self.update_xy_visuals()
        self.after(50, self.anim_loop)
    def toggle_playback(self, e=None):
        if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
        else: self.play_preview()

    # --- Batch ---
    def sel_outdir(self):
        d=filedialog.askdirectory()
        if d: self.outdir=d
    def open_outdir(self):
        try: os.startfile(self.outdir)
        except: pass
        
    def run_batch(self):
        if self.is_batch_running: return
        if self.engine.y_a is None: messagebox.showwarning("Err","No Master A"); return
        try: cnt=int(self.b_cnt.get())
        except: return
        self.is_batch_running=True; self.btn_batch.configure(state="disabled")
        threading.Thread(target=self.batch_worker, args=(cnt, self.b_pre.get()), daemon=True).start()

    def batch_worker(self, cnt, pre):
        shapes = ["Circle", "Eight", "Scan", "Random", "Static"]
        for i in range(cnt):
            self.after(0, lambda v=(i+1)/cnt: self.prog_batch.set(v))
            self.after(0, lambda c=i+1: self.lbl_status.configure(text=f"Batch {c}/{cnt}..."))
            
            def get_rnd(var, scale, base, rrange):
                if var.get(): return base + random.uniform(-scale.get()*rrange, scale.get()*rrange)
                return base
            def get_rnd_u(var, scale, base, rrange): # Unsigned
                if var.get(): return base + random.uniform(0, scale.get()*rrange)
                return base
                
            x, y = 0.5, 0.5
            shape = "Static";  mspeed = 1.0
            if self.r_motion[0].get():
                rng = self.r_motion[1].get()
                x = random.uniform(0.5-0.5*rng, 0.5+0.5*rng); y = random.uniform(0.5-0.5*rng, 0.5+0.5*rng)
                if random.random() < rng: shape = random.choice(shapes)
            if self.r_mspeed[0].get(): mspeed = random.uniform(0.5, 5.0*self.r_mspeed[1].get())
            
            formant = get_rnd(self.r_formant[0], self.r_formant[1], 1.0, 0.5) 
            breath = get_rnd_u(self.r_breath[0], self.r_breath[1], 0.0, 1.0)
            growl = get_rnd_u(self.r_growl[0], self.r_growl[1], 0.0, 1.0)
            tone = get_rnd(self.r_tone[0], self.r_tone[1], 0.0, 1.0)
            speed = get_rnd(self.r_speed[0], self.r_speed[1], 1.0, 0.5)
            dist = get_rnd_u(self.r_dist[0], self.r_dist[1], 0.0, 1.0)
            vol = get_rnd(self.r_vol[0], self.r_vol[1], 1.0, 0.2)
            
            p_curve = np.zeros(100)
            if self.r_pitch[0].get():
                 amp = self.r_pitch[1].get()*6.0
                 c=0
                 for k in range(100): c+=random.uniform(-1,1); c-=c*0.1; p_curve[k]=c
                 mx=np.max(np.abs(p_curve))
                 if mx>0: p_curve=p_curve/mx*amp
            
            fn = f"{pre}_{i+1:03d}.wav"; fp = os.path.join(self.outdir, fn)
            self.engine.render_batch_sample(fp, x, y, shape, mspeed, formant, breath, p_curve, speed, growl, tone, dist, vol)
            
        self.is_batch_running = False
        self.after(0, lambda: self.btn_batch.configure(state="normal"))
        self.after(0, lambda: self.lbl_status.configure(text="Batch Complete!"))
        self.after(0, lambda: messagebox.showinfo("Done", f"Finished {cnt} files."))

    # --- Chart (Spline) ---
    def update_spline_curve(self):
        # Sort points by X
        self.pitch_points.sort(key=lambda p: p[0])
        px = [p[0] for p in self.pitch_points]
        py = [p[1] for p in self.pitch_points]
        
        # Update markers
        self.point_scatter.set_data(px, py)
        
        # Calculate Spline
        if len(self.pitch_points) >= 2:
            try:
                cs = CubicSpline(px, py, bc_type='clamped')
                xs = np.linspace(0, 100, 100)
                ys = cs(xs)
                self.pitch_curve_y = np.clip(ys, -6, 6)
                self.line.set_data(xs, self.pitch_curve_y)
            except: pass
        else:
            # Fallback for <2 points (shouldn't happen with reset logic)
             self.line.set_data([], [])

        self.canvas.draw_idle()

    def on_chart_click(self, e): 
        if e.inaxes != self.ax: return
        
        # Check proximity
        dist_thresh = 2.0 # X-axis units roughly
        self.drag_point_idx = None
        
        # Find closest
        min_d = 999
        closest = -1
        for i, p in enumerate(self.pitch_points):
            dx = abs(p[0] - e.xdata)
            dy = abs(p[1] - e.ydata) # scale difference ignore for now approx
            if dx < 5 and dy < 1: # generous hit box
                d = dx + dy
                if d < min_d: min_d = d; closest = i
        
        if e.button == 3: # Right Click -> Delete
            if closest != -1:
                # Don't delete start/end if we want to enforce them? 
                # Let's allow flexibility but maybe keep at least 2 points
                if len(self.pitch_points) > 2:
                    self.pitch_points.pop(closest)
                    self.update_spline_curve()
            return

        # Left Click
        if closest != -1 and min_d < 10: # Hit existing? (refine threshold)
             self.drag_point_idx = closest
        else:
             # Add new point
             self.pitch_points.append([e.xdata, e.ydata])
             self.drag_point_idx = len(self.pitch_points) - 1 # Auto grab
             self.update_spline_curve()

    def on_chart_drag(self, e): 
        if self.drag_point_idx is not None and e.xdata is not None:
             # Update Point
             self.pitch_points[self.drag_point_idx] = [np.clip(e.xdata, 0, 100), np.clip(e.ydata, -6, 6)]
             self.update_spline_curve()

    def on_chart_release(self, e): 
        self.drag_point_idx = None

    def reset_pitch_curve_action(self):
         self.pitch_points = [[0, 0], [25, 2], [50, 0], [75, -2], [100, 0]]
         self.update_spline_curve()
    def save_file(self):
         p=filedialog.asksaveasfilename(defaultextension=".wav",filetypes=[("WAV","*.wav")]); 
         if p: self.engine.save_output(p)

    # --- State Management ---
    def get_state(self):
        state = {
            "sliders": {
                "breath": self.sl_breath.get(),
                "formant": self.sl_formant.get(),
                "growl": self.sl_growl.get(),
                "tone": self.sl_tone.get(),
                "speed": self.sl_speed.get(),
                "dist": self.sl_dist.get(),
                "vol": self.sl_vol.get(),
                "mspeed": self.slider_mspeed.get()
            },
            "options": {
                "shape": self.cmb_shape.get()
            },
            "morph": {
                "x": self.morph_x,
                "y": self.morph_y
            },
            "pitch": self.pitch_points,
            "batch": {
                "count": self.b_cnt.get(),
                "prefix": self.b_pre.get(),
                "outdir": self.outdir,
                "randoms": {}
            }
        }
        
        # Helper for randoms
        rnd_map = {
            "motion": self.r_motion, "mspeed": self.r_mspeed, "breath": self.r_breath,
            "formant": self.r_formant, "growl": self.r_growl, "tone": self.r_tone,
            "pitch": self.r_pitch, "speed": self.r_speed, "dist": self.r_dist, "vol": self.r_vol
        }
        for k, v in rnd_map.items():
            state["batch"]["randoms"][k] = {"enabled": v[0].get(), "value": v[1].get()}
            
        return state

    def set_state(self, state):
        try:
            # Sliders
            s = state.get("sliders", {})
            self.sl_breath.set(s.get("breath", 0))
            self.sl_formant.set(s.get("formant", 1))
            self.sl_growl.set(s.get("growl", 0))
            self.sl_tone.set(s.get("tone", 0))
            self.sl_speed.set(s.get("speed", 1))
            self.sl_dist.set(s.get("dist", 0))
            self.sl_vol.set(s.get("vol", 1))
            self.slider_mspeed.set(s.get("mspeed", 1))
            
            # Options
            self.cmb_shape.set(state.get("options", {}).get("shape", "Static"))
            
            # Morph
            m = state.get("morph", {})
            self.morph_x = m.get("x", 0.5)
            self.morph_y = m.get("y", 0.5)
            self.update_xy_visuals()
            
            # Pitch
            self.pitch_points = state.get("pitch", [[0,0],[25,2],[50,0],[75,-2],[100,0]])
            self.update_spline_curve()
            
            # Batch
            b = state.get("batch", {})
            self.b_cnt.delete(0, tk.END); self.b_cnt.insert(0, b.get("count", "30"))
            self.b_pre.delete(0, tk.END); self.b_pre.insert(0, b.get("prefix", "Monster"))
            self.outdir = b.get("outdir", os.getcwd())
            
            rnd = b.get("randoms", {})
            rnd_map = {
                "motion": self.r_motion, "mspeed": self.r_mspeed, "breath": self.r_breath,
                "formant": self.r_formant, "growl": self.r_growl, "tone": self.r_tone,
                "pitch": self.r_pitch, "speed": self.r_speed, "dist": self.r_dist, "vol": self.r_vol
            }
            for k, val in rnd.items():
                if k in rnd_map:
                    rnd_map[k][0].set(val.get("enabled", True))
                    rnd_map[k][1].set(val.get("value", 0.5))
                    
        except Exception as e:
            print(f"Error loading state: {e}")

    def save_settings(self):
        d = os.path.join(os.getcwd(), "Settings")
        p = filedialog.asksaveasfilename(initialdir=d, defaultextension=".json", filetypes=[("JSON Config", "*.json")])
        if p:
            try:
                with open(p, "w") as f: json.dump(self.get_state(), f, indent=4)
                messagebox.showinfo("Success", "Settings saved!")
            except Exception as e: messagebox.showerror("Error", str(e))

    def load_settings(self):
        d = os.path.join(os.getcwd(), "Settings")
        p = filedialog.askopenfilename(initialdir=d, filetypes=[("JSON Config", "*.json")])
        if p:
            try:
                with open(p, "r") as f: self.set_state(json.load(f))
                messagebox.showinfo("Success", "Settings loaded!")
            except Exception as e: messagebox.showerror("Error", str(e))
            
    def save_last_state(self):
        try:
             with open("last_state.json", "w") as f: json.dump(self.get_state(), f)
        except: pass

    def load_last_state(self):
        try:
            if os.path.exists("last_state.json"):
                with open("last_state.json", "r") as f: self.set_state(json.load(f))
        except: pass

    def on_closing(self):
        self.save_last_state()
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()
