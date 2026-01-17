import numpy as np
import scipy.signal

# 共通定数
SR = 48000
BLOCK_SIZE = 512

class ADSR:
    """音量・変調の時間変化を制御するクラス"""
    IDLE, ATTACK, DECAY, SUSTAIN, RELEASE = 0, 1, 2, 3, 4
    
    def __init__(self):
        self.state = self.IDLE
        self.level = 0.0
        self.set_params(0.01, 0.1, 0.7, 0.5)
        
    def set_params(self, a, d, s, r):
        self.attack_time = max(0.001, a)
        self.decay_time = max(0.001, d)
        self.sustain_level = np.clip(s, 0.0, 1.0)
        self.release_time = max(0.001, r)
        self.attack_step = 1.0 / (self.attack_time * SR + 1.0)
        self.decay_step = (1.0 - self.sustain_level) / (self.decay_time * SR + 1.0)
        self.release_step = self.sustain_level / (self.release_time * SR + 1.0)
        
    def trigger(self):
        self.state = self.ATTACK
        
    def release(self):
        if self.level <= 1e-5:
            self.state = self.IDLE
            self.level = 0.0
        else:
            self.state = self.RELEASE
            self.release_step = self.level / (self.release_time * SR + 1.0)

    def process(self, num_samples):
        out = np.zeros(num_samples)
        cursor = 0
        while cursor < num_samples:
            rem = num_samples - cursor
            if self.state == self.ATTACK:
                n = min(rem, int((1.0 - self.level)/self.attack_step) + 1)
                out[cursor:cursor+n] = self.level + np.arange(n)*self.attack_step
                self.level += n*self.attack_step
                cursor += n
                if self.level >= 1.0: self.level = 1.0; self.state = self.DECAY
            elif self.state == self.DECAY:
                n = min(rem, int((self.level - self.sustain_level)/self.decay_step) + 1)
                out[cursor:cursor+n] = self.level - np.arange(n)*self.decay_step
                self.level -= n*self.decay_step
                cursor += n
                if self.level <= self.sustain_level: self.level = self.sustain_level; self.state = self.SUSTAIN
            elif self.state == self.SUSTAIN:
                out[cursor:] = self.level
                cursor = num_samples
            elif self.state == self.RELEASE:
                if self.release_step <= 1e-9:
                    out[cursor:] = 0.0; self.level = 0.0; self.state = self.IDLE; break
                n = min(rem, int(self.level/self.release_step) + 1)
                out[cursor:cursor+n] = self.level - np.arange(n)*self.release_step
                self.level -= n*self.release_step
                cursor += n
                if self.level <= 0: self.level = 0; self.state = self.IDLE; break
            else:
                break
        return out

class DSPUtils:
    """フィルターや歪みなどの共通エフェクト処理"""
    @staticmethod
    def apply_lowpass(audio, cutoff, zi):
        f_freq = np.clip(cutoff, 20, 20000)
        alpha = (2*np.pi*f_freq/SR) / (2*np.pi*f_freq/SR + 1)
        # 1-pole filter simulation
        out, zi = scipy.signal.lfilter([alpha], [1, -(1-alpha)], audio, zi=zi)
        return out, zi

    @staticmethod
    def apply_distortion(audio, drive):
        if drive <= 0: return audio
        k = drive * 20
        return (1 + k) * audio / (1 + k * np.abs(audio))