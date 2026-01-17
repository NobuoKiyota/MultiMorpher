class ParamConfig:
    def __init__(self, name, v_min, v_max, default, desc, order, group=0):
        self.name = name
        self.min = v_min
        self.max = v_max
        self.default = default
        self.desc = desc
        self.order = order
        self.group = group

class PySFXParams:
    """
    Centralized Parameter Management for PyQuartz SFX Factory.
    Edit 'order' to change the display and log sequence.
    Edit 'group' to change color (1-32).
    """
    DEFINITIONS = [
        # Basic (Group 1: Red-ish)
        ParamConfig("Duration", 0.1, 10.0, 2.0, "音の長さ(秒)", 1, 1),
        ParamConfig("NoteRange", 0, 127, 60, "音程(MIDI番号)", 0, 1),
        ParamConfig("Voices", 1, 8, 1, "和音数", 2, 1),
        ParamConfig("Chord", None, None, False, "和音構成アルゴリズム", 3, 1),
        ParamConfig("Strum", 0, 500, 0, "発音ズレ(ms)", 6, 1),
        
        # Arpeggio (Group 2: Orange-ish)
        ParamConfig("Arpeggio", None, None, False, "アルペジオ有効化", 4, 2),
        ParamConfig("ArpeggioSplit", 1, 32, 4, "アルペジオ分割数", 5, 2),
        
        # Envelope (Group 3: Yellow-ish)
        ParamConfig("AmpAttack", 0, 5000, 10, "アタック(ms)", 1000, 3),
        ParamConfig("AmpDecay", 0, 5000, 100, "ディケイ(ms)", 1001, 3),
        ParamConfig("AmpSustain", 0, 127, 100, "サスティン(0-127)", 1002, 3),
        ParamConfig("AmpRelease", 0, 10000, 200, "リリース(ms)", 1003, 3),
        
        # Pitch / Glide (Group 4: Green-ish)
        ParamConfig("Portament", 0, 1000, 0, "ポルタメント(ms)", 200, 4),
        ParamConfig("PitchRange", 0, 7200, 0, "ピッチ可変域(cent)", 210, 4),
        ParamConfig("PitchCurve", 0, 127, 64, "ピッチ曲線(64=Linear)", 220, 4),
        
        # Stereo / Mix (Group 5: Cyan-ish)
        ParamConfig("Pan", 0, 127, 64, "基本定位(0-127)", 1501, 5),
        ParamConfig("MasterPan", 0, 127, 64, "全体定位(Master)", 1502, 5),
        ParamConfig("Normalize", None, None, True, "最大化(Normalize)", 1500, 5),
        
        # Advanced Voice (Group 6: Blue-ish)
        ParamConfig("RouteVoiceVolume", 0.0, 1.0, 1.0, "Root音量(0-1)", 7, 6),
        ParamConfig("MultiVoiceVolume", 0.0, 1.0, 0.5, "Chord音量(0-1)", 8, 6),
        ParamConfig("DetuneVoice", 0, 8, 0, "Detune数/Note", 9, 6),
        ParamConfig("DetuneRange", 0, 50, 5, "Detune幅(cent)", 10, 6),
        ParamConfig("DetuneVolume", 0.0, 1.0, 0.5, "Detune音量比", 11, 6),
    ]
    
    @classmethod
    def get_sorted_params(cls):
        return sorted(cls.DEFINITIONS, key=lambda x: x.order)

    @classmethod
    def get_param_names(cls):
        return [p.name for p in cls.get_sorted_params()]
