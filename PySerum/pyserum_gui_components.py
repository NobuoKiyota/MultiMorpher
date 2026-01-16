import customtkinter as ctk
import tkinter as tk
import math

class RotaryKnob(ctk.CTkFrame):
    def __init__(self, master, width=60, height=80, from_=0, to=100, command=None, text="Knob", start_val=0, 
                 progress_color="#00e5ff", track_color="#111111", **kwargs):
        super().__init__(master, width=width, height=height, fg_color="transparent", **kwargs)
        
        self.min_val = from_
        self.max_val = to
        self.value = start_val
        self.command = command
        self.text = text
        self.progress_color = progress_color
        self.track_color = track_color
        
        self.click_y = 0
        self.senstivity = 0.01
        
        # UI
        self.canvas = tk.Canvas(self, width=40, height=40, bg=track_color, highlightthickness=0)
        # However, canvas bg should transparent/frame color? 
        # Standard Tk canvas doesn't support transparent bg easily on Windows without tricks.
        # But our panel color is #23262b. Let's set canvas bg to match parent or just generic dark?
        # User specified "Knob Track: #111111". That is the Arc line.
        # The rect itself should probably match the panel.
        # Defaulting simple black/dark grey for now, handled by parent usually but here we hardcode or pass?
        # Let's use a safe dark color close to panel.
        self.canvas.configure(bg="#23262b") 
        self.canvas.pack(pady=2)
        
        self.lbl_val = ctk.CTkLabel(self, text=f"{self.value:.2f}", font=("Arial", 9), text_color="#aaaaaa")
        self.lbl_val.pack()
        
        self.lbl_text = ctk.CTkLabel(self, text=self.text, font=("Arial", 10, "bold"), text_color="#eeeeee")
        self.lbl_text.pack()
        
        self.update_knob()
        
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<MouseWheel>", self.on_scroll)
        
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
        
        # 1. Track (Background Arc)
        self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start_angle, extent=max_extent, 
                               style="arc", width=5, outline=self.track_color)
        
        # 2. Progress (Foreground Arc)
        self.canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start_angle, extent=current_extent, 
                               style="arc", width=5, outline=self.progress_color)
        
        # 3. Indicator Line (Needle)
        # Angle in degrees for math (Tkinter arc start is 3 oclock = 0? No. 
        # Tkinter: 3 oclock is 0. Positive is CounterClockwise.
        # So 240 is approx 7-8 oclock.
        # Angle = Start + Extent
        angle_deg = start_angle + current_extent
        angle_rad = math.radians(angle_deg)
        
        # Line from slightly inner to outer radius
        r_in = 0
        r_out = r
        mx = cx + r_out * math.cos(angle_rad)
        my = cy - r_out * math.sin(angle_rad) # y inverted
        
        # White line for high contrast visibility
        self.canvas.create_line(cx, cy, mx, my, fill="#ffffff", width=2)
        
        # Label
        self.lbl_val.configure(text=f"{self.value:.2f}")

    def set(self, val):
        self.value = max(self.min_val, min(self.max_val, val))
        self.update_knob()
        
    def get(self):
        return self.value
        
    def on_click(self, event):
        self.click_y = event.y
        
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
        
        # Fill Polygon (Close the loop back to start)
        # Start(bottom) -> Start(0,0) -> Attack -> Decay/Sus -> Release -> Release(bottom)
        # y0 is 0.0 level (bottom)? No. l0=0.0 means bottom.
        # But we need to be careful.
        # l0=0.0 -> y0 is bottom.
        
        # Polygon points
        points = [
            x0, y0, # Start (0,0)
            x1, y1, # Attack Peak
            x2, y2, # Sustain
            x3, y3, # Release End (0)
            x3, self.canvas.winfo_height(), # Straight down from release end
            x0, self.canvas.winfo_height()  # Straight down from start
        ]
        # Actually simplified:
        # (x0,y0) -> (x1,y1) -> (x2,y2) -> (x3,y3) are the curve.
        # y0 and y3 are "bottom" visually if level 0.
        
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
