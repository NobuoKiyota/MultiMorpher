import numpy as np
import random
import scipy.io.wavfile
import os
from pyserum_engine import SerumEngine, SR, BLOCK_SIZE, AutomationLane

class PySerumFactory:
    def __init__(self):
        self.engine = SerumEngine()
        self.out_dir = "Output"
        if not os.path.exists(self.out_dir): os.makedirs(self.out_dir)

    def get_val(self, cfg, name):
        """Random設定に応じて単一の値または範囲内ランダム値を返す"""
        c = cfg[name]
        if c["random"]:
            v_min = float(c["min"])
            v_max = float(c["max"])
            return random.uniform(v_min, v_max)
        else:
            return float(c["value"])

    def run_advanced_batch(self, config):
        print("--- Advanced Production Started ---")
        
        # 1. 共通パラメータ決定
        duration = self.get_val(config, "Duration")
        root_note = int(self.get_val(config, "NoteRange"))
        num_voices = int(self.get_val(config, "Voices"))
        
        # 2. 音色設定 (ADSR反映)
        a = self.get_val(config, "AmpAttack") / 1000.0
        d = self.get_val(config, "AmpDecay") / 1000.0
        s = float(config["AmpSustain"]["value"]) / 127.0
        r = self.get_val(config, "AmpRelease") / 1000.0
        self.engine.set_adsr(a, d, s, r)

        # 3. MIDIノート構成 (Chordアルゴリズム)
        notes = [root_note]
        if config["Chord"]["value"] and num_voices > 1:
            # 簡易コード生成 (1, 3, 5, 7...)
            is_minor = random.choice([True, False])
            intervals = [3, 7, 10] if is_minor else [4, 7, 11]
            for i in range(num_voices - 1):
                notes.append(root_note + intervals[i % 3] + (12 * (i // 3)))
        elif num_voices > 1:
            # 完全ランダム
            for _ in range(num_voices - 1):
                notes.append(root_note + random.randint(-12, 12))

        # 4. ピッチ・オートメーション生成
        p_range = self.get_val(config, "PitchRange") # cents
        if abs(p_range) > 0:
            # 0..1 のカーブを生成
            points = [(0.0, 1.0), (1.0, 0.0)] # 簡易的な降下
            self.engine.automations["osc_a_semi"] = AutomationLane(duration=duration)
            self.engine.automations["osc_a_semi"].points = points
            # Engine側で semi = base + (auto * p_range/100) のような処理が必要
        
        # 5. レンダリング開始 (Strum処理含む)
        strum_ms = self.get_val(config, "Strum")
        print(f"Generating notes: {notes} with {strum_ms}ms strum")
        
        # ... (以下、これまでのレンダリングループを詳細設定に合わせて実行)
        # Note On/Offをstrum時間分ずらしてキューイングし、blockごとに処理