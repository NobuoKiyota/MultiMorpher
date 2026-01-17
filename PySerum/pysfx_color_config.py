class PySFXColors:
    # Colors defined as RGBA (Red, Green, Blue, Alpha) 0-255
    # Alpha is used to blend with a dark background (#000000 or similar) for "Dark Mode" intensity.
    # Background color assumed for blending:
    BG_BASE = (20, 20, 20) 

    GROUP_RGBA = {
        # Basic Numeric Groups
        1: (100, 100, 100, 40),   # Grey
        2: (255, 50, 50, 30),     # Red
        3: (255, 150, 50, 30),    # Orange
        4: (50, 255, 50, 25),     # Green
        5: (50, 255, 255, 25),    # Cyan
        6: (50, 100, 255, 30),    # Blue
        7: (220, 50, 220, 30),    # LFO-Pitch (Magenta)
        8: (100, 255, 50, 30),    # LFO-Vol (Lime)
        9: (255, 80, 120, 30),    # LFO-Pan (Pink)
        10: (50, 50, 255, 80),    # Blue2
        
        # New Named Groups (Page 3/4)
        "Distortion": (200, 50, 0, 40),   # Burnt Orange
        "Phaser": (100, 0, 200, 40),      # Purple
        "Reverb": (0, 150, 255, 40),      # Sky Blue
        "Delay": (0, 200, 150, 40),       # Teal
        "Spread": (255, 100, 150, 40),    # Rose
        
        "Envelope": (255, 200, 0, 30),    # Yellow
        "Pitch": (50, 255, 50, 25),       # Green
        "Stereo": (0, 255, 255, 25)       # Cyan
    }
    
    @classmethod
    def get_color(cls, group_id):
        if group_id is None or group_id == 0: return "transparent"
        
        rgba = cls.GROUP_RGBA.get(group_id, (128, 128, 128, 20)) # Default

        
        return cls._blend_rgba_to_hex(rgba, cls.BG_BASE)

    @staticmethod
    def _blend_rgba_to_hex(fore_rgba, back_rgb):
        """Blend foreground RGBA over opaque background RGB"""
        r, g, b, a = fore_rgba
        bg_r, bg_g, bg_b = back_rgb
        
        alpha = a / 255.0
        
        out_r = int(r * alpha + bg_r * (1 - alpha))
        out_g = int(g * alpha + bg_g * (1 - alpha))
        out_b = int(b * alpha + bg_b * (1 - alpha))
        
        return f"#{out_r:02x}{out_g:02x}{out_b:02x}"

    @classmethod
    def get_excel_color(cls, group_id):
        """Returns ARGB Hex for Excel or standard Hex ignoring alpha (RGB)"""
        if group_id is None or group_id == 0: return "FFFFFFFF" # White? or None
        
        rgba = cls.GROUP_RGBA.get(group_id, (128, 128, 128, 20))
        r, g, b, a = rgba
        
        # Excel OpenPyXL uses ARGB hex "AARRGGBB" or "RRGGBB"
        # Since our defined RGBA has low alpha (e.g. 30), using it directly in Excel might look very faint
        # if the background is white.
        # User said: "If RGBA not supported, Alpha ignore is OK" -> meaning implies we can use full opacity color?
        # OR we should use the blended color we see in GUI?
        # The GUI is dark theme. Excel is usually light theme.
        # If we use the raw color (e.g. Red (255, 50, 50)) it's very bright.
        # But maybe that's what is wanted for grouping.
        # Let's return the "Base Color" without alpha (Full Opacity) for clear grouping in Excel.
        # Or maybe pastel?
        # Let's use the explicit RGB values.
        
        return f"{r:02x}{g:02x}{b:02x}" # RGB Hex
