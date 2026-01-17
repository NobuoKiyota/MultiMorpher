import customtkinter as ctk
import tkinter as tk
import math
import numpy as np

def adjust_brightness(hex_color, factor):
    # hex_color: "#RRGGBB"
    if not hex_color.startswith("#") or len(hex_color) != 7: return hex_color
    r = int(hex_color[1:3], 16)
    g = int(hex_color[3:5], 16)
    b = int(hex_color[5:7], 16)
    
    r = min(255, int(r * factor))
    g = min(255, int(g * factor))
    b = min(255, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"

class RotaryKnob(ctk.CTkFrame):
    def __init__(self, master, width=60, height=80, from_=0, to=100, command=None, hover_command=None, text="Knob", start_val=0, 
                 progress_color="#00e5ff", track_color="#111111", show_value=False, param_id=None, focus_callback=None, **kwargs):
        super().__init__(master, width=width, height=height, fg_color="transparent", **kwargs)
        
        self.min_val = from_
        self.max_val = to
        self.value = start_val
        self.command = command
        self.hover_command = hover_command
        self.text = text
        self.base_progress_color = progress_color
        self.track_color = track_color
        self.show_value = show_value
        self.param_id = param_id
        self.focus_callback = focus_callback
        
        self.click_y = 0
        self.senstivity = 0.01
        
        # UI
        self.canvas = tk.Canvas(self, width=40, height=40, bg="#23262b", highlightthickness=0)
        self.canvas.pack(pady=2)
        
        if self.show_value:
            self.lbl_val = ctk.CTkLabel(self, text=f"{self.value:.2f}", font=("Arial", 9), text_color="#aaaaaa")
            self.lbl_val.pack()
        
        self.lbl_text = ctk.CTkLabel(self, text=self.text, font=("Arial", 10, "bold"), text_color="#eeeeee")
        self.lbl_text.pack()
        
        self.update_knob()
        
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<MouseWheel>", self.on_scroll)
        
        self.canvas.bind("<Enter>", self.on_enter)
        self.canvas.bind("<Leave>", self.on_leave)
        
    def update_knob(self):
        self.canvas.delete("all")
        w = 40
        h = 40
        cx, cy = w/2, h/2
        r = 16
        
        # Ranges
        start_angle = 240
        max_extent = -300
        
        # Norm
        if self.max_val == self.min_val: norm = 0.0
        else: norm = (self.value - self.min_val) / (self.max_val - self.min_val)
        norm = max(0.0, min(1.0, norm))
        
        current_extent = max_extent * norm
        
        # Dynamic Color: 50% brightness at 0, 100% at 1 (or 100% -> 150%?)
        # Let's say darker at low values.
        # factor: 0.4 + 0.6 * norm
        factor = 0.4 + 0.8 * norm
        # Assuming base color is bright.
        display_color = adjust_brightness(self.base_progress_color, factor)

        # 1. Track (Background Arc)
        self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start_angle, extent=max_extent, 
                               style="arc", width=5, outline=self.track_color)
        
        # 2. Progress (Foreground Arc)
        self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start_angle, extent=current_extent, 
                               style="arc", width=5, outline=display_color)
        
        # 3. Indicator Line (Needle)
        angle_deg = start_angle + current_extent
        angle_rad = math.radians(angle_deg)
        
        r_out = r
        mx = cx + r_out * math.cos(angle_rad)
        my = cy - r_out * math.sin(angle_rad) # y inverted
        
        self.canvas.create_line(cx, cy, mx, my, fill="#ffffff", width=2)
        
        if self.show_value:
            self.lbl_val.configure(text=f"{self.value:.2f}")

    def set(self, val):
        self.value = max(self.min_val, min(self.max_val, val))
        self.update_knob()
        if self.hover_command and self.mouse_in:  # Update display if hovering/dragging
             self.hover_command(self.text, self.value)
        
    def get(self):
        return self.value
        
    def on_click(self, event):
        self.click_y = event.y
        self.mouse_in = True
        if self.focus_callback and self.param_id:
            self.focus_callback(self.param_id)
        
    def on_drag(self, event):
        dy = self.click_y - event.y
        self.click_y = event.y
        rng = self.max_val - self.min_val
        step = rng * self.senstivity * 0.5
        if abs(dy) > 0:
            change = step * dy
            self.set(self.value + change)
            if self.command: self.command(self.value)
                
    def on_scroll(self, event):
        delta = event.delta / 120.0
        rng = self.max_val - self.min_val
        step = rng * 0.05
        self.set(self.value + step * delta)
        if self.command: self.command(self.value)

    # Hover
    mouse_in = False
    def on_enter(self, event):
        self.mouse_in = True
        if self.hover_command: self.hover_command(self.text, self.value)
        
    def on_leave(self, event):
        self.mouse_in = False
        if self.hover_command: self.hover_command("", None)

