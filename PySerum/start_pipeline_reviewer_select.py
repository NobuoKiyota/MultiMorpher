import os
import tkinter as tk
from tkinter import filedialog
import subprocess
import sys

def main():
    root = tk.Tk()
    root.withdraw() # Hide main window

    initial_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Pipeline_Output")
    if not os.path.exists(initial_dir):
        initial_dir = os.getcwd()

    print("Please select the target batch folder to review...")
    target_dir = filedialog.askdirectory(initialdir=initial_dir, title="Select Batch Folder to Review")

    if target_dir:
        print(f"Selected: {target_dir}")
        reviewer_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfx_reviewer_app.py")
        if os.path.exists(reviewer_script):
            subprocess.run([sys.executable, reviewer_script, target_dir])
        else:
            print(f"Error: {reviewer_script} not found.")
            input("Press Enter to exit...")
    else:
        print("No folder selected.")

if __name__ == "__main__":
    main()
