import random

class ChordData:
    """
    Enhanced chord definitions with multiple voicing patterns.
    Includes Open voicing and Minus-direction (Sub) variations.
   
    """
    
    # Each chord key now contains a LIST of interval patterns.
    # Logic will pick one randomly during generation.
    CHORDS = {
        # --- Basic Triads ---
        "Maj": [
            [0, 4, 7],          # Standard
            [0, 4, -5],         # Minus direction (5th dropped)
            [0, 7, 16],         # Open voice (10th spread)
            [-12, 0, 4, 7],     # Sub-root add
            [0, 4, 7, 12, 16]   # Wide stack
        ],
        "Min": [
            [0, 3, 7],          # Standard
            [0, 3, -5],         # Minus direction
            [0, 7, 15],         # Open voice (Min 10th)
            [-12, 0, 3, 7],     # Sub-root add
            [-12, -5, 0, 3]     # Deep dark cluster
        ],
        "Dim": [
            [0, 3, 6], 
            [0, 6, 15],         # Open
            [-12, 0, 3, 6]      # Tension sub
        ],
        "Aug": [
            [0, 4, 8],
            [0, 8, 16],         # Super open
            [-12, 0, 4, 8]
        ],

        # --- 7th & Color Chords ---
        "Maj7": [
            [0, 4, 7, 11],
            [0, 7, 11, 16],     # Drop 2 style
            [-12, 0, 7, 11, 16],# Cinematic spread
            [0, 11, 16, 19]     # High airy
        ],
        "Min7": [
            [0, 3, 7, 10],
            [0, 7, 10, 15],     # Open
            [-12, 0, 3, 7, 10], # Deep jazz
            [-24, -12, 0, 10]   # Sub heavy
        ],
        "Dom7": [
            [0, 4, 7, 10],
            [0, 10, 16],        # Shell voicing
            [-12, 0, 4, 10]     # Growl bass
        ],

        # --- Special SFX / Exotic ---
        "Power": [
            [0, 7],
            [0, 7, 12],
            [-12, 0, 7],        # Heavy sub power
            [-24, -12, 0, 7, 12, 19] # Mega stack
        ],
        "Space": [
            [0, 3, 7, 14, 18],  # Original
            [-12, 0, 7, 14, 21],# Quintal (Stacked 5ths)
            [0, 11, 22, 25]     # Dissonant shimmer
        ],
        "Dream": [
            [0, 4, 6, 11],
            [-12, 0, 6, 11, 18],# Deep dream
            [0, 6, 11, 13]      # Cluster dream
        ],
        "Void": [
            [0, 5, 11, 15],
            [-24, 0, 11, 17],   # Cinematic void
            [-12, -1, 0, 1]     # Error cluster
        ]
    }
    
    # Note names for formatted output (Cn3, Fs4 etc)
    NOTE_NAMES = ["Cn", "Cs", "Dn", "Ds", "En", "Fn", "Fs", "Gn", "Gs", "An", "As", "Bn"]

    @classmethod
    def get_chord_names(cls):
        """Returns all available chord names."""
        return list(cls.CHORDS.keys())

    @classmethod
    def get_random_pattern(cls, chord_name):
        """
        Picks a random interval pattern for the given chord name.
        If the chord name is not found, returns a basic root [0].
        """
        patterns = cls.CHORDS.get(chord_name, [[0]])
        return random.choice(patterns)