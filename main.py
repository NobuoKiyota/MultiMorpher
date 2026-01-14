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
from matplotlib.figure import Figure
from tkinterdnd2 import DND_FILES, TkinterDnD
from audio_engine import AudioEngine
from scipy.interpolate import PchipInterpolator
import time
import json

class CollapsibleFrame(ctk.CTkFrame):
    def __init__(self, parent, title="Title"):
        super().__init__(parent, fg_color="transparent")
        self.expanded = True
        self.title_text = title
        
        self.btn = ctk.CTkButton(self, text=f"▼ {title}", command=self.toggle, 
                                 fg_color="#222", hover_color="#333", 
                                 height=24,
                                 anchor="w", font=("Roboto", 11, "bold"), text_color="#ccc")
        self.btn.pack(fill="x", pady=1)
        
        self.frame = ctk.CTkFrame(self, fg_color="#161616", corner_radius=0)
        self.frame.pack(fill="x", padx=0, pady=0)
        
    def toggle(self):
        self.expanded = not self.expanded
        if self.expanded:
            self.frame.pack(fill="x", padx=0, pady=0)
            self.btn.configure(text=f"▼ {self.title_text}")
        else:
            self.frame.pack_forget()
            self.btn.configure(text=f"▶ {self.title_text}")

class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title("MultiMorpher - Advanced Audio Synthesis")
        self.geometry("1400x900")
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        
        self.engine = AudioEngine()
        pygame.mixer.init()
        
        self.pitch_curve_y = np.zeros(100)
        self.autoplay_morph = False
        self.is_morphing_busy = False
        self.is_batch_running = False
        self.morph_x = 0.5
        self.morph_y = 0.5
        self.morph_x = 0.5
        self.morph_y = 0.5
        self.is_animating = False
        self.debounce_timer = None
        
        # Meter Layout Config
        self.meter_bar_width = 25
        self.meter_gap = 4
        self.meter_margin = 5
        
        # Explorer State
        self.current_dir = os.getcwd()
        self.pins = []
        self.load_pins()
        
        # Grid Layout
        self.grid_columnconfigure(0, weight=0, minsize=260) 
        self.grid_columnconfigure(1, weight=0, minsize=260) 
        self.grid_columnconfigure(2, weight=1) 
        self.grid_columnconfigure(3, weight=0, minsize=340) 
        self.grid_columnconfigure(4, weight=0, minsize=60) # Level Meter
        self.grid_rowconfigure(0, weight=1)
        
        # Frames
        self.col_explorer = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.col_explorer.grid(row=0, column=0, sticky="nsew", padx=1)
        
        self.col_source = ctk.CTkFrame(self, corner_radius=0, fg_color="#222222")
        self.col_source.grid(row=0, column=1, sticky="nsew", padx=1)
        
        self.col_center = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="#111")
        self.col_center.grid(row=0, column=2, sticky="nsew", padx=1)
        
        self.col_batch = ctk.CTkFrame(self, corner_radius=0, fg_color="#1a1a1a")
        self.col_batch.grid(row=0, column=3, sticky="nsew", padx=1)
        
        self.col_meter = ctk.CTkFrame(self, corner_radius=0, fg_color="#111")
        self.col_meter.grid(row=0, column=4, sticky="nsew", padx=1)
        
        self.lbl_status = ctk.CTkLabel(self, text="Ready", text_color="gray", fg_color="#111")
        self.lbl_status.grid(row=1, column=0, columnspan=5, sticky="ew")

        # Shortcuts
        self.key_map = {}
        self.load_keybindings()
        
        # Bindings (Wrapped to check focus)
        self.bind(self.key_map.get("MORPH", "g"), lambda e: self._on_shortcut(lambda: self.trigger_morph(self.var_auto_apply.get())))
        self.bind(self.key_map.get("MORPH_AND_AUTO", "G"), lambda e: self._on_shortcut(lambda: self.trigger_morph(True)))
        self.bind(self.key_map.get("APPLY_FX", "h"), lambda e: self._on_shortcut(self.apply_pitch_thread))
        self.bind(self.key_map.get("CHAOS", "?"), lambda e: self._on_shortcut(self.chaos_action))
        self.bind(self.key_map.get("SNAPSHOT", "s"), lambda e: self._on_shortcut(self.quick_save))
        self.bind(self.key_map.get("SAVE", "<Control-s>"), lambda e: self.save_file()) # Save can override? No, consistency.
        self.bind(self.key_map.get("PLAY_STOP", "<space>"), lambda e: self._on_shortcut(self.toggle_playback))
        # Remove focus from entries when clicking BG
        self.bind_all("<Button-1>", self.check_focus_out)
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Init UI
        self._init_explorer()
        self._init_source()
        self._init_editor()
        self._init_batch()
        self._init_level_meter()
        
        self.refresh_file_list()
        self.after(200, self.load_last_state)

    # --- KEYBINDINGS & HELP ---
    # --- KEYBINDINGS & HELP ---
    def load_keybindings(self):
        default_keys = { "MORPH":"g", "MORPH_AND_AUTO":"G", "APPLY_FX":"h", "CHAOS":"?", "SNAPSHOT":"s", "SAVE":"<Control-Key-s>", "PLAY_STOP":"<space>" }
        try:
            if os.path.exists("keybindings.json"):
                with open("keybindings.json", "r") as f: self.key_map = json.load(f)
            else: self.key_map = default_keys
        except: self.key_map = default_keys
        
        if not os.path.exists("Settings"): 
            try: os.makedirs("Settings")
            except: pass
        if not os.path.exists("Snapshots"): 
            try: os.makedirs("Snapshots")
            except: pass

    def _on_shortcut(self, func):
        # Prevent shortcut execution if typing in an entry
        f = self.focus_get()
        if f and (f.winfo_class() == "Entry" or "Entry" in str(f.winfo_class())):
            return
        func()

    def check_focus_out(self, event):
        # Entryウィジェット以外をクリックした場合にフォーカスを外す
        w = event.widget
        try:
             # Check if widget class is related to Entry
             # Note: CustomTkinter entries are frames containing standard entries usually, logic might vary.
             # check class name standard tk
             c = w.winfo_class()
             if "Entry" not in c and "Text" not in c:
                  self.focus_set()
        except: pass

    def debounce_apply(self, *args):
        if not self.var_auto_apply.get(): return
        if self.debounce_timer:
            self.after_cancel(self.debounce_timer)
        self.debounce_timer = self.after(300, self.apply_pitch_thread)

    def validate_float(self, P):
        if P == "" or P == "-" or P == ".": return True
        try:
            float(P)
            return True
        except ValueError:
            return False

    def on_entry_scroll(self, event, entry, step):
        try:
            current_str = entry.get()
            val = float(current_str) if current_str and current_str not in ["-","."] else 0.0
        except: val = 0.0
        
        if event.delta > 0: val += step
        else: val -= step
        
        # Smart rounding to avoid 0.300000004
        if step >= 1:
            val = int(round(val))
            s_val = str(val)
        else:
            val = round(val, 2)
            s_val = str(val)
            
        entry.delete(0, "end")
        entry.insert(0, s_val)
        return "break"

    def open_help(self):
        # Internal Help UI
        top = ctk.CTkToplevel(self)
        top.title("Manual - MultiMorpher")
        top.geometry("700x700")
        top.attributes("-topmost", True)
        
        # Header / Lang Switch
        f_top = ctk.CTkFrame(top, fg_color="transparent")
        f_top.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(f_top, text="User Manual", font=("Roboto", 18, "bold")).pack(side="left", padx=10)
        
        def load_md(fn):
            text_box.configure(state="normal")
            text_box.delete("0.0", "end")
            path = fn
            if os.path.exists(path):
                try: 
                    with open(path, "r", encoding="utf-8") as f: text_box.insert("0.0", f.read())
                except Exception as e: text_box.insert("0.0", str(e))
            else:
                text_box.insert("0.0", f"File not found: {path} \n\nPlease generate MANUAL.md")
            text_box.configure(state="disabled")

        ctk.CTkButton(f_top, text="English", width=80, command=lambda: load_md("MANUAL.md")).pack(side="right", padx=5)
        ctk.CTkButton(f_top, text="日本語", width=80, command=lambda: load_md("MANUAL_JP.md")).pack(side="right", padx=5)

        text_box = ctk.CTkTextbox(top, font=("Consolas", 12)) 
        text_box.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Default load
        target = "MANUAL_JP.md" if os.path.exists("MANUAL_JP.md") else "MANUAL.md"
        load_md(target)
        
        ctk.CTkButton(top, text="Close", command=top.destroy, fg_color="#444").pack(pady=10)
    # ================= 1. EXPLORER (Left) =================
    def _init_explorer(self):
        f_head = ctk.CTkFrame(self.col_explorer, fg_color="transparent")
        f_head.pack(fill="x", pady=(10,5), padx=5)
        
        ctk.CTkLabel(f_head, text="EXPLORER", font=("Roboto", 14, "bold"), text_color="#aaa").pack(side="left")
        ctk.CTkButton(f_head, text="?", width=24, height=24, command=self.open_help, fg_color="#444").pack(side="right")
        
        self.drives = self.get_drives()
        self.cmb_drive = ctk.CTkOptionMenu(self.col_explorer, values=self.drives, command=self.on_drive_change, width=200)
        self.cmb_drive.set(os.path.splitdrive(os.getcwd())[0])
        self.cmb_drive.pack(pady=5)
        
        # Pins
        self.frame_pins = ctk.CTkFrame(self.col_explorer, fg_color="transparent")
        self.frame_pins.pack(fill="x")
        ctk.CTkButton(self.frame_pins, text="+ Pin Current", command=self.add_pin, height=20, fg_color="#444").pack(fill="x", padx=5)
        self.frame_pin_list = ctk.CTkScrollableFrame(self.col_explorer, height=100, fg_color="transparent")
        self.frame_pin_list.pack(fill="x", padx=5, pady=5)
        self.update_pin_list_ui()
        
        # Path & Nav
        frame_nav = ctk.CTkFrame(self.col_explorer, fg_color="transparent")
        frame_nav.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(frame_nav, text="⬆", width=30, command=self.go_up, fg_color="#444").pack(side="left")
        self.lbl_path = ctk.CTkLabel(frame_nav, text=".", text_color="gray", anchor="w")
        self.lbl_path.pack(side="left", padx=5, fill="x")
        
        # Preview
        frame_prev = ctk.CTkFrame(self.col_explorer, fg_color="transparent")
        frame_prev.pack(fill="x", padx=5)
        self.var_autoplay = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(frame_prev, text="Auto", variable=self.var_autoplay, width=50).pack(side="left")
        ctk.CTkButton(frame_prev, text="■", width=30, command=self.stop_preview, fg_color="#C62828").pack(side="left", padx=5)
        sl_vol = ctk.CTkSlider(frame_prev, from_=0, to=1, width=80, command=self.set_vol_preview)
        sl_vol.set(0.5); sl_vol.pack(side="left")

        # List
        self.listbox = tk.Listbox(self.col_explorer, bg="#202020", fg="white", selectbackground="#4da6ff", borderwidth=0, font=("Consolas", 10))
        self.listbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.listbox.bind("<Double-Button-1>", self.on_list_double_click)
        self.listbox.bind("<<ListboxSelect>>", self.on_list_select)
        self.listbox.bind("<Button-3>", self.on_list_right_click)
        self.listbox.drag_source_register(1, DND_FILES)
        self.listbox.dnd_bind('<<DragInitCmd>>', self.on_drag_init)
        
    def get_drives(self):
        import string
        drives = []
        for d in string.ascii_uppercase:
            if os.path.exists(f"{d}:"): drives.append(f"{d}:")
        return drives
    def on_drive_change(self, choice):
        if os.path.exists(choice): self.current_dir = choice + "\\"; self.refresh_file_list()
    def get_file_list(self):
        try:
            items = os.listdir(self.current_dir)
            dirs = sorted([d for d in items if os.path.isdir(os.path.join(self.current_dir, d))], key=str.lower)
            files = sorted([f for f in items if os.path.isfile(os.path.join(self.current_dir, f)) and f.lower().endswith(('.wav','.mp3','.flac','.ogg','.aif','.aiff'))], key=str.lower)
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
             self.current_dir = os.path.join(self.current_dir, txt[2:])
             self.refresh_file_list()
    def on_list_right_click(self, e):
        idx = self.listbox.nearest(e.y)
        self.listbox.selection_clear(0, tk.END); self.listbox.selection_set(idx); self.listbox.activate(idx)
        txt = self.listbox.get(idx)
        if not txt.startswith("🎵 "): return
        path = os.path.join(self.current_dir, txt[2:])
        m = tk.Menu(self, tearoff=0)
        m.add_command(label="Load into A (Master)", command=lambda: self.load_a(path))
        m.add_command(label="Load into B", command=lambda: self.load_b(path))
        m.add_command(label="Load into C", command=lambda: self.load_c(path))
        m.add_command(label="Load into D", command=lambda: self.load_d(path))
        m.tk_popup(e.x_root, e.y_root)
    def on_list_select(self, e):
        if not self.var_autoplay.get(): return
        sel = self.listbox.curselection()
        if not sel: return
        txt = self.listbox.get(sel[0])
        if txt.startswith("🎵 "):
            path = os.path.join(self.current_dir, txt[2:])
            self.play_explorer_preview(path)
    def stop_preview(self, e=None): 
        if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
    def set_vol_preview(self, val): pygame.mixer.music.set_volume(float(val))
    def go_up(self):
        self.current_dir = os.path.dirname(self.current_dir)
        self.refresh_file_list()
    def add_pin(self):
        p = os.path.normpath(self.current_dir)
        if p not in self.pins: 
            self.pins.append(p)
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
            # Use basename unless root
            name = os.path.basename(p) or p
            ctk.CTkButton(f, text=name, command=lambda x=p: self.go_to_pin(x), height=20, fg_color="transparent", border_width=1, anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(f, text="x", command=lambda x=i: self.delete_pin(x), width=20, height=20, fg_color="#522").pack(side="right")
    def delete_pin(self, index): self.pins.pop(index); self.save_pins(); self.update_pin_list_ui()
    
    def go_to_pin(self, path):
        if os.path.exists(path): 
            try:
                self.current_dir = os.path.normpath(path)
                # Update Drive Combo
                curr_drive = os.path.splitdrive(self.current_dir)[0].upper()
                # Ensure : format
                if curr_drive and not curr_drive.endswith(":"): curr_drive += ":"
                if curr_drive in self.drives: self.cmb_drive.set(curr_drive)
                
                self.refresh_file_list()
            except Exception as e: messagebox.showerror("Err", f"Cannot access pin: {e}")
        else:
             messagebox.showwarning("Missing", "Directory not found.")
    def on_drag_init(self, event):
        sel = self.listbox.curselection()
        if not sel: return None
        txt = self.listbox.get(sel[0])
        if txt.startswith("🎵 "): return ((map, DND_FILES, os.path.join(self.current_dir, txt[2:])),)
        return None
    def play_explorer_preview(self, path):
        try:
            if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
            pygame.mixer.music.load(path); pygame.mixer.music.play()
        except: pass

    # ================= 2. SOURCE (Col 1) =================
    def _init_source(self):
        ctk.CTkLabel(self.col_source, text="SOURCES", font=("Roboto", 14, "bold"), text_color="#4da6ff").pack(pady=(5,2))
        def mkbtn(t, c):
            b = ctk.CTkButton(self.col_source, text=t, command=c, height=28, fg_color="#333", border_color="#444", border_width=1)
            b.pack(pady=1, padx=5, fill="x")
            b.drop_target_register(DND_FILES); b.dnd_bind('<<Drop>>', lambda e: self.on_drop(e, c))
            return b
        self.btn_a = mkbtn("Load A (Master)", self.load_a)
        self.btn_b = mkbtn("Load B", self.load_b)
        self.btn_c = mkbtn("Load C", self.load_c)
        self.btn_d = mkbtn("Load D", self.load_d)
        
        ctk.CTkLabel(self.col_source, text="MORPH PAD", font=("Roboto", 12, "bold"), text_color="#4da6ff").pack(pady=(10,2))
        self.canvas_xy = tk.Canvas(self.col_source, width=200, height=200, bg="#1a1a1a", highlightthickness=0)
        self.canvas_xy.pack(pady=2)
        self.canvas_xy.create_text(10,10,text="A",fill="#888",anchor="nw")
        self.canvas_xy.create_text(190,10,text="B",fill="#888",anchor="ne")
        self.canvas_xy.create_text(10,190,text="C",fill="#888",anchor="sw")
        self.canvas_xy.create_text(190,190,text="D",fill="#888",anchor="se")
        self.xy_handle = self.canvas_xy.create_oval(0,0,16,16, fill="#4da6ff", outline="white")
        self.update_xy_visuals()
        self.canvas_xy.bind("<Button-1>", self.on_xy_click)
        self.canvas_xy.bind("<B1-Motion>", self.on_xy_drag)
        self.canvas_xy.bind("<ButtonRelease-1>", self.on_xy_release)
        
        f_mot = ctk.CTkFrame(self.col_source, fg_color="transparent")
        f_mot.pack(fill="x", pady=(5,0))
        ctk.CTkLabel(f_mot, text="MOTION", font=("Roboto", 10), width=50).pack(side="left")
        self.cmb_shape = ctk.CTkOptionMenu(f_mot, values=["Static", "RandomPoint", "Circle", "Eight", "Scan", "RandomMovement"], width=130, height=24)
        self.cmb_shape.set("Static"); self.cmb_shape.pack(side="left", padx=2)
        
        self.slider_mspeed = ctk.CTkSlider(self.col_source, from_=0.1, to=5.0, height=16); self.slider_mspeed.set(1.0); self.slider_mspeed.pack(pady=(2,0))
        
        # Action Buttons Here
        self.var_auto_apply = tk.BooleanVar(value=True)
        self.var_auto_morph = tk.BooleanVar(value=False)
        
        f_chk = ctk.CTkFrame(self.col_source, fg_color="transparent")
        f_chk.pack(pady=(5,0))
        ctk.CTkCheckBox(f_chk, text="Auto Morph", variable=self.var_auto_morph, font=("Roboto",10), width=80, height=20).pack(side="left", padx=5)
        ctk.CTkCheckBox(f_chk, text="Auto Apply", variable=self.var_auto_apply, font=("Roboto",10), width=80, height=20).pack(side="left", padx=5)
        
        self.btn_morph = ctk.CTkButton(self.col_source, text="MORPH (G)", command=lambda: self.trigger_morph(self.var_auto_apply.get()), fg_color="#E53935", height=32, font=("Roboto",12,"bold"))
        self.btn_morph.pack(fill="x", padx=10, pady=(5, 2))
        
        self.btn_apply = ctk.CTkButton(self.col_source, text="APPLY FX (H)", command=self.apply_pitch_thread, state="disabled", fg_color="#1976D2", height=32, font=("Roboto",12))
        self.btn_apply.pack(fill="x", padx=10, pady=2)
        
        self.btn_preview = ctk.CTkButton(self.col_source, text="▶ PLAY (Space)", command=self.play_preview, state="disabled", fg_color="#43A047", height=32, font=("Roboto",12))
        self.btn_preview.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkFrame(self.col_source, height=30, fg_color="transparent").pack() # Spacer

        self.btn_chaos = ctk.CTkButton(self.col_source, text="CHAOS (?)", command=self.chaos_action, fg_color="#8E24AA", height=32, font=("Roboto",12,"bold"))
        self.btn_chaos.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkFrame(self.col_source, height=30, fg_color="transparent").pack() # Spacer

        self.btn_snap = ctk.CTkButton(self.col_source, text="SNAPSHOT (S)", command=self.quick_save, fg_color="#FBC02D", text_color="black", height=32, font=("Roboto",12,"bold"))
        self.btn_snap.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkButton(self.col_source, text="SAVE WAV (Ctrl+S)", command=self.save_file, height=28, fg_color="#555").pack(fill="x", padx=10, pady=(5,5))
        
        # Settings
        f_sets = ctk.CTkFrame(self.col_source, fg_color="transparent")
        f_sets.pack(fill="x", padx=5, pady=(0,10))
        ctk.CTkButton(f_sets, text="💾 Save Sets", command=self.save_settings, width=60, fg_color="#333", height=24, font=("Roboto",10)).pack(side="left", padx=1, expand=True, fill="x")
        ctk.CTkButton(f_sets, text="📂 Load Sets", command=self.load_settings, width=60, fg_color="#333", height=24, font=("Roboto",10)).pack(side="left", padx=1, expand=True, fill="x")

    # ================= 3. EDITOR (Col 2 - ACORDION) =================
    def _init_editor(self):
        ctk.CTkLabel(self.col_center, text="EDITOR", font=("Roboto", 16, "bold"), text_color="#eee").pack(pady=10)
        
        # PITCH GRAPH
        self.f_pitch = CollapsibleFrame(self.col_center, "PITCH CURVE")
        self.f_pitch.pack(fill="x", padx=5, pady=2)
        
        plt.style.use('dark_background')
        # Embed Matplotlib
        self.pitch_fig = Figure(figsize=(5,2), dpi=100, facecolor="#111")
        self.ax = self.pitch_fig.add_subplot(111)
        self.ax.set_facecolor("#111")
        self.ax.tick_params(colors='white', labelsize=8)
        self.ax.grid(True, color="#333", linestyle='--')
        self.ax.set_xlim(0, 100); self.ax.set_ylim(-6, 6)
        
        # Waveform Background
        self.cached_wave = None
        self.wave_line, = self.ax.plot([], [], color='#4fc3f7', alpha=0.3, lw=1)
        
        self.line, = self.ax.plot([], [], color='#4da6ff', linewidth=2)
        self.point_scatter, = self.ax.plot([], [], 'o', color='white', markeredgecolor='#4da6ff')
        
        self.canvas_chart = FigureCanvasTkAgg(self.pitch_fig, master=self.f_pitch.frame)
        self.canvas_chart.get_tk_widget().pack(fill="x", padx=2, pady=2)
        self.canvas_chart.mpl_connect('button_press_event', self.on_chart_click)
        self.canvas_chart.mpl_connect('motion_notify_event', self.on_chart_drag)
        self.canvas_chart.mpl_connect('button_release_event', self.on_chart_release)
        
        self.pitch_points = [] 
        self.drag_point_idx = None
        self.pitch_range = 6.0
        
        # Pitch Ctrl Row
        f_pctrl = ctk.CTkFrame(self.f_pitch.frame, fg_color="transparent")
        f_pctrl.pack(fill="x", pady=2)
        ctk.CTkButton(f_pctrl, text="Reset", command=self.reset_pitch_curve_action, width=60, height=20, fg_color="#333").pack(side="left", padx=5)
        
        ctk.CTkLabel(f_pctrl, text="Range ±:", font=("Roboto",10)).pack(side="left", padx=2)
        self.ent_prange = ctk.CTkEntry(f_pctrl, width=40, height=20, validate="key", validatecommand=(self.register(self.validate_float), '%P'))
        self.ent_prange.insert(0, "6")
        self.ent_prange.pack(side="left")
        self.ent_prange.bind("<Return>", self.update_pitch_range_ui)
        self.ent_prange.bind("<FocusOut>", self.update_pitch_range_ui)
        
        def on_prange_scroll(e):
            self.on_entry_scroll(e, self.ent_prange, 1.0)
            self.update_pitch_range_ui()
            return "break"
        self.ent_prange.bind("<MouseWheel>", on_prange_scroll)
        
        self.reset_pitch_curve_action()

        # Helper to make sliders
        def mksl(parent, label, mn, mx, df):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(fill="x", pady=2)
            lbl = ctk.CTkLabel(f, text=label, width=80, anchor="w", font=("Roboto",11))
            lbl.pack(side="left")
            s = ctk.CTkSlider(f, from_=mn, to=mx, height=16, command=self.debounce_apply)
            s.set(df)
            s.pack(side="right", fill="x", expand=True, padx=5)
            
            def on_wheel(e):
                val = s.get()
                step = (mx - mn) * 0.05 # 5% step
                if e.delta > 0: val += step
                else: val -= step
                val = max(mn, min(mx, val))
                s.set(val)
                self.debounce_apply()
                return "break"
            
            s.bind("<MouseWheel>", on_wheel)
            f.bind("<MouseWheel>", on_wheel)
            lbl.bind("<MouseWheel>", on_wheel)
            
            return s

        # 1. CORE FX
        self.f_core = CollapsibleFrame(self.col_center, "CORE EFFECTS")
        self.f_core.pack(fill="x", padx=5, pady=2)
        self.sl_formant = mksl(self.f_core.frame, "Formant", 0.5, 2.0, 1.0)
        self.sl_breath = mksl(self.f_core.frame, "Breath", 0.0, 1.0, 0.0)
        self.sl_speed = mksl(self.f_core.frame, "Speed", 0.5, 2.0, 1.0)
        self.sl_vol = mksl(self.f_core.frame, "Volume", 0.0, 1.5, 1.0)
        
        # 2. MODULATION
        self.f_mod = CollapsibleFrame(self.col_center, "MODULATION & TONE")
        self.f_mod.pack(fill="x", padx=5, pady=2)
        self.sl_growl = mksl(self.f_mod.frame, "Growl", 0.0, 1.0, 0.0)
        self.sl_tone = mksl(self.f_mod.frame, "Tone (Filter)", -1.0, 1.0, 0.0)
        self.sl_ring_mix = mksl(self.f_mod.frame, "Ring Mix", 0.0, 1.0, 0.0)
        self.sl_ring_freq = mksl(self.f_mod.frame, "Ring Freq", 30, 3000, 30) # High range
        
        # 3. SPACE & TIME
        self.f_space = CollapsibleFrame(self.col_center, "SPACE & TIME")
        self.f_space.pack(fill="x", padx=5, pady=2)
        self.sl_spacer = mksl(self.f_space.frame, "Spacer Width", 0.0, 2.0, 1.0)
        self.sl_reverb = mksl(self.f_space.frame, "Reverb Mix", 0.0, 0.5, 0.0)
        
        f_d = ctk.CTkFrame(self.f_space.frame, fg_color="transparent")
        f_d.pack(fill="x", pady=2)
        ctk.CTkLabel(f_d, text="Delay", font=("Roboto",11,"bold"), anchor="w").pack(fill="x")
        self.sl_d_time = mksl(self.f_space.frame, "  Time (s)", 0.01, 1.0, 0.2)
        self.sl_d_fb = mksl(self.f_space.frame, "  Feedback", 0.0, 0.9, 0.3)
        self.sl_d_mix = mksl(self.f_space.frame, "  Mix", 0.0, 0.5, 0.0)
        
        # 4. LO-FI
        self.f_lofi = CollapsibleFrame(self.col_center, "LO-FI / DIST")
        self.f_lofi.pack(fill="x", padx=5, pady=2)
        self.sl_dist = mksl(self.f_lofi.frame, "Distortion", 0.0, 1.0, 0.0)
        self.sl_bits = mksl(self.f_lofi.frame, "Bit Depth", 4, 16, 16)
        self.sl_srdiv = mksl(self.f_lofi.frame, "SR Divider", 1, 50, 1)

    # ================= 4. BATCH (Col 3) =================
    def _init_batch(self):
        ctk.CTkLabel(self.col_batch, text="BATCH FACTORY 🏭", font=("Roboto", 16, "bold"), text_color="#FFA726").pack(pady=10)
        
        fc = ctk.CTkFrame(self.col_batch, fg_color="#222")
        fc.pack(fill="x", padx=10)
        self.b_cnt = ctk.CTkEntry(fc, width=60); self.b_cnt.insert(0,"30")
        self.b_pre = ctk.CTkEntry(fc, width=80); self.b_pre.insert(0,"Monster")
        
        ctk.CTkLabel(fc, text="Count:").pack(side="left", padx=5)
        self.b_cnt.pack(side="left", padx=5)
        ctk.CTkLabel(fc, text="Prefix:").pack(side="left", padx=5)
        self.b_pre.pack(side="left", padx=5)
        
        f_od = ctk.CTkFrame(self.col_batch, fg_color="transparent")
        f_od.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(f_od, text="Output Directory", command=self.sel_outdir, height=24, fg_color="#444").pack(side="left", fill="x", expand=True, padx=(0,2))
        ctk.CTkButton(f_od, text="📂 Open", command=self.open_outdir, height=24, width=60, fg_color="#444").pack(side="right")
        self.outdir = os.getcwd()
        
        # Ranges
        self.scroll_batch = ctk.CTkScrollableFrame(self.col_batch, height=500, label_text="Random Ranges (Min - Max)")
        self.scroll_batch.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.batch_ranges = {}
        
        def add_rng(key, label, d_min, d_max, l_min=0.0, l_max=1.0):
            f = ctk.CTkFrame(self.scroll_batch, fg_color="transparent")
            f.pack(fill="x", pady=1)
            # Left aligned label
            ctk.CTkLabel(f, text=label, width=90, anchor="w", font=("Roboto",10)).pack(side="left", padx=2)
            
            vcmd = (self.register(self.validate_float), '%P')
            
            e1 = ctk.CTkEntry(f, width=50, height=20, font=("Consolas",10), validate="key", validatecommand=vcmd)
            e1.insert(0, str(d_min))
            e1.pack(side="left", padx=2)
            
            ctk.CTkLabel(f, text="-", width=10).pack(side="left")
            
            e2 = ctk.CTkEntry(f, width=50, height=20, font=("Consolas",10), validate="key", validatecommand=vcmd)
            e2.insert(0, str(d_max))
            e2.pack(side="left", padx=2)
            
            # Limit info
            info = f"({l_min}~{l_max})"
            ctk.CTkLabel(f, text=info, font=("Roboto", 9), text_color="#666").pack(side="left", padx=5)

            # --- Validation Logic ---
            def validate_batch(e=None):
                try: v1 = float(e1.get())
                except: v1 = l_min
                try: v2 = float(e2.get())
                except: v2 = l_max
                
                # Clamp global
                v1 = max(l_min, min(l_max, v1))
                v2 = max(l_min, min(l_max, v2))
                
                # Check Min > Max
                if v1 > v2:
                    # Enforce constraint. If typing Min causes it to exceed Max, we could push Max.
                    # But simpler is preventing Min > Max.
                    # Or just swap? No.
                    # Let's cap v1 to v2.
                    v1 = min(v1, v2)
                
                # Formatting
                fmt = lambda x: str(int(x)) if x.is_integer() else str(round(x, 2))
                s1, s2 = fmt(v1), fmt(v2)
                
                if e1.get() != s1: e1.delete(0, "end"); e1.insert(0, s1)
                if e2.get() != s2: e2.delete(0, "end"); e2.insert(0, s2)
            
            e1.bind("<FocusOut>", validate_batch)
            e1.bind("<Return>", validate_batch)
            e2.bind("<FocusOut>", validate_batch)
            e2.bind("<Return>", validate_batch)
            
            # Scroll with Validation
            def on_wheel_local(e, ent):
                self.on_entry_scroll(e, ent, 0.1)
                validate_batch()
                return "break" # Stop propagation

            e1.bind("<MouseWheel>", lambda e: on_wheel_local(e, e1))
            e2.bind("<MouseWheel>", lambda e: on_wheel_local(e, e2))
            
            self.batch_ranges[key] = (e1, e2)
            
        add_rng("morph_x", "Morph X", 0.0, 1.0, 0.0, 1.0)
        add_rng("morph_y", "Morph Y", 0.0, 1.0, 0.0, 1.0)
        add_rng("mspeed", "M-Speed", 0.5, 2.0, 0.1, 5.0)
        
        # Core
        add_rng("formant", "Formant", 0.8, 1.2, 0.5, 2.0)
        add_rng("breath", "Breath", 0.0, 0.5, 0.0, 1.0)
        add_rng("speed", "Speed", 0.9, 1.1, 0.5, 2.0)
        add_rng("vol", "Volume", 0.8, 1.0, 0.0, 1.5)
        
        # Mod
        add_rng("growl", "Growl", 0.0, 0.5, 0.0, 1.0)
        add_rng("tone", "Tone", -0.5, 0.5, -1.0, 1.0)
        add_rng("ring_mix", "Ring Mix", 0.0, 0.3, 0.0, 1.0)
        add_rng("ring_freq","Ring Freq", 30, 200, 30, 3000)

        # Space
        add_rng("spacer", "Spacer", 0.8, 1.2, 0.0, 2.0)
        add_rng("reverb", "Reverb", 0.0, 0.2, 0.0, 0.5)
        add_rng("d_time", "D Time", 0.1, 0.3, 0.0, 1.0)
        add_rng("d_fb", "D Feed", 0.0, 0.4, 0.0, 0.9)
        add_rng("d_mix", "D Mix", 0.0, 0.3, 0.0, 0.5)
        
        # Lofi
        add_rng("dist", "Distortion", 0.0, 0.2, 0.0, 1.0)
        add_rng("bits", "BitDepth", 12, 16, 4, 32)
        add_rng("srdiv", "SR Div", 1, 4, 1, 50)
        
        self.prog_batch = ctk.CTkProgressBar(self.col_batch, progress_color="#FFA726")
        self.prog_batch.set(0)
        self.prog_batch.pack(fill="x", padx=10, pady=5)
        
        self.btn_batch = ctk.CTkButton(self.col_batch, text="🚀 RUN BATCH", command=self.run_batch, height=40, font=("Roboto", 12, "bold"), fg_color="#FFA726", text_color="black", hover_color="#F57C00")
        self.btn_batch.pack(fill="x", padx=10, pady=10)

    # ================= LOGIC HANDLERS =================
    
    def load_generic(self, f, btn):
        p = filedialog.askopenfilename()
        if p: f(p); btn.configure(text=os.path.basename(p))
    def load_a(self, path=None): 
        if not path: path=filedialog.askopenfilename()
        if path: 
            self.engine.load_source(0, path); self.btn_a.configure(text=os.path.basename(path))
            self.update_waveform_bg()
    def load_b(self, p=None): 
        if p: self.engine.load_source_b(p); self.btn_b.configure(text=os.path.basename(p))
        else: self.load_generic(self.engine.load_source_b, self.btn_b)
    def load_c(self, p=None): 
        if p: self.engine.load_source_c(p); self.btn_c.configure(text=os.path.basename(p))
        else: self.load_generic(self.engine.load_source_c, self.btn_c)
    def load_d(self, p=None): 
        if p: self.engine.load_source_d(p); self.btn_d.configure(text=os.path.basename(p))
        else: self.load_generic(self.engine.load_source_d, self.btn_d)
        
    def on_drop(self, event, func):
        path = event.data
        if path.startswith('{') and path.endswith('}'): path = path[1:-1]
        try: func(path); self.lbl_status.configure(text=f"Loaded {os.path.basename(path)}")
        except Exception as e: messagebox.showerror("Err", str(e))

    def on_xy_click(self, e): self.set_xy(e)
    def on_xy_drag(self, e): 
        self.set_xy(e)
        if self.var_auto_morph.get():
            self.trigger_morph(False, True)
            
    def on_xy_release(self, e): 
        # Always trigger on release if not already triggering? Or just ensure final pos is morphed.
        # If auto_morph is Off, we definitely want to morph on release (if that was the intention).
        # Actually user usually expects drag to move point, release to morph if not realtime.
        self.trigger_morph(False, False)
    def set_xy(self, e):
        w = 200
        self.morph_x = max(0.0, min(1.0, e.x/w)); self.morph_y = max(0.0, min(1.0, e.y/w))
        self.update_xy_visuals(); self.cmb_shape.set("Static")
    def update_xy_visuals(self):
        w = 200
        self.canvas_xy.coords(self.xy_handle, self.morph_x*w-8, self.morph_y*w-8, self.morph_x*w+8, self.morph_y*w+8)

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
        self.btn_apply.configure(state="normal"); self.btn_preview.configure(state="normal"); self.btn_morph.configure(text="MORPH (G)", state="normal")
        self.lbl_status.configure(text="Morph Done.")
        if self.engine.generated_audio is not None:
             dur = len(self.engine.generated_audio)/self.engine.sr
             self.ax.set_xlabel(f"Time ({dur:.2f}s)"); self.canvas_chart.draw()
        if self.autoplay_morph: self.apply_pitch_thread()

    def apply_pitch_thread(self):
        if self.engine.generated_audio is None: return
        self.btn_apply.configure(state="disabled")
        threading.Thread(target=self.run_apply, daemon=True).start()

    def run_apply(self):
        try:
            self.engine.process_pipeline(
                self.pitch_curve_y,
                speed=self.sl_speed.get(),
                growl=self.sl_growl.get(), tone=self.sl_tone.get(),
                dist=self.sl_dist.get(),
                bit_depth=self.sl_bits.get(), bit_rate_div=self.sl_srdiv.get(),
                ring_freq=self.sl_ring_freq.get(), ring_mix=self.sl_ring_mix.get(),
                delay_time=self.sl_d_time.get(), delay_fb=self.sl_d_fb.get(), delay_mix=self.sl_d_mix.get(),
                reverb_mix=self.sl_reverb.get(),
                spacer_width=self.sl_spacer.get(),
                vol=self.sl_vol.get()
            )
            self.after(0, self.apply_done)
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("Err", str(e))); self.after(0, self.apply_done)
            
    def apply_done(self):
        self.btn_apply.configure(state="normal"); self.lbl_status.configure(text="Applied FX.")
        if self.autoplay_morph: self.play_preview(); self.autoplay_morph = False

    def chaos_action(self, e=None):
        # Randomize Parameters
        val = lambda mn, mx: random.uniform(mn, mx)
        
        # Morph XY
        self.morph_x = random.random()
        self.morph_y = random.random()
        self.update_xy_visuals()
        
        # Sliders
        self.sl_formant.set(val(0.7, 1.6))
        self.sl_breath.set(val(0, 0.4))
        self.sl_speed.set(val(0.8, 1.2))
        
        self.sl_growl.set(val(0, 0.4) if random.random()>0.5 else 0)
        self.sl_tone.set(val(-0.6, 0.6))
        self.sl_ring_mix.set(val(0, 0.25) if random.random()>0.7 else 0)
        self.sl_ring_freq.set(val(30, 400))
        
        self.sl_spacer.set(val(0.8, 1.2))
        self.sl_reverb.set(val(0, 0.3) if random.random()>0.3 else 0)
        
        # Time FX (Less frequent)
        if random.random() > 0.6:
            self.sl_d_mix.set(val(0.1, 0.35))
            self.sl_d_time.set(val(0.1, 0.6))
            self.sl_d_fb.set(val(0.1, 0.5))
        else: self.sl_d_mix.set(0)
        
        # Lofi (Less frequent)
        if random.random() > 0.7:
             self.sl_dist.set(val(0, 0.15))
             self.sl_bits.set(random.randint(8, 16))
        else: self.sl_dist.set(0); self.sl_bits.set(16)
        
        if self.engine.generated_audio is not None and self.btn_apply.cget("state") != "disabled":
             self.apply_pitch_thread()

    def quick_save(self, e=None):
        import time
        if self.engine.generated_audio is None: return
        
        ts = time.strftime("%Y%m%d_%H%M%S")
        fn = f"Snap_{ts}.wav"
        fp = os.path.join("Snapshots", fn)
        
        try:
            self.engine.save_output(fp)
            self.lbl_status.configure(text=f"Saved: {fn}")
            # Visual Flash
            orig_bg = self.btn_snap.cget("fg_color")
            self.btn_snap.configure(fg_color="white")
            self.after(100, lambda: self.btn_snap.configure(fg_color=orig_bg))
        except Exception as ex:
            messagebox.showerror("Error", str(ex))

    def play_preview(self):
         if self.engine.generated_audio is None: return
         if pygame.mixer.music.get_busy(): 
             pygame.mixer.music.stop()
             self.btn_preview.configure(text="▶ PLAY (Space)", fg_color="#43A047")
             self.update_meter_visual(0,0)
             return

         pygame.mixer.music.unload()
         t = self.engine.processed_audio if self.engine.processed_audio is not None else self.engine.generated_audio
         import soundfile as sf; sf.write("prev.wav", t, self.engine.sr)
         
         self.prepare_meter_data(t, self.engine.sr)
         
         pygame.mixer.music.load("prev.wav"); pygame.mixer.music.play()
         
         self.btn_preview.configure(text="■ STOP (Space)", fg_color="#C62828")
         self.is_animating=True
         self.anim_loop()
         self.meter_update_loop()
         
    def anim_loop(self):
        if not self.is_animating: return
        if not pygame.mixer.music.get_busy(): 
            self.is_animating=False
            self.btn_preview.configure(text="▶ PLAY (Space)", fg_color="#43A047")
            self.update_meter_visual(0,0)
            return

        # Restore Trajectory Visualization
        pos_ms = pygame.mixer.music.get_pos()
        # map ms to frame index roughly
        # frame_period in audio_engine is 5.0 ms
        if pos_ms >= 0 and self.engine.last_trajectory_x is not None:
             idx = int(pos_ms / 5.0) 
             if idx < len(self.engine.last_trajectory_x):
                 self.morph_x = self.engine.last_trajectory_x[idx]
                 self.morph_y = self.engine.last_trajectory_y[idx]
                 self.update_xy_visuals()

        self.after(30, self.anim_loop)

    def prepare_meter_data(self, audio, sr):
        try:
            fps = 30
            hop = int(sr / fps)
            if audio.ndim == 1:
                audio_l = audio
                audio_r = audio
            else:
                audio_l = audio[:, 0]
                audio_r = audio[:, 1]
            
            # --- Integrated Loudness (Approx LUFS as RMS dBFS) ---
            # Just global RMS for now
            g_rms_l = np.sqrt(np.mean(audio_l**2))
            g_rms_r = np.sqrt(np.mean(audio_r**2))
            g_avg = (g_rms_l + g_rms_r) / 2
            self.lufs_val = 20 * np.log10(g_avg + 1e-9)
            
            # --- Envelope for Animation ---
            n_frames = len(audio_l) // hop
            if n_frames == 0: 
                self.meter_envelope = None
                return

            # Optimized RMS block calc
            end_idx = n_frames * hop
            l_sq = audio_l[:end_idx].reshape(-1, hop) ** 2
            r_sq = audio_r[:end_idx].reshape(-1, hop) ** 2
            
            rms_l = np.sqrt(np.mean(l_sq, axis=1))
            rms_r = np.sqrt(np.mean(r_sq, axis=1))
            
            # Convert to dB immediately for easier plotting? 
            # Or keep linear 0-1 for processing? 
            # Let's keep linear amplitude 0-1 here, convert in visualizer for smoothness or log scale there.
            
            self.meter_envelope = np.column_stack((rms_l, rms_r))
            self.meter_fps = fps
        except:
            self.meter_envelope = None
            self.lufs_val = -100

    def meter_update_loop(self):
        if not pygame.mixer.music.get_busy(): 
            self.update_meter_visual(0, 0)
            return

        t_ms = pygame.mixer.music.get_pos()
        if t_ms < 0: t_ms = 0
        
        l, r = 0, 0
        if self.meter_envelope is not None:
            frame = int((t_ms / 1000.0) * self.meter_fps)
            if frame < len(self.meter_envelope):
                l = self.meter_envelope[frame][0]
                r = self.meter_envelope[frame][1]
            
        self.update_meter_visual(l, r)
        self.after(30, self.meter_update_loop)

    def _init_level_meter(self):
        # Header
        ctk.CTkLabel(self.col_meter, text="LEVEL", font=("Roboto", 10, "bold")).pack(pady=(5,0))
        
        # Readouts
        self.lbl_peak_val = ctk.CTkLabel(self.col_meter, text="-inf", font=("Consolas", 10), text_color="#ccc")
        self.lbl_peak_val.pack(pady=0)
        ctk.CTkLabel(self.col_meter, text="dB", font=("Roboto", 8), text_color="#666").pack(pady=0)
        
        # Canvas
        # Canvas
        total_w = self.meter_margin*2 + self.meter_bar_width*2 + self.meter_gap
        self.cv_meter = ctk.CTkCanvas(self.col_meter, width=total_w, bg="#000", highlightthickness=0)
        self.cv_meter.pack(fill="y", expand=True, padx=2, pady=5)
        
        # LUFS Label Bottom
        ctk.CTkLabel(self.col_meter, text="LUFS", font=("Roboto", 8), text_color="#666").pack(pady=(5,0))
        self.lbl_lufs_val = ctk.CTkLabel(self.col_meter, text="--", font=("Consolas", 10), text_color="#ccc")
        self.lbl_lufs_val.pack(pady=(0,10))
        
        self.cv_meter.update()
        h = self.cv_meter.winfo_height()
        if h < 100: h = 600
        self.meter_h = h
        
        # BG Lines (dB scale markings approx)
        # 0dB, -6, -12, -24, -48
        # We'll calculate positions dynamically in update if needed, but static lines are fine.
        
        # Bars
        x_l1 = self.meter_margin
        x_l2 = x_l1 + self.meter_bar_width
        x_r1 = x_l2 + self.meter_gap
        x_r2 = x_r1 + self.meter_bar_width
        
        # L ch (Left bar)
        self.id_l = self.cv_meter.create_rectangle(x_l1, h, x_l2, h, fill="#4CAF50", outline="")
        # R ch (Right bar)
        self.id_r = self.cv_meter.create_rectangle(x_r1, h, x_r2, h, fill="#4CAF50", outline="")
        
        # Bind resize
        def on_resize(e):
            self.meter_h = e.height
            self.update_meter_visual(0,0, reset=True)
        self.cv_meter.bind("<Configure>", on_resize)
        
    def update_meter_visual(self, l_amp, r_amp, reset=False):
        h = self.meter_h
        
        # Convert amp to dB for height calculation
        # Range: -60dB to 0dB mapping to height
        def amp_to_db(a):
            if a <= 0.001: return -100
            return 20 * np.log10(a)
            
        def db_to_y(db):
            # Scale -60..0 to h..0
            if db < -60: return h
            if db > 0: return 0
            ratio = (db - (-60)) / 60.0
            return h - (ratio * h)

        db_l = amp_to_db(l_amp)
        db_r = amp_to_db(r_amp)
        
        ym_l = db_to_y(db_l)
        ym_r = db_to_y(db_r)
        
        # Color based on dB
        # > -1.0 Red, > -6.0 Yellow, else Green
        def get_col(db):
            if db > -1.0: return "#E53935"
            if db > -6.0: return "#FFEB3B"
            return "#4CAF50"
            
        col_l = get_col(db_l)
        col_r = get_col(db_r)
        
        x_l1 = self.meter_margin
        x_l2 = x_l1 + self.meter_bar_width
        x_r1 = x_l2 + self.meter_gap
        x_r2 = x_r1 + self.meter_bar_width
        
        self.cv_meter.coords(self.id_l, x_l1, ym_l, x_l2, h)
        self.cv_meter.coords(self.id_r, x_r1, ym_r, x_r2, h)
        self.cv_meter.itemconfig(self.id_l, fill=col_l)
        self.cv_meter.itemconfig(self.id_r, fill=col_r)
        
        # Text Updates
        if reset:
             self.lbl_peak_val.configure(text="-inf")
             self.lbl_lufs_val.configure(text="--")
        else:
             peak_db = max(db_l, db_r)
             txt = f"{peak_db:+.1f}" if peak_db > -90 else "-inf"
             self.lbl_peak_val.configure(text=txt)
             
             if hasattr(self, 'lufs_val'):
                 self.lbl_lufs_val.configure(text=f"{self.lufs_val:+.1f}")
         

        
    def toggle_playback(self, e=None):
        if self.btn_preview.cget("state") == "disabled": return
        self.play_preview()

    def sel_outdir(self):
        d=filedialog.askdirectory(); 
        if d: self.outdir=d
    def open_outdir(self):
        try: os.startfile(self.outdir)
        except: pass

    def save_file(self):
         p=filedialog.asksaveasfilename(defaultextension=".wav",filetypes=[("WAV","*.wav")]); 
         if p: self.engine.save_output(p)

    def run_batch(self):
        if self.is_batch_running: return
        if self.engine.y_a is None: messagebox.showwarning("Err","No Master A"); return
        try: cnt=int(self.b_cnt.get())
        except: return
        
        self.is_batch_running=True; self.btn_batch.configure(state="disabled")
        threading.Thread(target=self.batch_worker, args=(cnt, self.b_pre.get()), daemon=True).start()

    def batch_worker(self, cnt, pre):
        shapes = ["Circle", "Eight", "Scan", "RandomMovement", "RandomPoint", "Static"]
        
        def r(key):
            try:
                mn = float(self.batch_ranges[key][0].get())
                mx = float(self.batch_ranges[key][1].get())
                return random.uniform(mn, mx) if mn != mx else mn
            except: return 0.0
            
        for i in range(cnt):
            self.after(0, lambda v=(i+1)/cnt: self.prog_batch.set(v))
            self.after(0, lambda c=i+1: self.lbl_status.configure(text=f"Batch {c}/{cnt}..."))
            
            x = r("morph_x"); y = r("morph_y")
            shape = shapes[random.randint(0,4)] if random.random() > 0.5 else "Static"
            
            p_curve = np.zeros(100)
            
            # Use Random point logic if shape is RandomPoint
            if shape == "RandomPoint":
                x = random.random(); y = random.random()

            self.engine.render_batch_sample(
                os.path.join(self.outdir, f"{pre}_{i+1:03d}.wav"),
                x, y, shape, r("mspeed"),
                r("formant"), r("breath"), p_curve,
                r("speed"), r("growl"), r("tone"), r("dist"),
                r("bits"), r("srdiv"), r("ring_freq"), r("ring_mix"),
                r("d_time"), r("d_fb"), r("d_mix"), r("reverb"), r("spacer"),
                r("vol")
            )
            
        self.is_batch_running = False
        self.after(0, lambda: self.btn_batch.configure(state="normal", text="🚀 RUN BATCH"))

    # --- CHART ---
    def update_waveform_bg(self):
        # Optimized waveform visualization
        try:
            raw = self.engine.sources[0]
            if raw is None: 
                self.cached_wave = None
                self.wave_line.set_data([], [])
            else:
                # Downsample for speed
                step = max(1, len(raw) // 1000)
                small = raw[::step]
                if small.ndim > 1: small = np.mean(small, axis=1) # Mono mix
                
                # Create X axis (0-100)
                x = np.linspace(0, 100, len(small))
                
                # Normalize peak to 0.9 for visual
                mx = np.max(np.abs(small))
                if mx > 0.001: small = small / mx 
                
                self.cached_wave = (x, small)
            
            self.draw_waveform_on_chart()
        except Exception as e: print(e)

    def draw_waveform_on_chart(self):
        if self.cached_wave is None: return
        x, y = self.cached_wave
        # Scale Y to fill the current pitch range visual
        # Pitch range is +/- self.pitch_range
        # We want waveform to fill e.g. 80% of height
        
        y_scaled = y * (self.pitch_range * 0.9)
        self.wave_line.set_data(x, y_scaled)
        self.canvas_chart.draw_idle()

    def update_pitch_range_ui(self, e=None):
        txt = self.ent_prange.get().strip()
        v = self.pitch_range
        
        if not txt:
            # If empty, revert to currently stored valid range or default
            v = self.pitch_range
        else:
            try:
                v = float(txt)
                v = max(1.0, min(60.0, v)) # Clamp 1 ~ 60
                self.pitch_range = v
            except: 
                v = self.pitch_range

        # Refill entry with validated value
        current_display = self.ent_prange.get()
        new_display = str(int(v)) if v.is_integer() else str(v)
        
        # Only update if different to avoid cursor jumping if user is typing valid chars (though return/focusout handles this)
        # Since this is bound to Return/FocusOut, we can force update.
        if current_display != new_display:
            self.ent_prange.delete(0, tk.END)
            self.ent_prange.insert(0, new_display)

        self.update_spline_curve()
        self.draw_waveform_on_chart() # Re-scale background
        
    def update_spline_curve(self):
        self.pitch_points.sort(key=lambda p: p[0])
        px = [p[0] for p in self.pitch_points]; py = [p[1] for p in self.pitch_points]
        
        # Update Axis
        rng = self.pitch_range
        self.ax.set_ylim(-rng, rng)
        self.point_scatter.set_data(px, py)
        
        if len(self.pitch_points) >= 2:
            try:
                # Pchip is monotonic, prevents overshoot
                cs = PchipInterpolator(px, py)
                xs = np.linspace(0, 100, 100); ys = cs(xs)
                self.pitch_curve_y = np.clip(ys, -rng, rng)
                self.line.set_data(xs, self.pitch_curve_y)
            except: pass
        else: self.line.set_data([], [])
        self.canvas_chart.draw_idle()

    def on_chart_click(self, e): 
        if e.inaxes != self.ax: return
        min_d = 999; closest = -1
        # Scale handling for hit detection?
        # Just maintain simple pixel like ratio logic
        yr = self.pitch_range * 2.0
        
        for i, p in enumerate(self.pitch_points):
            dx = abs(p[0] - e.xdata)
            dy = abs(p[1] - e.ydata) * (100.0 / yr) # rough normalize weight
            d = dx + dy
            if d < min_d: min_d = d; closest = i
        if e.button == 3:
            if closest != -1: self.pitch_points.pop(closest); self.update_spline_curve(); self.debounce_apply()
            return
        if closest != -1 and min_d < 6: self.drag_point_idx = closest
        else: self.pitch_points.append([e.xdata, e.ydata]); self.drag_point_idx = len(self.pitch_points) - 1
        self.update_spline_curve(); self.debounce_apply()

    def on_chart_drag(self, e): 
        if self.drag_point_idx is not None and e.xdata is not None:
             rng = self.pitch_range
             self.pitch_points[self.drag_point_idx] = [np.clip(e.xdata, 0, 100), np.clip(e.ydata, -rng, rng)]
             self.update_spline_curve()

    def on_chart_release(self, e): 
        self.drag_point_idx = None
        self.debounce_apply()
    def reset_pitch_curve_action(self):
         self.pitch_points = [[0, 0], [100, 0]]
         self.update_spline_curve()

    # --- STATE ---
    def get_state(self):
        s = {
            "sliders": {
                "formant": self.sl_formant.get(), "breath": self.sl_breath.get(),
                "speed": self.sl_speed.get(), "vol": self.sl_vol.get(),
                "growl": self.sl_growl.get(), "tone": self.sl_tone.get(),
                "ring_mix": self.sl_ring_mix.get(), "ring_freq": self.sl_ring_freq.get(),
                "spacer": self.sl_spacer.get(), "reverb": self.sl_reverb.get(),
                "d_time": self.sl_d_time.get(), "d_fb": self.sl_d_fb.get(), "d_mix": self.sl_d_mix.get(),
                "dist": self.sl_dist.get(), "bits": self.sl_bits.get(), "srdiv": self.sl_srdiv.get(),
                "mspeed": self.slider_mspeed.get()
            },
            "batch": {k: (v[0].get(), v[1].get()) for k,v in self.batch_ranges.items()}
        }
        s["morph"] = {"x":self.morph_x, "y":self.morph_y, "shape":self.cmb_shape.get()}
        s["pitch"] = self.pitch_points
        s["pitch_range"] = self.pitch_range
        return s

    def set_state(self, s):
        try:
            sl = s.get("sliders", {})
            self.sl_formant.set(sl.get("formant",1)); self.sl_breath.set(sl.get("breath",0))
            self.sl_speed.set(sl.get("speed",1)); self.sl_vol.set(sl.get("vol",1))
            self.sl_growl.set(sl.get("growl",0)); self.sl_tone.set(sl.get("tone",0))
            self.sl_ring_mix.set(sl.get("ring_mix",0)); self.sl_ring_freq.set(sl.get("ring_freq",30))
            self.sl_spacer.set(sl.get("spacer",1)); self.sl_reverb.set(sl.get("reverb",0))
            self.sl_d_time.set(sl.get("d_time",0.2)); self.sl_d_fb.set(sl.get("d_fb",0)); self.sl_d_mix.set(sl.get("d_mix",0))
            self.sl_dist.set(sl.get("dist",0)); self.sl_bits.set(sl.get("bits",16)); self.sl_srdiv.set(sl.get("srdiv",1))
            self.slider_mspeed.set(sl.get("mspeed",1))
            
            b = s.get("batch", {})
            for k, val in b.items():
                if k in self.batch_ranges:
                     # Check if widgets exist before accessing (safety)
                    if self.batch_ranges[k][0].winfo_exists():
                        self.batch_ranges[k][0].delete(0,tk.END); self.batch_ranges[k][0].insert(0, str(val[0]))
                        self.batch_ranges[k][1].delete(0,tk.END); self.batch_ranges[k][1].insert(0, str(val[1]))
            
            m = s.get("morph", {})
            self.morph_x = m.get("x",0.5); self.morph_y = m.get("y",0.5)
            self.cmb_shape.set(m.get("shape","Static")); self.update_xy_visuals()
            
            self.pitch_points = s.get("pitch", [[0,0],[100,0]])
            
            pr = s.get("pitch_range", 6.0)
            self.ent_prange.delete(0, tk.END); self.ent_prange.insert(0, str(pr))
            self.update_pitch_range_ui() # this sets self.pitch_range and redraws curve
            
        except Exception as e: print(e)

    def save_settings(self):
        d = os.path.join(os.getcwd(), "Settings")
        p = filedialog.asksaveasfilename(initialdir=d, defaultextension=".json", filetypes=[("JSON Config", "*.json")])
        if p:
            try:
                with open(p, "w") as f: json.dump(self.get_state(), f, indent=4)
                messagebox.showinfo("Success", "Saved")
            except Exception as e: messagebox.showerror("Err", str(e))

    def load_settings(self):
        d = os.path.join(os.getcwd(), "Settings")
        p = filedialog.askopenfilename(initialdir=d, filetypes=[("JSON Config", "*.json")])
        if p:
            try:
                with open(p, "r") as f: self.set_state(json.load(f))
                messagebox.showinfo("Success", "Loaded")
            except Exception as e: messagebox.showerror("Err", str(e))

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
