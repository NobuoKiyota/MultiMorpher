
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import threading
import sys
import os
import queue
from pysfx_ui_extractor import scan_and_extract
from tkinterdnd2 import TkinterDnD, DND_ALL

# Configure Appearance
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class UIExctractorGUI(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)

        self.title("Quartz UI Extractor")
        self.geometry("480x700")

        # Layout Configuration
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top Frame: Target selection
        self.frame_top = ctk.CTkFrame(self)
        self.frame_top.grid(row=0, column=0, padx=20, pady=20, sticky="ew")
        
        self.lbl_target = ctk.CTkLabel(self.frame_top, text="Target Directory:", font=("Roboto", 14, "bold"))
        self.lbl_target.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        
        self.entry_path = ctk.CTkEntry(self.frame_top, width=500, placeholder_text="Path to WAV folder...")
        self.entry_path.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.frame_top.grid_columnconfigure(1, weight=1)
        
        self.btn_browse = ctk.CTkButton(self.frame_top, text="📂 Browse / Drag Folder Here", command=self.browse_folder)
        self.btn_browse.grid(row=0, column=2, padx=10, pady=10)
        
        # Action Button
        self.btn_run = ctk.CTkButton(self.frame_top, text="START EXTRACTION", command=self.start_thread, fg_color="#E91E63", hover_color="#C2185B", font=("Roboto", 14, "bold"))
        self.btn_run.grid(row=1, column=0, columnspan=3, padx=10, pady=(0,10), sticky="ew")
        
        # Bottom Frame: Log
        self.frame_log = ctk.CTkFrame(self)
        self.frame_log.grid(row=1, column=0, padx=20, pady=(0,20), sticky="nsew")
        
        self.lbl_log = ctk.CTkLabel(self.frame_log, text="Execution Log", font=("Roboto", 12))
        self.lbl_log.pack(anchor="w", padx=10, pady=5)
        
        self.txt_log = ctk.CTkTextbox(self.frame_log, font=("Consolas", 12))
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Setup Queue for Thread Communication
        self.log_queue = queue.Queue()
        self.is_running = False
        
        # Status Bar
        self.lbl_status = ctk.CTkLabel(self, text="Ready - Drag & Drop Supported", anchor="w")
        self.lbl_status.grid(row=2, column=0, padx=20, pady=5, sticky="ew")

        # Initial Default Path (Current Directory)
        self.entry_path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # Start monitoring queue
        self.check_queue()

        # Register Drag & Drop
        self.drop_target_register(DND_ALL)
        self.dnd_bind('<<Drop>>', self.drop)

    def drop(self, event):
        path = event.data
        if path:
            # Clean curly braces if present (Tcl artifact for paths with spaces)
            if path.startswith('{') and path.endswith('}'):
                path = path[1:-1]
            
            # Remove multiple paths if dragged (just take first)
            # Actually TkinterDnD might allow multiple items.
            # Usually separated by space if not braces? 
            # Simple handling: assume single folder or take first valid
            
            # If path ends with specific file ext, get dirname
            if os.path.isfile(path):
                path = os.path.dirname(path)
            
            if os.path.exists(path):
                self.entry_path.delete(0, tk.END)
                self.entry_path.insert(0, path)
                self.logger(f"Target set to: {path}")

    def browse_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.entry_path.delete(0, tk.END)
            self.entry_path.insert(0, folder_selected)

    def logger(self, message):
        """Called by the extractor script (in another thread)"""
        self.log_queue.put(str(message))

    def status_update(self, msg):
        """Called by thread to update status label"""
        # Queue simple strings starting with "STATUS:" to differentiate
        self.log_queue.put(f"STATUS:{msg}")

    def check_queue(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                if msg == "___DONE___":
                    self.btn_run.configure(state="normal", text="START EXTRACTION")
                    self.is_running = False
                elif msg.startswith("STATUS:"):
                    self.lbl_status.configure(text=msg[7:])
                else:
                    self.txt_log.insert("end", msg + "\n")
                    self.txt_log.see("end")
        except queue.Empty:
            pass
        
        self.after(100, self.check_queue)

    def start_thread(self):
        if self.is_running:
            return
        
        target_dir = self.entry_path.get()
        if not os.path.isdir(target_dir):
            self.logger(f"Error: Invalid directory: {target_dir}")
            return
            
        self.is_running = True
        self.btn_run.configure(state="disabled", text="Running...")
        self.txt_log.delete("1.0", "end") # Clear Log
        
        threading.Thread(target=self.run_process, args=(target_dir,), daemon=True).start()

    def run_process(self, target_dir):
        try:
            scan_and_extract(target_dir, logger=self.logger, status_callback=self.status_update)
            self.logger("\n=== COMPLETE ===")
        except Exception as e:
            self.logger(f"\nFATAL ERROR: {e}")
            import traceback
            self.logger(traceback.format_exc())
            
        self.is_running = False
        self.log_queue.put("___DONE___")

if __name__ == "__main__":
    app = UIExctractorGUI()
    app.mainloop()
