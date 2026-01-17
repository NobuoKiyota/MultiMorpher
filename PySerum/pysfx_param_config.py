class ParamConfig:
    def __init__(self, name, v_min, v_max, default, desc, order, group=0, page=1):
        self.name = name
        self.min = v_min
        self.max = v_max
        self.default = default
        self.desc = desc
        self.order = order
        self.group = group
        self.page = page

class PySFXParams:
    """
    Centralized Parameter Management for PyQuartz SFX Factory.
    Edit 'order' to change the display and log sequence.
    Edit 'group' to change color (1-32).
    Edit 'page' to change GUI tab (1, 2, 3...).
    """
    DEFINITIONS = [
        # Basic (Group 1: Red-ish) - Page 1
        ParamConfig("SimpleOscType", 0, 3, 0, "波形(0:Sine, 1:Squ, 2:Tri, 3:Saw)", 0, 10, 1),
        
        
        ParamConfig("Duration", 0.1, 10.0, 2.0, "音の長さ(秒)", 2, 1, 1),
        ParamConfig("NoteRange", 0, 127, 60, "音程(MIDI番号)", 3, 1, 1),
        ParamConfig("Voices", 1, 8, 1, "和音数", 4, 1, 1),
        ParamConfig("Chord", None, None, False, "和音構成アルゴリズム", 5, 1, 1),
        ParamConfig("Strum", 0, 500, 0, "発音ズレ(ms)", 6, 1, 1),
        
        # Arpeggio (Group 2: Orange-ish) - Page 1
        ParamConfig("Arpeggio", None, None, False, "アルペジオ有効化", 7, 2, 1),
        ParamConfig("ArpeggioSplit", 1, 32, 4, "アルペジオ分割数", 8, 2, 1),
        
        # Advanced Voice (Group 6: Blue-ish) - Page 1
        ParamConfig("RouteVoiceVolume", 0.0, 1.0, 1.0, "Root音量(0-1)", 9, 6, 1),
        ParamConfig("MultiVoiceVolume", 0.0, 1.0, 0.5, "Chord音量(0-1)", 10, 6, 1),
        ParamConfig("DetuneVoice", 0, 8, 0, "Detune数/Note", 11, 6, 1),
        ParamConfig("DetuneRange", 0, 50, 5, "Detune幅(cent)", 12, 6, 1),
        ParamConfig("DetuneVolume", 0.0, 1.0, 0.5, "Detune音量比", 13, 6, 1),

        # LFO-Pitch (Group 7: Magenta/Purple) - Page 2
        ParamConfig("LFO_P_Range", 0, 7200, 0, "Pitch揺れ幅(cent)", 1700, 7, 2),
        ParamConfig("LFO_P_Type", 0, 4, 0, "Type(0:Sine,1:Tri,2:Saw,3:Sqr,4:Rnd)", 1701, 7, 2),
        ParamConfig("LFO_P_Speed", 0, 30000, 5, "Pitch速度(Hz)", 1702, 7, 2),
        ParamConfig("LFO_P_Shape", 0, 100, 50, "Shape(Duty/Skew %)", 1703, 7, 2),

        # LFO-Volume (Group 8: Lime/Green) - Page 2
        ParamConfig("LFO_V_Range", 0, 100, 0, "Vol揺れ幅(%)", 1800, 8, 2),
        ParamConfig("LFO_V_Type", 0, 4, 0, "Type(0:Sine,1:Tri,2:Saw,3:Sqr,4:Rnd)", 1801, 8, 2),
        ParamConfig("LFO_V_Speed", 0, 30000, 5, "Vol速度(Hz)", 1802, 8, 2),
        ParamConfig("LFO_V_Shape", 0, 100, 50, "Shape(Duty/Skew %)", 1803, 8, 2),

        # LFO-Pan (Group 9: Teal/Cyan) - Page 3 (Placeholder as requested)
        ParamConfig("LFO_Pan_Range", 0, 100, 0, "Pan揺れ幅(%)", 1900, 9, 2),
        ParamConfig("LFO_Pan_Type", 0, 4, 0, "Type(0:Sine,1:Tri,2:Saw,3:Sqr,4:Rnd)", 1901, 9, 2),
        ParamConfig("LFO_Pan_Speed", 0, 30000, 5, "Pan速度(Hz)", 1902, 9, 2),
        ParamConfig("LFO_Pan_Shape", 0, 100, 50, "Shape(Duty/Skew %)", 1903, 9, 2),

        # --- Page 3: Effects (New) ---
        ParamConfig("DistortionGain", 0.0, 1.0, 0.0, "ディストーションの歪み量", 3001, "Distortion", 3),
        ParamConfig("DistortionFeed", 0.0, 1.0, 0.0, "ディストーションのフィードバック(Tone)", 3002, "Distortion", 3), 
        ParamConfig("DistortionWet", 0.0, 1.0, 0.0, "ディストーションの原音Mix比率", 3003, "Distortion", 3),

        ParamConfig("PhaserDepth", 0.0, 1.0, 0.0, "フェーザーの深さ", 3101, "Phaser", 3),
        ParamConfig("PhaserSpeed", 0.1, 20.0, 1.0, "フェーザーの速度(Hz)", 3102, "Phaser", 3),
        ParamConfig("PhaserWet", 0.0, 1.0, 0.0, "フェーザーのMix比率", 3103, "Phaser", 3),

        ParamConfig("ReverbTime", 0.1, 10.0, 0.0, "リバーブの長さ(秒)", 3201, "Reverb", 3),
        ParamConfig("ReverbSpread", 0.0, 1.0, 0.0, "リバーブの広がり", 3202, "Reverb", 3),
        ParamConfig("ReverbWet", 0.0, 1.0, 0.0, "リバーブのMix比率", 3203, "Reverb", 3),

        ParamConfig("DelayTime", 0.01, 1.0, 0.0, "ディレイタイム(秒)", 3301, "Delay", 3),
        ParamConfig("DelayFeedback", 0.0, 0.95, 0.0, "ディレイの繰り返し量", 3302, "Delay", 3),
        ParamConfig("DelayWet", 0.0, 1.0, 0.0, "ディレイのMix比率", 3303, "Delay", 3),

        ParamConfig("SpreadRange", 0.0, 1.0, 0.0, "空間の広がり幅", 3401, "Spread", 3),
        ParamConfig("SpreadDensity", 0.0, 1.0, 0.0, "空間の密度(Detune Spread)", 3402, "Spread", 3),
        ParamConfig("SpreadWet", 0.0, 1.0, 0.0, "空間効果のMix比率", 3403, "Spread", 3),

        # --- Page 4: Advanced (Moved from Page 3) ---
        ParamConfig("AmpAttack", 0.0, 2000.0, 10.0, "アタック時間(ms)", 4001, "Envelope", 4),
        ParamConfig("AmpDecay", 0.0, 2000.0, 100.0, "ディケイ時間(ms)", 4002, "Envelope", 4),
        ParamConfig("AmpSustain", 0, 127, 64, "サスティンレベル", 4003, "Envelope", 4),
        ParamConfig("AmpRelease", 0.0, 5000.0, 300.0, "リリース時間(ms)", 4004, "Envelope", 4),
        
        ParamConfig("Portament", 0.0, 500.0, 0.0, "ポルタメント時間(ms)", 4101, "Pitch", 4),
        ParamConfig("PitchRange", -2400.0, 2400.0, 0.0, "ピッチ変動幅(cent)", 4102, "Pitch", 4),
        ParamConfig("PitchCurve", 0, 127, 64, "ピッチカーブ(>64:Expo <64:Log)", 4103, "Pitch", 4),
        
        ParamConfig("Pan", 0, 127, 64, "パン(0=L, 64=C, 127=R)", 4201, "Stereo", 4),
        ParamConfig("MasterPan", 0, 127, 64, "全体パン補正", 4202, "Stereo", 4),
        ParamConfig("Normalize", None, None, True, "音量正規化", 4210, 10, 4),
        ParamConfig("MasterVolume", 0.0, 1.0, 0.5, "全体音量(0.1-1.0)", 4205, 10, 4),
    ]
    
    @classmethod
    def get_sorted_params(cls):
        return sorted(cls.DEFINITIONS, key=lambda x: x.order)

    @classmethod
    def get_param_names(cls):
        return [p.name for p in cls.get_sorted_params()]
