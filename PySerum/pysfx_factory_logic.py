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
    def get_pitch_curve(range_cent, num_points, curve_val=64, curve_type=0):
        """
        Generates pitch automation points.
        range_cent: Scale factor (used by caller, logic returns 0.0-1.0 or -1.0-1.0 normalized)
        curve_val: 0-127 (Control time-warping/curvature)
        curve_type: 0=Flat, 1=Linear, 2=Exp, 3+=Image
        """
        if range_cent == 0 or curve_type == 0:
            return [(0.0, 0.0), (1.0, 0.0)]

        # Time Warping Power
        # 0 -> 0.1 (Slow start), 64 -> 1.0 (Linear), 127 -> 10.0 (Fast start)
        # Flip logic: value low (0) -> Log curve (fast rise?), value high -> Exp curve (slow rise)
        # Let's map: 0..127 -> Power 0.1 .. 10.0
        power = 10.0 ** ((curve_val - 64) / 40.0) # 40 divisor gives softer range (approx 0.02 - 40)
        
        points = []
        
        # Prepare Image Tracer if needed
        tracer_curve = None
        if curve_type >= 3:
            from pysfx_image_tracer import ImageTracer
            tracer = ImageTracer()
            idx = curve_type - 3
            tracer_curve = tracer.get_curve(idx, resolution=1000)

        for i in range(num_points):
            t = i / (num_points - 1)
            
            # Apply Time Warping to t
            t_warped = t ** power
            
            if curve_type == 1: # Linear Rise
                # Simply 0.0 to 1.0 (warped in time)
                val = t_warped
                
            elif curve_type == 2: # Exponential
                # Already warped t is exponential-ish if power != 1
                # But let's apply a curve function on top? 
                # Actually Time Warping IS the curvature control for simple A->B.
                val = t_warped
                
            elif curve_type >= 3: # Image
                # Sample from tracer_curve at t_warped
                # Curve is 0.0-1.0
                sample_idx = int(t_warped * (len(tracer_curve) - 1))
                val = tracer_curve[sample_idx]
                
            else:
                val = 0.0

            # Map 0.0-1.0 to -1.0 to 1.0?
            # Or keep 0.0-1.0 and let Range decide?
            # Existing random logic returned -1.0 to 1.0.
            # If we return 0.0 to 1.0, range=1200 means 0->1200.
            # If random was -1 to 1, range=1200 means -1200->1200? Or range was max amp?
            # Let's assume user wants full control via Range.
            # If Image is 0-1, output is 0-Range.
            # To center, user can draw line at 0.5.
            
            # Correction: To make "Flat" (Type 0) work naturally with Images,
            # Images should probably be centered around 0.5 if they are bipolar?
            # But PNG 0-1 is absolute.
            # Let's stick to returning 0.0 to 1.0.
            # BUT, the caller: `scaled_points = [(t, v * range_semis) for t, v in points]`
            # If range_semis = 12 (1 oct). 1.0 -> +1 oct. 0.0 -> 0 oct.
            # This implies "Unipolar" automation.
            # If user wants "Bipolar" (LFO style), they need to offset?
            # Let's assume Unipolar for now as it's easier to verify.
            
            points.append((t, val))
            
        return points