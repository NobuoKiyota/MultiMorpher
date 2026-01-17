class ChordData:
    """
    Chord definitions relative to root (0).
    Using standard intervals.
    """
    CHORDS = {
        # Basic Triads
        "Maj": [0, 4, 7],
        "Min": [0, 3, 7],
        "Dim": [0, 3, 6],
        "Aug": [0, 4, 8],
        "Sus4": [0, 5, 7],
        "Sus2": [0, 2, 7],
        
        # 7th Chords
        "Maj7": [0, 4, 7, 11],
        "Min7": [0, 3, 7, 10],
        "Dom7": [0, 4, 7, 10],
        "Dim7": [0, 3, 6, 9],
        "HalfDim7": [0, 3, 6, 10],
        "MinMaj7": [0, 3, 7, 11],
        
        # Extended
        "Maj9": [0, 4, 7, 11, 14],
        "Min9": [0, 3, 7, 10, 14],
        "Add9": [0, 4, 7, 14],
        "6": [0, 4, 7, 9],
        "Min6": [0, 3, 7, 9],
        
        # Power
        "5": [0, 7],
        
        # Exotic / clusters (optional)
        "Dream": [0, 4, 6, 11],
        "Space": [0, 3, 7, 14, 18],
    }
    
    # Note names for formatted output (Cn3, Fs4 etc)
    NOTE_NAMES = ["Cn", "Cs", "Dn", "Ds", "En", "Fn", "Fs", "Gn", "Gs", "An", "As", "Bn"]

    @classmethod
    def get_chord_names(cls):
        return list(cls.CHORDS.keys())
