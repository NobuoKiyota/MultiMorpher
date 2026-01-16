import numpy as np
import scipy.signal
import soundfile as sf
import random

class WeaponSynth:
    def __init__(self):
        self.sr = 44100
        self.bit_depth = 16
    
    def _float_to_pcm16(self, audio):
        audio = np.clip(audio, -1.0, 1.0)
        return (audio * 32767).astype(np.int16)

    def _generate_envelope(self, length, attack, decay, sustain_level=0.0, release=0.0):
        # Simple AD or ADSR envelope generator
        t = np.linspace(0, 1, length)
        att_samps = int(attack * self.sr)
        
        # Guard against zero attack
        att_samps = max(1, att_samps)
        
        if att_samps >= length:
            return np.linspace(0, 1, length)
            
        env = np.zeros(length)
        # Attack
        env[:att_samps] = np.linspace(0, 1, att_samps)
        
        # Decay/Release
        rem = length - att_samps
        # Exponential decay to 0
        tau = decay  # time constant
        if tau > 0:
            xs = np.linspace(0, rem/self.sr, rem)
            decay_curve = np.exp(-xs / tau)
            env[att_samps:] = decay_curve
        else:
            env[att_samps:] = 0
            
        return env

    def _generate_noise(self, length, color="white"):
        if color == "white":
            return np.random.uniform(-1, 1, length)
        elif color == "pink":
            # Simple 1/f approximation
            white = np.random.uniform(-1, 1, length)
            b, a = scipy.signal.butter(1, 0.02) # Low shelving
            return scipy.signal.lfilter(b, a, white)
        return np.random.uniform(-1, 1, length)

    def generate_charge(self, duration, swell, rise, color_tone):
        # Phase 1: Charge
        # FM Synth + Filtered Noise
        num_frames = int(duration * self.sr)
        if num_frames == 0: return np.array([])
        
        t = np.linspace(0, duration, num_frames)
        
        # 1. Pitch Riser (Exponential)
        # Base freq 100Hz -> rising to 100 + rise*1000
        f_start = 100.0
        f_end = 100.0 + (rise * 2000.0)
        
        # Exp curve
        freqs = f_start * (f_end/f_start)**(t/duration)
        phases = 2 * np.pi * np.cumsum(freqs) / self.sr
        
        # 2. LFO Acceleration (Wobble)
        # LFO rate increases from 2Hz to 20Hz
        lfo_rate_start = 2.0
        lfo_rate_end = 5.0 + (swell * 20.0)
        lfo_freqs = np.linspace(lfo_rate_start, lfo_rate_end, num_frames)
        lfo_phases = 2 * np.pi * np.cumsum(lfo_freqs) / self.sr
        lfo = np.sin(lfo_phases)
        
        # FM Carrier
        carrier = np.sin(phases + lfo * swell * 2.0)
        
        # 3. Noise Layer (Energy Flow)
        noise = self._generate_noise(num_frames, "white")
        # Bandpass sweep
        sos = scipy.signal.butter(2, [0.1, 0.5], btype='band', output='sos')
        filtered_noise = scipy.signal.sosfilt(sos, noise)
        
        # Color Tone (Brightness)
        if color_tone == "Dark":
             carrier = scipy.signal.sosfilt(scipy.signal.butter(2, 0.1, btype='low', output='sos'), carrier)
        elif color_tone == "Bright":
             # Highpass
             carrier = scipy.signal.sosfilt(scipy.signal.butter(2, 0.1, btype='high', output='sos'), carrier)
             
        # Mix
        charge_audio = carrier * 0.6 + filtered_noise * 0.3 * swell
        
        # Amp Envelope (Fade In)
        fade_in = np.linspace(0, 1, num_frames) ** 2
        charge_audio *= fade_in
        
        # Stereo Widening (Haas / Phase)
        # Create Right channel with phase invert or delay
        l = charge_audio
        r = np.roll(charge_audio, int(self.sr * 0.005)) # 5ms delay
        # Fluctuate pan?
        pan_lfo = np.sin(2 * np.pi * 3 * t) # 3Hz panning
        l = l * (0.5 + 0.3 * pan_lfo)
        r = r * (0.5 - 0.3 * pan_lfo)
        
        return np.column_stack((l, r))

    def generate_impact(self, impact, aggression, type_preset):
        # Phase 2: Impact
        # Short burst (0.2s - 0.5s)
        duration = 0.3
        num_frames = int(duration * self.sr)
        t = np.linspace(0, duration, num_frames)
        
        # 1. Kick (Sine drop)
        f_start = 200.0 + (impact * 200.0)
        f_end = 50.0
        freqs = np.linspace(f_start, f_end, num_frames)
        phases = 2 * np.pi * np.cumsum(freqs) / self.sr
        kick = np.sin(phases)
        kick_env = self._generate_envelope(num_frames, 0.005, 0.1)
        kick *= kick_env * impact
        
        # 2. Main Body (Laser/Plasma/Gun)
        body = np.zeros(num_frames)
        if type_preset == "Laser":
            # Fast Sweep Sine/Tri
            f_s = 2000.0
            f_e = 200.0
            freqs = np.linspace(f_s, f_e, num_frames)
            b_phases = 2 * np.pi * np.cumsum(freqs) / self.sr
            body = scipy.signal.sawtooth(b_phases, width=0.5) # Triangle ish
            body_env = self._generate_envelope(num_frames, 0.0, 0.15)
            body *= body_env
            
        elif type_preset == "Plasma":
            # FM Noise
            carrier_f = 150.0
            mod_f = 500.0 + (aggression * 500)
            mod = np.sin(2*np.pi * mod_f * t)
            body = np.sin(2*np.pi * carrier_f * t + mod * 5.0)
            body_env = self._generate_envelope(num_frames, 0.01, 0.2)
            body *= body_env
            
        elif type_preset == "Magic":
            # Chimes/Sparkle
            # Sum of high pitched sines
            for i in range(5):
                f = 1000 + random.random() * 3000
                body += np.sin(2*np.pi*f*t) * random.random()
            body_env = self._generate_envelope(num_frames, 0.05, 0.3)
            body *= body_env
            
        else: # Railgun / Artillery
            # Noise burst
            noise = np.random.uniform(-1, 1, num_frames)
            body = noise * self._generate_envelope(num_frames, 0.0, 0.2)
            
        # 3. Crackle (High freq transient)
        crackle = np.random.uniform(-1, 1, num_frames)
        # Highpass
        sos = scipy.signal.butter(2, 0.6, btype='high', output='sos')
        crackle = scipy.signal.sosfilt(sos, crackle)
        crackle_env = self._generate_envelope(num_frames, 0.0, 0.05)
        crackle *= crackle_env * aggression
        
        # Mix
        mix = kick + body + crackle
        
        # Distortion
        if aggression > 0:
            drive = 1.0 + (aggression * 10.0)
            mix = np.tanh(mix * drive)
            
        # Mono to Stereo
        return np.column_stack((mix, mix))

    def generate_tail(self, seed_audio, tail_length_s):
        # Phase 3: Tail (Reverb/Delay from Impact)
        # seed_audio should be the impact sound (stereo)
        
        if tail_length_s <= 0: return seed_audio
        
        tail_frames = int(tail_length_s * self.sr)
        total_len = len(seed_audio) + tail_frames
        
        # Pad
        padded = np.zeros((total_len, 2))
        padded[:len(seed_audio)] = seed_audio
        
        # Simple Feedback Delay Network or Schroeder Reverb approximation
        # Let's do a simple recursive delay with diffusion (noise)
        
        y = padded.copy()
        
        # 3 Delay lines
        delays = [int(0.05 * self.sr), int(0.07 * self.sr), int(0.11 * self.sr)]
        decays = [0.6, 0.5, 0.4]
        
        for i, d_len in enumerate(delays):
            decay = decays[i]
            # Simple ring buffer effect via slicing? 
            # Vectorized echo adding
            
            # For a tail, we can just add copies
            # This is "Feed Forward" echo, not infinite IIR reverb, but stable
            # To simulate long reverb, we repeat many times with decreasing vol
            
            num_echoes = 8
            for n in range(1, num_echoes):
                delta = d_len * n
                if delta >= total_len: break
                
                vol = decay ** n
                # Add shifted
                start = delta
                end = min(total_len, start + len(seed_audio))
                src_end = end - start
                
                # Ping pong?
                if i % 2 == 0:
                     y[start:end, 0] += seed_audio[:src_end, 0] * vol
                     y[start:end, 1] += seed_audio[:src_end, 1] * vol * 0.8
                else:
                     y[start:end, 0] += seed_audio[:src_end, 0] * vol * 0.8
                     y[start:end, 1] += seed_audio[:src_end, 1] * vol

        # Normalize tail part
        # Fade out
        # Apply release envelope to the whole tail
        fade_out = np.linspace(1, 0, tail_frames)
        y[len(seed_audio):, 0] *= fade_out
        y[len(seed_audio):, 1] *= fade_out

        return y

    def generate(self, params):
        # Unpack params
        # Charge
        p_charge = params.get("charge", {})
        dur_c = p_charge.get("duration", 1.0)
        swell = p_charge.get("swell", 0.5)
        rise = p_charge.get("rise", 0.5)
        color = p_charge.get("color", "Dark")
        
        # Shot
        p_shot = params.get("shot", {})
        impact = p_shot.get("impact", 0.5)
        tail_len = p_shot.get("tail", 1.0)
        aggro = p_shot.get("aggression", 0.5)
        preset_type = p_shot.get("type", "Laser")
        
        # 1. Generate Charge
        if dur_c > 0:
            audio_charge = self.generate_charge(dur_c, swell, rise, color)
        else:
            audio_charge = np.zeros((0, 2))
            
        # 2. Generate Impact
        audio_impact = self.generate_impact(impact, aggro, preset_type)
        
        # 3. Generate Tail (from Impact)
        audio_tail = self.generate_tail(audio_impact, tail_len)
        
        # Mix/Concatenate
        # Charge directly precedes Impact's distinct start?
        # Often Charge builds UP TO the impact.
        # So Concatenate Charge + Tail(which includes Impact at start)
        
        final_len = len(audio_charge) + len(audio_tail)
        final_audio = np.zeros((final_len, 2))
        
        if len(audio_charge) > 0:
            final_audio[:len(audio_charge)] = audio_charge
            
        final_audio[len(audio_charge):] = audio_tail
        
        # Master Limiter
        max_val = np.max(np.abs(final_audio))
        if max_val > 0.0:
            final_audio /= max_val
            final_audio *= 0.95 # Leave headroom
            
        return final_audio

    def get_presets(self):
        return {
            "Laser Gun": {
                "charge": {"duration": 0.5, "swell": 0.2, "rise": 0.8, "color": "Bright"},
                "shot": {"impact": 0.3, "tail": 0.5, "aggression": 0.2, "type": "Laser"}
            },
            "Plasma Cannon": {
                "charge": {"duration": 1.2, "swell": 0.8, "rise": 0.4, "color": "Dark"},
                "shot": {"impact": 0.8, "tail": 1.5, "aggression": 0.6, "type": "Plasma"}
            },
            "Magic Cast": {
                "charge": {"duration": 1.5, "swell": 0.6, "rise": 0.2, "color": "Bright"},
                "shot": {"impact": 0.1, "tail": 2.0, "aggression": 0.0, "type": "Magic"}
            },
            "Railgun": {
                "charge": {"duration": 2.0, "swell": 1.0, "rise": 1.0, "color": "Dark"},
                "shot": {"impact": 1.0, "tail": 0.8, "aggression": 0.9, "type": "Railgun"}
            },
            "Heavy Artillery": {
                "charge": {"duration": 0.2, "swell": 0.0, "rise": 0.0, "color": "Dark"},
                "shot": {"impact": 1.0, "tail": 2.5, "aggression": 0.8, "type": "Artillery"}
            }
        }