class EnvelopeEditor(ctk.CTkFrame):
    def __init__(self, master, width=300, height=150, callback=None, 
                 bg_color="#23262b", line_color="#00e5ff", fill_color="#1a4c54", **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        
        self.callback = callback
        
        self.canvas_bg = bg_color
        self.line_color = line_color
        self.fill_color = fill_color # Darker shade of line
        self.handle_color = "#ffffff"
        self.handle_r = 5
        
        # Canvas
        self.canvas = tk.Canvas(self, width=width, height=height, bg=self.canvas_bg, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Params
        self.p_attack = 0.5
        self.p_decay = 0.5
        self.p_sustain = 0.7
        self.p_release = 1.0
        
        self.drag_item = None
        self.scale_x = 40.0 
        
        self.update_drawing()
        
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
    def _to_canvas_coords(self, t, lvl):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10: w = 300
        if h < 10: h = 150
        
        margin_x = 10
        margin_y = 10
        draw_h = h - margin_y * 2
        
        x = margin_x + t * self.scale_x
        y = h - margin_y - (lvl * draw_h)
        return x, y

    def _from_canvas_coords(self, x, y):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10: w = 300
        if h < 10: h = 150
        
        margin_x = 10
        margin_y = 10
        draw_h = h - margin_y * 2
        
        t = (x - margin_x) / self.scale_x
        if t < 0: t = 0
        
        lvl = (h - margin_y - y) / draw_h
        if lvl < 0: lvl = 0.0
        if lvl > 1: lvl = 1.0
        return t, lvl

    def update_drawing(self):
        self.canvas.delete("all")
        
        # Points
        t0, l0 = 0.0, 0.0
        t1, l1 = self.p_attack, 1.0
        t2, l2 = t1 + self.p_decay, self.p_sustain
        t3, l3 = t2 + self.p_release, 0.0
        
        x0, y0 = self._to_canvas_coords(t0, l0)
        x1, y1 = self._to_canvas_coords(t1, l1)
        x2, y2 = self._to_canvas_coords(t2, l2)
        x3, y3 = self._to_canvas_coords(t3, l3)
        
        # Polygon points
        points = [
            x0, y0, # Start (0,0)
            x1, y1, # Attack Peak
            x2, y2, # Sustain
            x3, y3, # Release End (0)
            x3, self.canvas.winfo_height(), # Straight down from release end
            x0, self.canvas.winfo_height()  # Straight down from start
        ]
        
        self.canvas.create_polygon(points, fill=self.fill_color, outline="")
        
        # Outline Line
        self.canvas.create_line(x0, y0, x1, y1, fill=self.line_color, width=2)
        self.canvas.create_line(x1, y1, x2, y2, fill=self.line_color, width=2)
        self.canvas.create_line(x2, y2, x3, y3, fill=self.line_color, width=2, dash=(4, 2))
        
        # Handles
        r = self.handle_r
        for x, y, tag in [(x1,y1,"h1"), (x2,y2,"h2"), (x3,y3,"h3")]:
            self.canvas.create_oval(x-r, y-r, x+r, y+r, fill=self.handle_color, tags=tag)
            
        # Text
        self.canvas.create_text(x1, y1-15, text=f"A:{self.p_attack:.2f}", fill="#aaaaaa", font=("Arial", 9))
        self.canvas.create_text(x2, y2-15, text=f"D:{self.p_decay:.2f}/S:{self.p_sustain:.2f}", fill="#aaaaaa", font=("Arial", 9))
        self.canvas.create_text(x3, y3-15, text=f"R:{self.p_release:.2f}", fill="#aaaaaa", font=("Arial", 9))

    def on_click(self, event):
        x, y = event.x, event.y
        pts = [
            (self.p_attack, 1.0, "h1"),
            (self.p_attack + self.p_decay, self.p_sustain, "h2"),
            (self.p_attack + self.p_decay + self.p_release, 0.0, "h3")
        ]
        closest_tag = None
        min_dist = 20
        for t_val, l_val, tag in pts:
            cx, cy = self._to_canvas_coords(t_val, l_val)
            dist = ((cx - x)**2 + (cy - y)**2)**0.5
            if dist < min_dist:
                min_dist = dist
                closest_tag = tag
        self.drag_item = closest_tag

    def on_drag(self, event):
        if not self.drag_item: return
        x, y = event.x, event.y
        t, lvl = self._from_canvas_coords(x, y)
        
        if self.drag_item == "h1":
            self.p_attack = max(0.01, t)
        elif self.drag_item == "h2":
            decay_cand = t - self.p_attack
            self.p_decay = max(0.01, decay_cand)
            self.p_sustain = lvl
        elif self.drag_item == "h3":
            base_t = self.p_attack + self.p_decay
            release_cand = t - base_t
            self.p_release = max(0.01, release_cand)
            
        self.update_drawing()
        self.trigger_callback()

    def on_release(self, event):
        self.drag_item = None
        self.trigger_callback()

    def trigger_callback(self):
        if self.callback:
            self.callback(self.p_attack, self.p_decay, self.p_sustain, self.p_release)
            
    def set_params(self, a, d, s, r):
        self.p_attack, self.p_decay, self.p_sustain, self.p_release = a, d, s, r
        self.update_drawing()

    def get_params(self):
        return self.p_attack, self.p_decay, self.p_sustain, self.p_release

class VirtualKeyboard(ctk.CTkFrame):
    def __init__(self, master, start_note=36, num_keys=24, callback_on=None, callback_off=None, **kwargs):
        super().__init__(master, **kwargs)
        self.start_note = start_note 
        self.num_keys = num_keys
        self.callback_on = callback_on
        self.callback_off = callback_off
        self.canvas = tk.Canvas(self, height=80, bg="#111111", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.white_key_width = 30
        self.black_key_width = 18
        self.black_key_height = 50
        self.draw_keys()
        self.pressed_note = None
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.key_rects = {}

    def draw_keys(self):
        self.canvas.delete("all")
        self.key_rects = {}
        wk_x = 0
        # Draw Whites
        for i in range(self.num_keys):
            note = self.start_note + i
            is_black = (note % 12) in [1, 3, 6, 8, 10]
            if not is_black:
                tag = f"key_{note}"
                self.canvas.create_rectangle(wk_x, 0, wk_x+self.white_key_width, 80, fill="white", outline="black", tags=tag)
                self.key_rects[note] = {"tag":tag, "type":"white"}
                wk_x += self.white_key_width
        # Draw Blacks
        total_w = wk_x
        self.canvas.configure(width=total_w)
        wk_idx = 0
        for i in range(self.num_keys):
            note = self.start_note + i
            is_black = (note % 12) in [1, 3, 6, 8, 10]
            if is_black:
                x = (wk_idx * self.white_key_width) - (self.black_key_width/2)
                tag = f"key_{note}"
                self.canvas.create_rectangle(x, 0, x+self.black_key_width, self.black_key_height, fill="black", outline="black", tags=tag)
                self.key_rects[note] = {"tag":tag, "type":"black"}
            else: wk_idx += 1

    def get_note_at(self, x, y):
        # Top-most check (Blacks)
        for note, info in self.key_rects.items():
            if info["type"] == "black":
                bbox = self.canvas.bbox(info["tag"])
                if bbox and bbox[0]<=x<=bbox[2] and bbox[1]<=y<=bbox[3]: return note
        # Then whites
        for note, info in self.key_rects.items():
            if info["type"] == "white":
                bbox = self.canvas.bbox(info["tag"])
                if bbox and bbox[0]<=x<=bbox[2] and bbox[1]<=y<=bbox[3]: return note
        return None

    def on_press(self, event):
        note = self.get_note_at(event.x, event.y)
        if note: self.trigger_on(note)
    def on_drag(self, event):
        note = self.get_note_at(event.x, event.y)
        if note and note != self.pressed_note:
            self.trigger_off(self.pressed_note)
            self.trigger_on(note)
    def on_release(self, event):
        if self.pressed_note: self.trigger_off(self.pressed_note)

    def trigger_on(self, note):
        if self.pressed_note == note: return
        self.pressed_note = note
        info = self.key_rects.get(note)
        if info:
            c = "#dddddd" if info["type"]=="white" else "#333333"
            self.canvas.itemconfig(info["tag"], fill=c)
        if self.callback_on: self.callback_on(note)

    def trigger_off(self, note):
        if note is None: return
        info = self.key_rects.get(note)
        if info:
            c = "white" if info["type"]=="white" else "black"
            self.canvas.itemconfig(info["tag"], fill=c)
        if self.callback_off: self.callback_off(note)
        if self.pressed_note == note: self.pressed_note = None

class AutomationEditor(ctk.CTkFrame):
    def __init__(self, master, width=250, height=400, update_callback=None, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self.update_callback = update_callback # fn(points, duration)
        
        self.current_param_id = None
        self.points = [(0.0, 0.0), (1.0, 0.0)]
        self.duration = 4.0
        
        # Colors
        self.bg_color = "#23262b"
        self.line_color = "#e67e22" # Orange
        self.handle_color = "#ffffff"
        
        # Header
        self.header = ctk.CTkFrame(self, fg_color="transparent")
        self.header.pack(fill="x", padx=5, pady=5)
        self.lbl_title = ctk.CTkLabel(self.header, text="Automation", font=("Arial", 12, "bold"), text_color=self.line_color)
        self.lbl_title.pack(side="left")
        
        # Duration Knob
        self.knob_dur = RotaryKnob(self.header, text="Time", from_=0.1, to=16.0, start_val=4.0, 
                                   command=self.on_dur_change, width=50, height=60, 
                                   progress_color=self.line_color, show_value=False)
        self.knob_dur.pack(side="right")
        
        # Canvas
        self.canvas = tk.Canvas(self, bg=self.bg_color, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<Double-Button-1>", self.on_dclick)
        
        self.drag_idx = None
        self.draw()

    def set_target(self, param_id, param_name, points, duration):
        self.current_param_id = param_id
        self.lbl_title.configure(text=f"Auto: {param_name}")
        self.points = sorted(points, key=lambda x: x[0])
        self.duration = duration
        self.knob_dur.set(duration)
        self.draw()

    def on_dur_change(self, val):
        self.duration = val
        self.trigger_update()

    def draw(self):
        self.canvas.delete("all")
        w = max(10, self.canvas.winfo_width())
        h = max(10, self.canvas.winfo_height())
        
        # Grid
        self.canvas.create_line(0, h/2, w, h/2, fill="#333", dash=(2,2))
        self.canvas.create_line(w/4, 0, w/4, h, fill="#333", dash=(2,2))
        self.canvas.create_line(w/2, 0, w/2, h, fill="#333", dash=(2,2))
        self.canvas.create_line(3*w/4, 0, 3*w/4, h, fill="#333", dash=(2,2))
        
        # Points -> Coords
        coords = []
        for t, v in self.points:
            cx = t * w
            cy = h/2 - (v * (h/2 - 10)) 
            coords.append((cx, cy))
            
        # Draw Line
        if len(coords) > 1:
            self.canvas.create_line(coords, fill=self.line_color, width=2)
            
        # Draw Points
        r = 4
        for i, (cx, cy) in enumerate(coords):
            tag = f"p_{i}"
            col = self.handle_color
            if i == 0 or i == len(coords)-1: col = "#888" # Lock ends
            self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=col, tags=tag)

    def _to_logic(self, x, y):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        t = x / w
        t = max(0.0, min(1.0, t))
        
        v = (h/2 - y) / (h/2 - 10)
        v = max(-1.0, min(1.0, v))
        return t, v

    def on_click(self, event):
        if not self.current_param_id: return
        x, y = event.x, event.y
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        min_dist = 10
        hit = -1
        
        for i, (t, v) in enumerate(self.points):
            cx = t * w
            cy = h/2 - (v * (h/2 - 10))
            dist = ((cx-x)**2 + (cy-y)**2)**0.5
            if dist < min_dist:
                min_dist = dist
                hit = i
        
        if hit != -1:
            self.drag_idx = hit
        else:
            t, v = self._to_logic(x, y)
            self.points.append((t, v))
            self.points.sort(key=lambda p: p[0])
            self.draw()
            self.trigger_update()
            
    def on_drag(self, event):
        if self.drag_idx is None: return
        t, v = self._to_logic(event.x, event.y)
        
        if self.drag_idx == 0: t = 0.0
        if self.drag_idx == len(self.points) - 1: t = 1.0
        
        if 0 < self.drag_idx < len(self.points) - 1:
            prev_t = self.points[self.drag_idx-1][0]
            next_t = self.points[self.drag_idx+1][0]
            t = max(prev_t + 0.01, min(next_t - 0.01, t))
            
        self.points[self.drag_idx] = (t, v)
        self.draw()
        self.trigger_update()

    def on_dclick(self, event):
        if self.drag_idx is not None:
             if 0 < self.drag_idx < len(self.points) - 1:
                 del self.points[self.drag_idx]
                 self.drag_idx = None
                 self.draw()
                 self.trigger_update()

    def on_release(self, event):
        self.drag_idx = None

    def trigger_update(self):
        if self.update_callback and self.current_param_id:
            self.update_callback(self.current_param_id, self.points, self.duration)

class LevelMeter(ctk.CTkFrame):
    def __init__(self, master, width=30, height=300, **kwargs):
        super().__init__(master, width=width, height=height, **kwargs)
        self.canvas = tk.Canvas(self, width=width, height=height, bg="#111111", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.peak = 0.0
        
        self.lbl_val = ctk.CTkLabel(self, text="-inf dB", font=("Arial", 9), text_color="#aaaaaa")
        self.lbl_val.place(relx=0.5, rely=0.05, anchor="center")

    def update_meter(self, stereo_block):
        # stereo_block: numpy array (samples)
        if len(stereo_block) == 0: return

        # Calc Peak (L+R average or max)
        # stereo_block is interleaved if from pyaudio? Or usually from engine it's flat float32 array
        # Engine calculate_block returns flat array. Stereo is reshaped later.
        # But we pass data to update_meter.
        
        # Simple Peak
        peak = np.max(np.abs(stereo_block))
        
        # Check against previous to smooth decay?
        self.peak = max(peak, self.peak * 0.9) # Simple falloff

        self.draw()

    def draw(self):
        self.canvas.delete("all")
        w = max(10, self.canvas.winfo_width())
        h = max(10, self.canvas.winfo_height())
        
        # DB Calculation
        db = 20 * math.log10(max(1e-9, self.peak))
        self.lbl_val.configure(text=f"{db:.1f} dB")
        
        # Map peak 0..1 to height
        # Use log scale visually? Linear for now.
        val = self.peak
        val = max(0, min(1, val))
        
        meter_h = h * val
        
        # Gradient colors?
        # Draw segments
        # Green (-inf to -12), Yellow (-12 to -3), Red (-3 to 0)
        
        # Simple single bar with color change at top
        c = "#00ff00"
        if val > 0.7: c = "#ffff00" # approx -3dB linear is 0.707
        if val > 0.9: c = "#ff0000"
        
        self.canvas.create_rectangle(0, h-meter_h, w, h, fill=c, outline="")
        
        # Draw some ticks
        for db_tick, col in [(-3, "#555"), (-6, "#555"), (-12, "#555"), (-24, "#555")]:
            lin = 10**(db_tick/20)
            y = h - (lin * h)
            self.canvas.create_line(0, y, w, y, fill=col)
