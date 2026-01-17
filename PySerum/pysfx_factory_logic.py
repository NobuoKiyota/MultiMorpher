import random

class GenerationLogic:
    """Music theory and random generation recipes for PyQuartz SFX Factory."""
    
    @staticmethod
    def get_chord_notes(root_note, num_voices, is_chord_mode):
        """
        Generates chord notes based on ChordData.
        Returns: (list_of_notes, chord_name_str)
        """
        from pysfx_chord_data import ChordData
        
        if isinstance(root_note, list) or isinstance(root_note, tuple):
             if len(root_note) > 0: root_note = root_note[0]
        root_note = int(root_note)

        if not is_chord_mode or num_voices <= 1: 
            if num_voices == 1:
                return [root_note], "Single"
            else:
                return [root_note + random.randint(-1, 1) for _ in range(num_voices)], "Cluster"
        
        # Select a random chord type
        chord_name = random.choice(ChordData.get_chord_names())
        intervals = ChordData.get_random_pattern(chord_name)
        
        # Safety check for intervals structure
        if intervals and isinstance(intervals[0], list):
             intervals = intervals[0]
             
        notes = []
        for i in range(num_voices):
            interval = intervals[i % len(intervals)]
            
            # Double safety: verify interval is int
            if isinstance(interval, list):
                interval = interval[0] 
            
            interval = int(interval)
            
            octave_offset = (i // len(intervals)) * 12
            notes.append(root_note + interval + octave_offset)
            
        return notes, chord_name

    @staticmethod
    def get_note_name(midi_note):
        """
        Format: name + octave. 
        User Req: n=Natural, s=Sharp. e.g. Cn3, Fs4.
        C3 = 60 assumed? Or C4=60? 
        Let's use C3=60 standard (Yamaha is C3=60, Roland C4=60).
        Let's stick to C3 = 60 for "Cn3".
        """
        from pysfx_chord_data import ChordData
        midi_note = int(round(midi_note))
        note_idx = midi_note % 12
        octave = (midi_note // 12) - 2 # 60 -> 5 - 2 = 3 (Cn3)
        
        name = ChordData.NOTE_NAMES[note_idx]
        return f"{name}{octave}"

    @staticmethod
    def get_pitch_curve(range_cent, num_points):
        """Generates a list of points for pitch automation (AutomationLane)."""
        if range_cent == 0: return [(0.0, 0.0), (1.0, 0.0)]
        points = []
        for i in range(num_points):
            t = i / (num_points - 1)
            # Randomize middle points, keep start/end at zero offset
            val = random.uniform(-1.0, 1.0) if 0 < i < num_points - 1 else 0.0
            points.append((t, val))
        return points