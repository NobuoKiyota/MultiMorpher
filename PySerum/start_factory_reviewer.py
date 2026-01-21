import os
import subprocess
import sys

def launch():
    # Target directory is "Output" in the same folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(current_dir, "Output")
    
    if not os.path.exists(target_dir):
        print(f"Warning: Output directory not found at {target_dir}")
        print("Creating it now...")
        os.makedirs(target_dir)

    reviewer_script = os.path.join(current_dir, "sfx_reviewer_app.py")
    
    if not os.path.exists(reviewer_script):
        print(f"Error: Reviewer script not found at {reviewer_script}")
        input("Press Enter to exit...")
        return

    print(f"Launching Reviewer for: {target_dir}")
    # Launch purely, no cmd /k if we want a clean app window, but python console is useful for debug
    subprocess.run([sys.executable, reviewer_script, target_dir])

if __name__ == "__main__":
    launch()
