import customtkinter as ctk
import speech_recognition as sr
import threading
import time
import numpy as np
import pyaudio
import pyperclip
from deep_translator import GoogleTranslator

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class QuartzTranslator(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Quartz Audio Translator")
        self.geometry("400x550")
        
        self.recognizer = sr.Recognizer()
        self.mic = None
        self.is_listening = False
        self.stop_listening_func = None

        self.p_audio = pyaudio.PyAudio()
        self.stream = None
        
        self._init_ui()
        self.after(100, self.populate_mics)
        
        # Meter Thread
        self.meter_running = True
        threading.Thread(target=self._meter_loop, daemon=True).start()

    def _init_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # 1. Device Select
        fr_top = ctk.CTkFrame(self, fg_color="transparent")
        fr_top.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(fr_top, text="Microphone:", font=("Arial", 12)).pack(anchor="w")
        self.combo_mic = ctk.CTkComboBox(fr_top, width=300, command=self.change_mic)
        self.combo_mic.pack(fill="x", pady=(2, 0))

        # 2. Level Meter
        self.canvas_meter = ctk.CTkCanvas(self, height=15, bg="#222", highlightthickness=0)
        self.canvas_meter.pack(fill="x", padx=15, pady=(10, 5))
        self.meter_bar = self.canvas_meter.create_rectangle(0, 0, 0, 15, fill="#00E676", width=0)

        # 3. Main Controls
        self.btn_mic = ctk.CTkButton(self, text="🎤 Start Listening", command=self.toggle_listening, 
                                     height=50, font=("Arial", 16, "bold"), fg_color="#FBC02D", text_color="black")
        self.btn_mic.pack(fill="x", padx=20, pady=10)
        
        self.lbl_status = ctk.CTkLabel(self, text="Ready", text_color="gray")
        self.lbl_status.pack(pady=5)

        # 4. Results
        fr_res = ctk.CTkFrame(self)
        fr_res.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Japanese Row
        fr_jp_head = ctk.CTkFrame(fr_res, fg_color="transparent", height=24)
        fr_jp_head.pack(fill="x", padx=5, pady=(5,0))
        ctk.CTkLabel(fr_jp_head, text="Japanese (Detected):", font=("Arial", 12, "bold")).pack(side="left")
        ctk.CTkButton(fr_jp_head, text="Clear", width=60, height=20, fg_color="#555", command=self.clear_jp).pack(side="right")
        
        self.txt_jp = ctk.CTkTextbox(fr_res, height=60, font=("Meiryo", 14))
        self.txt_jp.pack(fill="x", padx=5, pady=(2, 5))
        self.txt_jp.bind("<KeyRelease>", self.on_jp_key)
        self.translation_timer = None
        
        # English
        ctk.CTkLabel(fr_res, text="English (Translated):", font=("Arial", 12, "bold")).pack(anchor="w", padx=5)
        self.txt_en = ctk.CTkTextbox(fr_res, height=60, font=("Arial", 14))
        self.txt_en.pack(fill="x", padx=5, pady=(2, 5))

        # Tags
        ctk.CTkLabel(fr_res, text="Tags (Generated):", font=("Arial", 12, "bold")).pack(anchor="w", padx=5)
        self.txt_tags = ctk.CTkTextbox(fr_res, height=50, font=("Arial", 12), text_color="#4FC3F7")
        self.txt_tags.pack(fill="x", padx=5, pady=(2, 5))
        
        # Action Buttons
        fr_acts = ctk.CTkFrame(self, fg_color="transparent")
        fr_acts.pack(fill="x", padx=20, pady=20)
        
        self.btn_copy_en = ctk.CTkButton(fr_acts, text="Copy English", command=self.copy_english, height=40, width=140, fg_color="#E040FB")
        self.btn_copy_en.pack(side="left", padx=5)
        
        self.btn_copy_tag = ctk.CTkButton(fr_acts, text="Copy Tags", command=self.copy_tags, height=40, width=140, fg_color="#00BCD4")
        self.btn_copy_tag.pack(side="right", padx=5)

    def populate_mics(self):
        devices = []
        default_idx = 0
        try:
            cnt = self.p_audio.get_device_count()
            for i in range(cnt):
                info = self.p_audio.get_device_info_by_index(i)
                if info.get('maxInputChannels') > 0:
                    name = info.get('name')
                    devices.append(f"{i}: {name}")
            
            if devices:
                self.combo_mic.configure(values=devices)
                self.combo_mic.set(devices[0])
                self.change_mic(devices[0])
        except Exception as e:
            print(f"Mic Enum Error: {e}")

    def change_mic(self, choice):
        try:
            idx = int(choice.split(":")[0])
            self.mic_idx = idx
            
            # Stop if running
            was_listening = self.is_listening
            if self.is_listening:
                self.toggle_listening()
            
            # Re-init mic
            self.mic_source = sr.Microphone(device_index=idx)
            
            # Restart if it was running
            if was_listening:
                self.after(200, self.toggle_listening)
                
        except Exception as e:
            print(f"Change Mic Error: {e}")

    def toggle_listening(self):
        if self.is_listening:
            # STOP
            self.is_listening = False
            self.btn_mic.configure(text="🎤 Start Listening", fg_color="#FBC02D")
            self.lbl_status.configure(text="Stopped", text_color="gray")
        else:
            # START
            if not hasattr(self, 'mic_source'): 
                self.lbl_status.configure(text="No Mic Selected")
                return
            
            self.is_listening = True
            self.btn_mic.configure(text="⏹ Stop Listening", fg_color="#E91E63")
            self.lbl_status.configure(text="Initializing...", text_color="yellow")
            
            threading.Thread(target=self._listen_loop, daemon=True).start()

    def _listen_loop(self):
        try:
            with self.mic_source as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                if not self.is_listening: return
                
                self.after(0, lambda: self.lbl_status.configure(text="Listening...", text_color="#E91E63"))
                
                while self.is_listening:
                    try:
                        audio = self.recognizer.listen(source, timeout=1.0, phrase_time_limit=10.0)
                        self._process_audio(audio)
                    except sr.WaitTimeoutError:
                        continue 
                    except Exception as e:
                        pass
        except Exception as e:
            print(f"Mic Init Error: {e}")
            self.is_listening = False
            self.after(0, lambda: self.reset_ui_state())

    def reset_ui_state(self):
        self.btn_mic.configure(text="🎤 Start Listening", fg_color="#FBC02D")
        self.lbl_status.configure(text="Mic Error (Check device)", text_color="red")

    def _process_audio(self, audio):
        try:
            jp_text = self.recognizer.recognize_google(audio, language="ja-JP")
            if not jp_text: return
            
            self.after(0, lambda: self.update_jp(jp_text))
            
            en_text = GoogleTranslator(source='ja', target='en').translate(jp_text)
            self.after(0, lambda: self.update_en(en_text))
            
        except sr.UnknownValueError:
            pass 
        except Exception as e:
            print(f"Trans Error: {e}")

    def update_jp(self, text):
        self.txt_jp.delete("1.0", "end")
        self.txt_jp.insert("end", text)
        self.lbl_status.configure(text="Translating...", text_color="yellow")

    def update_en(self, text):
        self.txt_en.delete("1.0", "end")
        self.txt_en.insert("end", text)
        self.lbl_status.configure(text="Listening...", text_color="#E91E63")
        self.after(0, lambda: self.generate_tags(text))

    def generate_tags(self, text):
        # Stop words (Common English grammar words)
        STOP_WORDS = {"a", "an", "the", "in", "on", "at", "by", "with", "from", 
                      "to", "for", "of", "and", "or", "is", "are", "it", "this", "that", "level", "please", "my", "your"}
                      
        # Normalize
        import re
        clean = re.sub(r'[^a-zA-Z0-9\s]', '', text.lower())
        words = clean.split()
        
        tags = [w for w in words if w not in STOP_WORDS and len(w) > 1]
        
        # Deduplicate preserving order
        seen = set()
        unique_tags = []
        for t in tags:
            if t not in seen:
                unique_tags.append(t)
                seen.add(t)
        
        tag_str = ", ".join(unique_tags)
        self.txt_tags.delete("1.0", "end")
        self.txt_tags.insert("end", tag_str)

    def copy_english(self):
        text = self.txt_en.get("1.0", "end").strip()
        if text:
            pyperclip.copy(text)
            self.lbl_status.configure(text="Copied English!", text_color="#E040FB")

    def copy_tags(self):
        text = self.txt_tags.get("1.0", "end").strip()
        if text:
            pyperclip.copy(text)
            self.lbl_status.configure(text="Copied Tags!", text_color="#00BCD4")

    def clear_jp(self):
        self.txt_jp.delete("1.0", "end")

    def on_jp_key(self, event):
        if self.translation_timer:
            self.after_cancel(self.translation_timer)
        self.translation_timer = self.after(1000, self.translate_input)

    def translate_input(self):
        text = self.txt_jp.get("1.0", "end").strip()
        if not text: return
        
        self.lbl_status.configure(text="Translating Text...", text_color="yellow")
        
        def run():
            try:
                en_text = GoogleTranslator(source='ja', target='en').translate(text)
                self.after(0, lambda: self.update_en(en_text))
            except Exception as e:
                print(f"Text Trans Error: {e}")
                
        threading.Thread(target=run, daemon=True).start()
            
    def _meter_loop(self):
        """Read audio level when NOT listening (Mic Check). SR locks device during listen."""
        CHUNK = 1024
        while self.meter_running:
            # Conflict Avoidance: If SR is listening, close our manual stream
            if self.is_listening:
                if self.stream:
                    try:
                        self.stream.stop_stream()
                        self.stream.close()
                    except: pass
                    self.stream = None
                
                # Visual Pulse to indicate "Active"
                import random
                fake_level = random.uniform(0.1, 0.3) 
                self.after(0, lambda v=fake_level: self.update_meter(v))
                time.sleep(0.1)
                continue

            # --- Mic Check Mode (Not Listening to SR) ---
            if not hasattr(self, 'mic_idx'):
                time.sleep(0.1)
                continue
                
            try:
                if self.stream is None:
                     self.stream = self.p_audio.open(format=pyaudio.paInt16,
                                                    channels=1,
                                                    rate=44100,
                                                    input=True,
                                                    input_device_index=self.mic_idx,
                                                    frames_per_buffer=CHUNK)
                
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                shorts = np.frombuffer(data, dtype=np.int16)
                rms = np.sqrt(np.mean(shorts**2))
                level = min(1.0, rms / 10000.0) 
                
                self.after(0, lambda v=level: self.update_meter(v))
                
            except Exception as e:
                if self.stream:
                    try: 
                        self.stream.close()
                    except: pass
                    self.stream = None
                time.sleep(1.0)

    def update_meter(self, level):
        w = self.canvas_meter.winfo_width()
        bar_w = w * level
        self.canvas_meter.coords(self.meter_bar, 0, 0, bar_w, 15)
        
        # Color Code
        if level > 0.9: col = "#D32F2F" # Red clip
        elif level > 0.7: col = "#FBC02D" # Yellow
        else: col = "#00E676" # Green
        self.canvas_meter.itemconfig(self.meter_bar, fill=col)

    def on_close(self):
        self.meter_running = False
        if self.stream: self.stream.close()
        self.p_audio.terminate()
        self.stop_listening_func = None
        self.destroy()

if __name__ == "__main__":
    app = QuartzTranslator()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
