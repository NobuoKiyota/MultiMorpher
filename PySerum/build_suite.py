import os
import subprocess
import shutil

# Project Configuration
DIST_DIR = "QuartzSuite"
TOOLS = [
    "quartz_launcher.py",
    "pysfx_factory_gui.py",
    "pysfx_masker_gui.py",
    "pysfx_slicer_gui.py",
    "pysfx_ui_gui.py",
    "pysfx_transformer_gui.py",
    "pysfx_normalizer_gui.py",
    "pysfx_translator_gui.py"
]

# Assets needed in the same folder
ASSETS_DIRS = ["presets", "PitchCurveSample", "Settings", "BestAssets"]
# Note: "Output" and "Scans" should be created by app if missing, but we can copy empty.

def build():
    print("--- Starting Quartz Suite Build ---")
    
    # 1. Clean previous build
    if os.path.exists("dist"):
        try: shutil.rmtree("dist")
        except: pass
    if os.path.exists("build"):
        try: shutil.rmtree("build")
        except: pass

    # 2. Build each tool
    # We build everything into 'onedir' mode, but merged?
    # No, PyInstaller 'onedir' creates a folder per app.
    # We want ONE folder with all EXEs sharing dependencies if possible?
    # Sharing is hard. Simple way: Build all to same output dir?
    # PyInstaller overwrites.
    # 
    # Best approach for stability: Build 'quartz_launcher' as the main 'onedir'.
    # Then build others as 'onedir' too, but effectively we will have multiple huge folders.
    # 
    # BETTER: Build ALL as '--onefile' (Single EXE) and put them in one folder.
    # Start up might be slightly slower (unpacking), but distribution is cleaner.
    # User asked for "EXE化". One folder with 8 EXEs is fine.
    
    os.makedirs(f"dist/{DIST_DIR}", exist_ok=True)
    
    for script in TOOLS:
        print(f"Building {script}...")
        cmd = [
            "pyinstaller",
            "--noconfirm",
            "--onedir", # Use onedir for speed, we will merge? No, merge is risky.
            # Let's use --onefile for sub-tools to keep it tidy, 
            # OR --onedir for everything and hope for the best?
            # 
            # Let's try --onedir for JUST the launcher, and --onefile for tools?
            # Or --onefile for EVERYTHING. Simplest structure.
            "--onefile", 
            "--windowed", # No console
            "--distpath", f"dist/{DIST_DIR}",
            "--clean",
            # Add icon if available?
            # "--icon=icon.ico", 
            script
        ]
        subprocess.run(cmd, check=True)

    # 3. Copy Assets
    print("Copying Assets...")
    base_dist = f"dist/{DIST_DIR}"
    
    for d in ASSETS_DIRS:
        src = d
        dst = os.path.join(base_dist, d)
        if os.path.exists(src):
            if os.path.exists(dst): shutil.rmtree(dst)
            shutil.copytree(src, dst)
            print(f"Copied {d}")
    
    # Copy Config JSONs
    for f in os.listdir("."):
        if f.endswith(".json") and os.path.isfile(f):
            shutil.copy(f, os.path.join(base_dist, f))
            print(f"Copied {f}")

    # Copy Custom Data Python files if dynamic import needed?
    # ImageTracer uses 'PitchCurveSample'.
    # Factory uses 'pysfx_param_config' etc. PyInstaller handles imports.
    
    print(f"--- Build Complete! ---")
    print(f"Output: dist/{DIST_DIR}")

if __name__ == "__main__":
    build()
