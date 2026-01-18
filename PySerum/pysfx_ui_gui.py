
import customtkinter as ctk
import os
import threading
import json
import time
import winsound
from tkinterdnd2 import TkinterDnD, DND_ALL
from tkinter import filedialog
from pysfx_tagger_engine import TaggerEngine

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "tagger_config.json"

try:
    import speech_recognition as sr
    HAS_SR = True
except ImportError:
    HAS_SR = False

class QuartzInteractiveTagger(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        
        self.title("Quartz Interactive Tagger")
        self.geometry("500x750")
        
        self.engine = None
        self.audio_playing = False
        self.loop_var = ctk.BooleanVar(value=False)
        self.config = self.load_config()
        
        # Voice Rec Setup
        self.recognizer = None
        self.mic = None
        self.stop_listening = None
        self.is_listening = False
        

        if HAS_SR:
            try:
                self.recognizer = sr.Recognizer()
                # Default mic
                self.mic = sr.Microphone()
            except Exception as e:
                print(f"Mic Error: {e}")
        
        self.target_voice_field = 'tag' # Default target
        self._init_ui()
        
        # Populate Mics (Robust)
        if HAS_SR:
            try:
                import pyaudio
                p = pyaudio.PyAudio()
                mic_list = []
                for i in range(p.get_device_count()):
                    info = p.get_device_info_by_index(i)
                    if info.get('maxInputChannels') > 0:
                        name = info.get('name')
                        # Attempt to fix encoding if necessary (Windows sometimes returns mojibake)
                        try:
                            # Some environments assert utf-8 but get CP932 bytes
                            # But usually pure python str. Just use as is.
                            pass
                        except: pass
                        mic_list.append(f"{i}: {name}")
                p.terminate()
                
                self.combo_mic.configure(values=mic_list)
                if mic_list: self.combo_mic.set(mic_list[0])
            except Exception as e:
                print(f"PyAudio Error: {e}")
                # Fallback
                try:
                    mics = sr.Microphone.list_microphone_names()
                    mic_list = [f"{i}: {m}" for i, m in enumerate(mics)]
                    self.combo_mic.configure(values=mic_list)
                except: pass
        
        # Restore paths
        if self.config.get("input_path"):
            self.ent_input.insert(0, self.config["input_path"])
        if self.config.get("drive_path"):
            self.ent_drive.insert(0, self.config["drive_path"])
            
        self.after(200, self._animation_loop)

    def _animation_loop(self):
        try:
            txt = self.lbl_progress.cget("text")
            # Only animate if Loading/Scanning/Analyzing
            if any(x in txt for x in ["Loading", "Scanning", "Analyzing"]):
                base = txt.rstrip(".")
                count = txt.count(".")
                if count >= 3: new_txt = base + "."
                else: new_txt = txt + "."
                self.lbl_progress.configure(text=new_txt)
        except: pass
        self.after(500, self._animation_loop)
            
    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0) # Config
        self.grid_rowconfigure(1, weight=1) # Player / Info
        self.grid_rowconfigure(2, weight=0) # Input
        self.grid_rowconfigure(3, weight=0) # Action
        
        # --- Zone 1: Paths ---
        fr_cfg = ctk.CTkFrame(self)
        fr_cfg.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        ctk.CTkLabel(fr_cfg, text="① Workspace Setup", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        # Input
        self.ent_input = ctk.CTkEntry(fr_cfg, placeholder_text="Input Folder (WAV Source)")
        self.ent_input.pack(fill="x", padx=10, pady=2)
        self.ent_input.drop_target_register(DND_ALL)
        self.ent_input.dnd_bind('<<Drop>>', lambda e: self.drop_path(e, self.ent_input))
        
        # Drive
        self.ent_drive = ctk.CTkEntry(fr_cfg, placeholder_text="Learning/Drive Folder (Destination)")
        self.ent_drive.pack(fill="x", padx=10, pady=2)
        self.ent_drive.drop_target_register(DND_ALL)
        self.ent_drive.dnd_bind('<<Drop>>', lambda e: self.drop_path(e, self.ent_drive))
        
        self.btn_load = ctk.CTkButton(fr_cfg, text="Load File List", command=self.load_list, fg_color="#5E35B1")
        self.btn_load.pack(fill="x", padx=10, pady=10)
        
        # --- Zone 2: Monitor ---
        fr_mon = ctk.CTkFrame(self, fg_color="#263238")
        fr_mon.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        
        self.lbl_progress = ctk.CTkLabel(fr_mon, text="Waiting...", font=("Consolas", 12), text_color="#aaa")
        self.lbl_progress.pack(pady=(10,0))
        
        self.lbl_filename = ctk.CTkLabel(fr_mon, text="---", font=("Arial", 18, "bold"), text_color="#fff")
        self.lbl_filename.pack(pady=5)
        
        self.btn_play = ctk.CTkButton(fr_mon, text="▶ Play", font=("Arial", 16), width=100, command=self.play_sound, fg_color="#00E676", text_color="black")
        self.btn_play.pack(pady=(10,2))
        
        self.chk_loop = ctk.CTkCheckBox(fr_mon, text="Loop Play", variable=self.loop_var)
        self.chk_loop.pack(pady=2)
        
        # AI Info
        ctk.CTkLabel(fr_mon, text="AI Suggestions:", font=("Arial", 11, "bold"), text_color="#aaa").pack(pady=(10,2))
        self.lbl_ai_tags = ctk.CTkLabel(fr_mon, text="---", text_color="#4FC3F7")
        self.lbl_ai_tags.pack()
        
        self.btn_train = ctk.CTkButton(fr_mon, text="🧠 Train Model", command=self.train_ai, fg_color="#7B1FA2", width=120, height=28)
        self.btn_train.pack(pady=(10,5))
        
        # --- Zone 3: Input ---
        fr_inp = ctk.CTkFrame(self)
        fr_inp.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        
        fr_inp.grid_columnconfigure(1, weight=1) # Entry expands
        
        ctk.CTkLabel(fr_inp, text="② Your Annotation", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.combo_mic = ctk.CTkComboBox(fr_inp, width=180, command=self.change_mic)
        self.combo_mic.grid(row=0, column=1, columnspan=2, sticky="e", padx=10)
        
        # Tag Row
        ctk.CTkLabel(fr_inp, text="TAG:", width=60).grid(row=1, column=0, padx=5, pady=5)
        self.ent_user_tag = ctk.CTkEntry(fr_inp, placeholder_text="e.g. 爆発, UI")
        self.ent_user_tag.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.ent_user_tag.bind("<KP_Enter>", lambda e: self.next_file())
        self.ent_user_tag.bind("<Return>", lambda e: self.next_file())
        
        self.btn_mic_tag = ctk.CTkButton(fr_inp, text="🎤", width=40, fg_color="#FBC02D", text_color="black", command=lambda: self.toggle_voice_input('tag'))
        self.btn_mic_tag.grid(row=1, column=2, padx=(0,10), pady=5)
        
        # Comment Row
        ctk.CTkLabel(fr_inp, text="Comment:", width=60).grid(row=2, column=0, padx=5, pady=5)
        self.ent_comment = ctk.CTkEntry(fr_inp, placeholder_text="Optional feature note")
        self.ent_comment.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        
        self.btn_mic_cmt = ctk.CTkButton(fr_inp, text="🎤", width=40, fg_color="#FBC02D", text_color="black", command=lambda: self.toggle_voice_input('comment'))
        self.btn_mic_cmt.grid(row=2, column=2, padx=(0,10), pady=5)
        
        # --- Zone 4: Action ---
        fr_act = ctk.CTkFrame(self, fg_color="transparent")
        fr_act.grid(row=3, column=0, sticky="ew", padx=10, pady=10)
        fr_act.grid_columnconfigure(2, weight=1)
        
        self.btn_prev = ctk.CTkButton(fr_act, text="◀ Back", fg_color="#555", width=70, height=50, font=("Arial", 12, "bold"), command=self.prev_file)
        self.btn_prev.grid(row=0, column=0, padx=(0,5))
        
        self.btn_reject = ctk.CTkButton(fr_act, text="🗑 Reject", fg_color="#D32F2F", width=90, height=50, font=("Arial", 14, "bold"), command=self.reject_file)
        self.btn_reject.grid(row=0, column=1, padx=(0,10))
        
        self.btn_next = ctk.CTkButton(fr_act, text="Save & Next", command=self.next_file, height=50, font=("Arial", 16, "bold"))
        self.btn_next.grid(row=0, column=2, sticky="ew")

        # Shortcuts
        self.bind('<space>', self.on_space)
        self.bind('<Escape>', self.on_esc)
        self.bind('<Button-1>', self.on_click_anywhere)

        self.lbl_status = ctk.CTkLabel(self, text="Ready", text_color="gray")
        self.lbl_status.grid(row=4, column=0, pady=5)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f: return json.load(f)
            except: pass
        return {}

    def save_config(self):
        cfg = {"input_path": self.ent_input.get(), "drive_path": self.ent_drive.get()}
        try:
            with open(CONFIG_FILE, 'w') as f: json.dump(cfg, f)
        except: pass

    def drop_path(self, event, widget):
        path = event.data
        if path.startswith('{') and path.endswith('}'): path = path[1:-1]
        widget.delete(0, 'end')
        widget.insert(0, path)

    def load_list(self):
        self.lbl_progress.configure(text="Loading...")
        self.update_idletasks()
        
        inp = self.ent_input.get()
        drv = self.ent_drive.get()
        
        if not os.path.exists(inp):
            self.lbl_status.configure(text="Invalid Input Path", text_color="red")
            return
            
        self.save_config()
        self.engine = TaggerEngine(drv, inp)
        files = self.engine.scan_input()
        
        self.lbl_status.configure(text=f"Loaded {len(files)} files.", text_color="white")
        self.update_view()

    def update_view(self):
        # Stop previous audio
        self.stop_sound()
        
        fname = self.engine.get_current_file()
        total = len(self.engine.todo_list)
        current = self.engine.current_idx + 1
        
        if not fname:
            self.lbl_filename.configure(text="ALL DONE!")
            self.lbl_progress.configure(text=f"{total}/{total}")
            self.btn_next.configure(state="disabled")
            return
            
        self.lbl_filename.configure(text=os.path.basename(fname))
        self.lbl_progress.configure(text=f"{current} / {total}")
        self.btn_next.configure(state="normal")
        
        # Reset Inputs
        self.ent_user_tag.delete(0, "end")
        self.ent_comment.delete(0, "end")
        self.ent_user_tag.focus_set()
        
        # Async Analyze
        threading.Thread(target=self._analyze_bg, daemon=True).start()
        
        # Auto Play
        self.play_sound()

    def _analyze_bg(self):
        tags = self.engine.analyze_current()
        txt = ", ".join([f"{t} ({s:.1f})" for t, s in tags])
        self.lbl_ai_tags.configure(text=txt)

    def play_sound(self):
        if not self.engine: return
        fpath = self.engine.get_current_file()
        if not fpath: return
        
        if self.audio_playing:
            self.stop_sound()
            return

        flags = winsound.SND_FILENAME | winsound.SND_ASYNC
        if self.loop_var.get():
            flags |= winsound.SND_LOOP
            
        try:
            winsound.PlaySound(fpath, flags)
            self.audio_playing = True
            self.btn_play.configure(text="■ Stop")
        except: pass

    def next_file(self):
        if not self.engine: return
        
        # 1. Translate Tag
        raw_tag = self.ent_user_tag.get()
        eng_tag = self.engine.simple_translate(raw_tag)
        comment = self.ent_comment.get()
        
        # 2. Save
        success = self.engine.save_and_next(eng_tag, comment)
        if success:
             self.lbl_status.configure(text="Saved.", text_color="#00E676")
             self.update_view()
        else:
             self.lbl_status.configure(text="Error or End of List", text_color="red")

    def toggle_voice_input(self, target='tag'):
        if not HAS_SR or not self.recognizer:
            self.lbl_status.configure(text="Voice Input Unavailable.", text_color="red")
            return
        
        # If clicking active target -> Stop
        if self.is_listening and self.target_voice_field == target:
            if self.stop_listening:
                try:
                    self.stop_listening(wait_for_stop=False)
                except: pass
                self.stop_listening = None
            self.is_listening = False
            self.btn_mic_tag.configure(fg_color="#FBC02D")
            self.btn_mic_cmt.configure(fg_color="#FBC02D")
            self.lbl_status.configure(text="Voice Input Stopped.", text_color="white")
            return

        # If switching target or starting new
        self.target_voice_field = target
        
        # Update Colors
        if target == 'tag':
            self.btn_mic_tag.configure(fg_color="#E91E63") # Red
            self.btn_mic_cmt.configure(fg_color="#FBC02D")
        else:
            self.btn_mic_tag.configure(fg_color="#FBC02D")
            self.btn_mic_cmt.configure(fg_color="#E91E63") # Red

        # Start if not already
        if not self.is_listening:
            try:
                self.stop_listening = self.recognizer.listen_in_background(self.mic, self.voice_callback)
                self.is_listening = True
            except Exception as e:
                self.lbl_status.configure(text=f"Mic Error: {e}", text_color="red")
                return

        field_name = "Tag" if target == 'tag' else "Comment"
        self.lbl_status.configure(text=f"Listening for {field_name}... (Speak Japanese)", text_color="#E91E63")

    def voice_callback(self, recognizer, audio):
        try:
            # Japanese recognition
            text = recognizer.recognize_google(audio, language="ja-JP")
            self.after(0, lambda: self.update_from_voice(text))
        except sr.UnknownValueError:
            pass # No speech
        except sr.RequestError:
            self.after(0, lambda: self.lbl_status.configure(text="API Error", text_color="red"))

    def update_from_voice(self, text):
        if not text: return
        self.lbl_status.configure(text=f"Heard: {text}", text_color="white")
        
        if self.target_voice_field == 'tag':
            self.ent_user_tag.delete(0, "end")
            self.ent_user_tag.insert(0, text)
        else:
            ws = self.ent_comment.get()
            if ws:
                self.ent_comment.insert("end", " " + text)
            else:
                self.ent_comment.insert(0, text)

    def change_mic(self, choice):
        if not HAS_SR: return
        try:
            was_listening = self.is_listening
            tgt = self.target_voice_field
            
            # Stop first if running
            if was_listening:
                self.toggle_voice_input(tgt)
                # Allow thread to cleanup
                self.update_idletasks()
                time.sleep(0.2)
                
            idx = int(choice.split(":")[0])
            self.mic = sr.Microphone(device_index=idx)
            
            # Restart
            if was_listening:
                self.toggle_voice_input(tgt)
                
        except Exception as e:
            print(f"Mic Change Error: {e}")
            self.lbl_status.configure(text=f"Device Error: {e}", text_color="red")

    def reject_file(self):
        self.ent_user_tag.delete(0, "end")
        self.ent_user_tag.insert(0, "Reject")
        self.next_file()

    def train_ai(self):
        if not self.engine: return
        self.lbl_status.configure(text="Training AI... (This may take a while)", text_color="yellow")
        self.btn_train.configure(state="disabled")
        self.update_idletasks()
        
        def _target():
            try:
                res = self.engine.train_model()
                self.after(0, lambda: self.lbl_status.configure(text=res, text_color="#00E676"))
            except Exception as e:
                self.after(0, lambda: self.lbl_status.configure(text=f"Train Error: {e}", text_color="red"))
            finally:
                self.after(0, lambda: self.btn_train.configure(state="normal"))
            
        threading.Thread(target=_target, daemon=True).start()

    def stop_sound(self):
        if self.audio_playing:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except: pass
            self.audio_playing = False
            self.btn_play.configure(text="▶ Play")

    def prev_file(self):
        if not self.engine: return
        self.stop_sound()
        if self.engine.prev_file():
             self.update_view()
        else:
             self.lbl_status.configure(text="First file.", text_color="yellow")

    def on_space(self, event):
        widget = self.focus_get()
        # If focusing entry, do nothing (let space type)
        if widget and "entry" in str(widget).lower():
            return
        self.play_sound()

    def on_esc(self, event):
        self.focus_set()
        
    def on_click_anywhere(self, event):
        try:
             # Basic check if clicking entry
             w = event.widget
             # In CTK/Tkinter, widget names might vary, but this is a reasonable heuristic
             if "entry" in str(w).lower(): return
             self.focus_set()
        except: pass

if __name__ == "__main__":
    app = QuartzInteractiveTagger()
    app.mainloop()
