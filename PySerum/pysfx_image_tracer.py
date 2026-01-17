import os
import glob
import numpy as np
from PIL import Image

class ImageTracer:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(ImageTracer, cls).__new__(cls)
        return cls._instance

    def __init__(self, sample_folder="PitchCurveSample"):
        if not hasattr(self, 'initialized'):
            self.folder = sample_folder
            self.curves = [] # List of normalized arrays
            self.filenames = []
            self.initialized = True
            self.scan_and_process()

    def scan_and_process(self):
        """スキャンして全画像をメモリにキャッシュする"""
        if not os.path.exists(self.folder):
            print(f"[ImageTracer] Folder not found: {self.folder}")
            return
            
        files = sorted(glob.glob(os.path.join(self.folder, "*.png")))
        self.curves = []
        self.filenames = []
        
        for f in files:
            try:
                curve = self._process_image(f)
                if curve is not None:
                    self.curves.append(curve)
                    self.filenames.append(os.path.basename(f))
                    print(f"[ImageTracer] Loaded: {os.path.basename(f)}")
                else:
                    print(f"[ImageTracer] Failed to trace (Low/No Red): {os.path.basename(f)}")
            except Exception as e:
                print(f"[ImageTracer] Error loading {os.path.basename(f)}: {e}")

    def _process_image(self, path):
        """画像から赤線を抽出して0.0-1.0の配列(長さ1000固定)にする"""
        with Image.open(path) as img:
            img = img.convert("RGB")
            # Resize width to standard resolution (e.g. 1000) for consistent output
            target_width = 1000
            w, h = img.size
            if w != target_width:
                img = img.resize((target_width, h))
            
            data = np.array(img, dtype=np.float32) # (H, W, 3)
            
            # Extract Red Emphasis: R - (G + B)/2
            # Or simplified: if R > 100 and R > G+50 and R > B+50
            r = data[:, :, 0]
            g = data[:, :, 1]
            b = data[:, :, 2]
            
            # Red Score
            score = r - (g + b) * 0.5
            score[score < 0] = 0
            
            # Find center of gravity for each column (X)
            # Y coords are 0..H-1 (0 is top)
            # We want normalized 0.0 (Bottom) to 1.0 (Top) ?
            # Usually Pitch Curve: Top is High Pitch (1.0), Bottom is Low (0.0).
            # Image Y: 0 is Top. So we invert.
            
            # Weighted average Y per column
            col_sums = np.sum(score, axis=0) # (W,)
            
            # Avoid division by zero
            valid_cols = col_sums > 1.0
            
            # Create Y indices grid
            y_indices = np.arange(h).reshape(h, 1)
            
            # Weighted Sum of Y
            weighted_y = np.sum(y_indices * score, axis=0) # (W,)
            
            # Calculate Center Y (0 is Top)
            center_y = np.zeros(target_width)
            center_y[valid_cols] = weighted_y[valid_cols] / col_sums[valid_cols]
            
            # Fill missing columns with nearest neighbor or interpolation
            # Simple 1D linear interpolation for gaps
            x_range = np.arange(target_width)
            if np.any(valid_cols):
                center_y = np.interp(x_range, x_range[valid_cols], center_y[valid_cols])
            else:
                return None # No red found
            
            # Normalize to 0.0 - 1.0
            # Image Y=0 -> Value 1.0 (High Pitch)
            # Image Y=H -> Value 0.0 (Low Pitch)
            norm_curve = 1.0 - (center_y / float(h))
            
            return np.clip(norm_curve, 0.0, 1.0)

    def get_curve_count(self):
        return len(self.curves)

    def get_curve(self, index, resolution=None):
        """index: 0 to N-1. resolution: if specified, resample."""
        if index < 0 or index >= len(self.curves):
            # Fallback Flat
            return np.zeros(resolution if resolution else 1000)
            
        curve = self.curves[index]
        
        if resolution and resolution != len(curve):
            # Resample
            curr_x = np.linspace(0, 1, len(curve))
            target_x = np.linspace(0, 1, resolution)
            return np.interp(target_x, curr_x, curve)
            
        return curve
