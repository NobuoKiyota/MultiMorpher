import customtkinter as ctk
import os
import shutil
import openpyxl
import winsound
import threading
from tkinter import filedialog, ttk
import tkinter as tk

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SFXReviewerApp(ctk.CTk):
    def __init__(self, start_path=None):
        super().__init__()
        self.title("SFX Factory Reviewer")
        self.geometry("1000x800")
        
        self.current_folder = ""
        self.excel_path = ""
        self.wb = None
        self.ws = None
        self.data_map = {} # filename -> row_index
        self.current_file = None
        
        self.auto_advance = True
        
        self._init_ui()
        
        if start_path and os.path.exists(start_path):
             self.load_batch(start_path)
        else:
            # Try load last state
            import json
            try:
                if os.path.exists("last_state.json"):
                    with open("last_state.json", "r") as f:
                        state = json.load(f)
                        last = state.get("last_reviewer_path")
                        if last and os.path.exists(last):
                            self.load_batch(last)
            except: pass
        
    def _init_ui(self):
        # Layout: Left (List 300px), Right (Detail)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # --- Left Panel ---
        fr_left = ctk.CTkFrame(self, width=300)
        fr_left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        fr_left.grid_rowconfigure(1, weight=1)
        
        ctk.CTkButton(fr_left, text="Load Batch Folder", command=self.browse_folder).grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(fr_left, text="☁ Sync to Cloud", command=self.on_sync, fg_color="#009688", hover_color="#00796B").grid(row=3, column=0, padx=10, pady=20, sticky="ew")
        
        # Treeview style list
        # Using standard tk Treeview for columns (Score, Name)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2b2b2b", fieldbackground="#2b2b2b", foreground="white", rowheight=24)
        style.map("Treeview", background=[("selected", "#1f538d")])
        
        self.tree = ttk.Treeview(fr_left, columns=("score", "name"), show="headings")
        self.tree.heading("score", text="Scr", anchor="center")
        self.tree.column("score", width=40, anchor="center")
        self.tree.heading("name", text="Filename", anchor="w")
        self.tree.column("name", width=220)
        
        self.tree.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        
        sb = ttk.Scrollbar(fr_left, orient="vertical", command=self.tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        
        # Filter / Stats
        self.lbl_stats = ctk.CTkLabel(fr_left, text="Total: 0 | High: 0 | Low: 0")
        self.lbl_stats.grid(row=2, column=0, pady=5)
        
        # --- Right Panel ---
        fr_right = ctk.CTkFrame(self)
        fr_right.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        fr_right.grid_rowconfigure(2, weight=1) # Params expand
        
        # Header
        self.lbl_filename = ctk.CTkLabel(fr_right, text="No File Selected", font=("Arial", 24, "bold"), anchor="w")
        self.lbl_filename.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 5))
        
        self.lbl_path = ctk.CTkLabel(fr_right, text="...", font=("Arial", 12), text_color="gray", anchor="w")
        self.lbl_path.grid(row=1, column=0, sticky="w", padx=20, pady=(0, 20))
        
        # Params List
        self.fr_params = ctk.CTkScrollableFrame(fr_right, label_text="Parameters")
        self.fr_params.grid(row=2, column=0, sticky="nsew", padx=20, pady=10)
        
        # Controls Zone (Bottom)
        fr_ctrl = ctk.CTkFrame(fr_right, height=150, fg_color="#1a1a1a")
        fr_ctrl.grid(row=3, column=0, sticky="ew", padx=20, pady=20)
        
        # Current Score
        self.lbl_current_score = ctk.CTkLabel(fr_ctrl, text="-", font=("Arial", 64, "bold"), width=100)
        self.lbl_current_score.pack(side="left", padx=30)
        
        fr_btns = ctk.CTkFrame(fr_ctrl, fg_color="transparent")
        fr_btns.pack(side="left", fill="y", padx=10)
        
        ctk.CTkLabel(fr_btns, text="Numpad 1-9 to Score").pack(anchor="w")
        self.chk_auto = ctk.CTkCheckBox(fr_btns, text="Auto Advance", command=self.toggle_auto)
        self.chk_auto.select()
        self.chk_auto.pack(anchor="w", pady=5)
        
        ctk.CTkButton(fr_btns, text="PLAY (.)", command=self.play_audio, fg_color="green", width=120).pack(pady=10)
        
        # --- Binds ---
        self.bind("<Key>", self.on_key)
        self.bind(".", lambda e: self.play_audio())
        
    def toggle_auto(self):
        self.auto_advance = self.chk_auto.get()
        
    def browse_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.load_batch(p)
            
    def load_batch(self, folder):
        self.current_folder = folder
        
        # Save state
        import json
        try:
            state = {}
            if os.path.exists("last_state.json"):
                with open("last_state.json", "r") as f:
                    state = json.load(f)
            state["last_reviewer_path"] = folder
            with open("last_state.json", "w") as f:
                json.dump(state, f)
        except: pass
        
        # Look for Excel
        xls = os.path.join(folder, "final_manifest.xlsx")
        # Fallback to generation_log.xlsx
        if not os.path.exists(xls):
             xls = os.path.join(folder, "generation_log.xlsx")
             
        if not os.path.exists(xls):
            print("No Excel log found!")
            return
            
        self.excel_path = xls
        self.wb = openpyxl.load_workbook(xls)
        self.ws = self.wb.active
        
        # Subdirs
        self.dir_high = os.path.join(folder, "HighScore")
        self.dir_low = os.path.join(folder, "LowScore")
        if not os.path.exists(self.dir_high): os.makedirs(self.dir_high)
        if not os.path.exists(self.dir_low): os.makedirs(self.dir_low)
        
        # Parse Excel
        # Assume Col A = Score, Col B = Filename
        # We need headers to show params
        
        headers = [c.value for c in self.ws[1]]
        self.headers = headers
        
        # Clear Tree
        for i in self.tree.get_children(): self.tree.delete(i)
        self.data_map = {}
        
        high_c = 0
        low_c = 0
        
        for idx, row in enumerate(self.ws.iter_rows(min_row=2)):
            # Row index is idx+2
            score_cell = row[0]
            name_cell = row[1]
            
            fname = name_cell.value
            score = score_cell.value
            
            if not fname: continue
            
            # Map filename to row object
            self.data_map[fname] = {
                "row_obj": row,
                "headers": headers,
                "vals": [c.value for c in row] 
            }
            
            # Determine path (it might have moved)
            # Check root, high, low
            actual_path = self.find_file(fname)
            self.data_map[fname]["path"] = actual_path
            
            # Add to Tree
            disp_score = str(score) if score else "-"
            item_id = self.tree.insert("", "end", values=(disp_score, fname))
            self.data_map[fname]["item_id"] = item_id
            
            # Color
            if score:
                try:
                    sC = int(score)
                    if sC >= 8: 
                        self.tree.item(item_id, tags=("high",))
                        high_c += 1
                    elif sC <= 3:
                        self.tree.item(item_id, tags=("low",))
                        low_c += 1
                except: pass
        
        self.tree.tag_configure("high", foreground="#4caf50")
        self.tree.tag_configure("low", foreground="#f44336")
        
        self.lbl_stats.configure(text=f"Total: {len(self.data_map)} | High: {high_c} | Low: {low_c}")
        
    def find_file(self, fname):
        # 1. Root
        p = os.path.join(self.current_folder, fname)
        if os.path.exists(p): return p
        # 2. High
        p = os.path.join(self.dir_high, fname)
        if os.path.exists(p): return p
        # 3. Low
        p = os.path.join(self.dir_low, fname)
        if os.path.exists(p): return p
        return None

    def on_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0])
        fname = item['values'][1]
        self.load_file_details(fname)
        
        if self.auto_advance:
             self.play_audio()

    def load_file_details(self, fname):
        data = self.data_map.get(fname)
        if not data: return
        
        self.current_file = fname
        self.lbl_filename.configure(text=fname)
        self.lbl_path.configure(text=data["path"] if data["path"] else "FILE MISSING")
        
        # Score
        row = data["row_obj"]
        sc = row[0].value
        self.lbl_current_score.configure(text=str(sc) if sc else "-")
        if sc:
             try:
                 if int(sc) >= 8: self.lbl_current_score.configure(text_color="green")
                 elif int(sc) <= 3: self.lbl_current_score.configure(text_color="red")
                 else: self.lbl_current_score.configure(text_color="white")
             except: pass
        else:
             self.lbl_current_score.configure(text_color="white")
             
        # Params
        for w in self.fr_params.winfo_children(): w.destroy()
        
        vals = [c.value for c in row]
        # Skip Score, Name, params... Date
        # Usually params are index 2 to end-2
        
        for i, h in enumerate(self.headers):
            if i < 2: continue # Score, Name
            if not h: continue
            
            val = vals[i]
            if val is None: val = ""
            
            row_fr = ctk.CTkFrame(self.fr_params, fg_color="transparent")
            row_fr.pack(fill="x", pady=1)
            
            # Shorten header if too long?
            lbl_k = ctk.CTkLabel(row_fr, text=str(h)[:25], width=200, anchor="w", text_color="#aaaaaa")
            lbl_k.pack(side="left")
            
            lbl_v = ctk.CTkLabel(row_fr, text=str(val), anchor="w", font=("Consolas", 12))
            lbl_v.pack(side="left")

    def play_audio(self):
        if not self.current_file: return
        path = self.data_map[self.current_file]["path"]
        if path and os.path.exists(path):
            winsound.PlaySound(path, winsound.SND_ASYNC)

    def on_key(self, event):
        if not self.current_file: return
        
        # 1-9
        if event.char.isdigit():
            val = int(event.char)
            if 0 <= val <= 9:
                if val == 0: val = 10 # 0 key as 10? Or 0=10? Let's use 0 as 10 or ignore.
                # User asked for "10 points max". 
                # Let's map '0' to 10.
                self.set_score(val)
        
    def set_score(self, score):
        if not self.current_file: return
        fname = self.current_file
        data = self.data_map[fname]
        
        # 1. Update Excel Row Object
        row = data["row_obj"]
        row[0].value = score
        
        # 2. Save Excel
        try:
            self.wb.save(self.excel_path)
        except Exception as e:
            print(f"Save Error: {e}")
            
        # 3. Move File
        old_path = data["path"]
        if old_path and os.path.exists(old_path):
            if score >= 8:
                target_dir = self.dir_high
            elif score <= 3:
                target_dir = self.dir_low
            else:
                target_dir = self.current_folder # Back to root
            
            if os.path.dirname(old_path) != target_dir:
                 new_path = os.path.join(target_dir, fname)
                 try:
                     shutil.move(old_path, new_path)
                     data["path"] = new_path
                 except Exception as e:
                     print(f"Move Error: {e}")
        
        # 4. Update UI
        self.lbl_current_score.configure(text=str(score))
        item_id = data["item_id"]
        self.tree.set(item_id, "score", str(score))
        
        # Color
        cur_tags = list(self.tree.item(item_id, "tags"))
        if "high" in cur_tags: cur_tags.remove("high")
        if "low" in cur_tags: cur_tags.remove("low")
        
        if score >= 8: cur_tags.append("high")
        elif score <= 3: cur_tags.append("low")
        
        self.tree.item(item_id, tags=cur_tags)
        
        # 5. Next
        if self.auto_advance:
            self.select_next()
            
    def select_next(self):
        sel = self.tree.selection()
        if not sel: return
        
        next_id = self.tree.next(sel[0])
        if next_id:
            self.tree.selection_set(next_id)
            self.tree.focus(next_id)
            # This triggers on_select -> Play

    def on_sync(self):
        # Check config
        config_path = "uploader_config.json"
        target_path = ""
        import json
        
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                c = json.load(f)
                target_path = c.get("upload_target", "")
        
        if not target_path or not os.path.exists(target_path):
            # Ask user
            tk.messagebox.showinfo("Setup", "Please select the Google Drive (Sync Target) folder.\nExample: G:\\My Drive\\SFX_Raw_Candidates")
            target_path = filedialog.askdirectory(title="Select Sync Target Folder")
            if not target_path: return
            
            # Save config
            with open(config_path, "w") as f:
                json.dump({"upload_target": target_path}, f)
                
        # Confirm
        ans = tk.messagebox.askyesno("Sync to Drive", f"Upload High/Low assets to:\n{target_path}\n\nThis will COPY files. Continue?")
        if not ans: return
        
        self.perform_sync(target_path)

    def perform_sync(self, target_root):
        # Structure:
        # Target/HighScore
        # Target/LowScore
        
        t_high = os.path.join(target_root, "HighScore")
        t_low = os.path.join(target_root, "LowScore")
        
        if not os.path.exists(t_high): os.makedirs(t_high)
        if not os.path.exists(t_low): os.makedirs(t_low)
        
        count = 0
        
        # 1. Copy High
        if os.path.exists(self.dir_high):
            for f in os.listdir(self.dir_high):
                src = os.path.join(self.dir_high, f)
                if os.path.isfile(src) and f.lower().endswith(".wav"):
                     dst = os.path.join(t_high, f)
                     if not os.path.exists(dst):
                         shutil.copy2(src, dst)
                         count += 1
        
        # 2. Copy Low
        if os.path.exists(self.dir_low):
            for f in os.listdir(self.dir_low):
                src = os.path.join(self.dir_low, f)
                if os.path.isfile(src) and f.lower().endswith(".wav"):
                     dst = os.path.join(t_low, f)
                     if not os.path.exists(dst):
                         shutil.copy2(src, dst)
                         count += 1
                         
        # 3. Copy/Update Manifest
        # To avoid overwrite, we copy manifest as [PC]_[Folder]_manifest.xlsx
        import socket
        pc_name = socket.gethostname()
        folder_name = os.path.basename(self.current_folder)
        man_name = f"{pc_name}_{folder_name}_manifest.xlsx"
        
        src_man = self.excel_path
        dst_man = os.path.join(target_root, man_name)
        shutil.copy2(src_man, dst_man)
        
        tk.messagebox.showinfo("Sync Complete", f"Synced {count} audio files.\nManifest updated.")
        
        # Mark as synced? (Rename folder)
        # Optional.

    def on_closing(self):
        # Check if unsynced? 
        # For now just simple confirmation
        # self.destroy()
        if tk.messagebox.askokcancel("Quit", "Do you want to quit?"):
             self.destroy()

if __name__ == "__main__":
    import sys
    start_dir = None
    if len(sys.argv) > 1:
        start_dir = sys.argv[1]
        
    app = SFXReviewerApp(start_dir)
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
