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
        # --- Page 1: Basic & OSC (Group 1: Red-ish) ---
        ParamConfig("SimpleOscType", 0, 3, 0, "波形(0:Sine, 1:Squ, 2:Tri, 3:Saw)", 0, 10, 1),
        ParamConfig("SimpleOscVolume", 0.0, 1.0, 1.0, "SimpleOsc音量", 0.5, 10, 1),
        ParamConfig("OSC:A", 0.0, 1.0, 1.0, "OSC:Aのマスター音量", 1, 10, 1),
        ParamConfig("OSC:B", 0.0, 1.0, 0.0, "OSC:Bのマスター音量", 1.01, 10, 1),
        
        # OSC:A Details
        ParamConfig("OSC:A:Table", 0, 2, 0, "Table(0:Classic,1:Monster,2:Basic)", 1.1, 11, 1),
        ParamConfig("OSC:A:Pos", 0.0, 1.0, 0.0, "Wavetable Position", 1.2, 11, 1),
        ParamConfig("OSC:A:WarpAutoRange", -1.0, 1.0, 0.0, "Warp Auto Depth", 1.21, 11, 1),
        ParamConfig("OSC:A:WarpAutoType", 0, 10, 0, "Warp Auto Type(Img)", 1.22, 11, 1),
        
        ParamConfig("OSC:A:Unison", 0.0, 1.0, 0.0, "Unison Detune", 1.3, 11, 1),
        ParamConfig("OSC:A:DetuneAutoRange", -1.0, 1.0, 0.0, "Detune Auto Depth", 1.31, 11, 1),
        ParamConfig("OSC:A:DetuneAutoType", 0, 10, 0, "Detune Auto Type(Img)", 1.32, 11, 1),
        
        ParamConfig("OSC:A:Semi", -12, 12, 0, "Semi Tone", 1.4, 11, 1),
        ParamConfig("OSC:A:Oct", -3, 3, 0, "Octave", 1.5, 11, 1),
        # ParamConfig("OSC:A:Fine", -100, 100, 0, "Fine Tune (cent)", 1.6, 11, 1), # Simplified
        ParamConfig("OSC:A:Pan", -1.0, 1.0, 0.0, "Pan (-1.0=L, 1.0=R)", 1.7, 11, 1),
        ParamConfig("OSC:A:Phase", 0.0, 1.0, 0.0, "Start Phase (0-1)", 1.8, 11, 1),
        # ParamConfig("OSC:A:Rand", None, None, False, "Random Phase", 1.9, 11, 1), # Simplified
        
        ParamConfig("Duration", 0.1, 10.0, 2.0, "音の長さ(秒)", 2, 1, 1),
        ParamConfig("NoteRange", 0, 127, 60, "音程(MIDI番号)", 3, 1, 1),
        ParamConfig("Voices", 1, 40, 1, "和音数", 4, 1, 1),
        ParamConfig("Chord", None, None, False, "和音構成アルゴリズム", 5, 1, 1),
        ParamConfig("Strum", 0, 500, 0, "発音ズレ(ms)", 6, 1, 1),
        
        # Arpeggio (Group 2: Orange-ish)
        ParamConfig("Arpeggio", None, None, False, "アルペジオ有効化", 7, 2, 1),
        ParamConfig("ArpeggioSplit", 1, 32, 4, "アルペジオ分割数", 8, 2, 1),
        
        # Voice Details (Group 6: Blue-ish)
        ParamConfig("RouteVoiceVolume", 0.0, 1.0, 1.0, "Root音量(0-1)", 9, 6, 1),
        ParamConfig("MultiVoiceVolume", 0.0, 1.0, 0.5, "Chord音量(0-1)", 10, 6, 1),
        ParamConfig("DetuneVoice", 0, 8, 0, "Detune数/Note", 11, 6, 1),
        ParamConfig("DetuneRange", 0, 50, 5, "Detune幅(cent)", 12, 6, 1),
        ParamConfig("DetuneVolume", 0.0, 1.0, 0.5, "Detune音量比", 13, 6, 1),

        # --- Page 2: LFOs ---
        # LFO-Pitch (Group 7: Magenta/Purple)
        ParamConfig("LFO_P_Range", 0, 7200, 0, "Pitch揺れ幅(cent)", 2000, 7, 2),
        ParamConfig("LFO_P_Type", 0, 4, 0, "Type(0:Sine,1:Tri,2:Saw,3:Sqr,4:Rnd)", 2001, 7, 2),
        ParamConfig("LFO_P_Speed", 0, 30000, 5, "Pitch速度(Hz)", 2002, 7, 2),
        ParamConfig("LFO_P_Shape", 0, 100, 50, "Shape(Duty/Skew %)", 2003, 7, 2),

        # LFO-Volume (Group 8: Lime/Green)
        ParamConfig("LFO_V_Range", 0, 100, 0, "Vol揺れ幅(%)", 2100, 8, 2),
        ParamConfig("LFO_V_Type", 0, 4, 0, "Type(0:Sine,1:Tri,2:Saw,3:Sqr,4:Rnd)", 2101, 8, 2),
        ParamConfig("LFO_V_Speed", 0, 30000, 5, "Vol速度(Hz)", 2102, 8, 2),
        ParamConfig("LFO_V_Shape", 0, 100, 50, "Shape(Duty/Skew %)", 2103, 8, 2),

        # LFO-Pan (Group 9: Teal/Cyan)
        ParamConfig("LFO_Pan_Range", 0, 100, 0, "Pan揺れ幅(%)", 2200, 9, 2),
        ParamConfig("LFO_Pan_Type", 0, 4, 0, "Type(0:Sine,1:Tri,2:Saw,3:Sqr,4:Rnd)", 2201, 9, 2),
        ParamConfig("LFO_Pan_Speed", 0, 30000, 5, "Pan速度(Hz)", 2202, 9, 2),
        ParamConfig("LFO_Pan_Shape", 0, 100, 50, "Shape(Duty/Skew %)", 2203, 9, 2),

        # --- OSC:B (Page 2 Hidden/Back) (Group 30: Cyan) ---
        ParamConfig("OSC:B:Table", 0, 2, 0, "Table(0:Classic,1:Monster,2:Basic)", 2501, 30, 2),
        ParamConfig("OSC:B:Pos", 0.0, 1.0, 0.0, "Wavetable Position", 2502, 30, 2),
        ParamConfig("OSC:B:WarpAutoRange", -1.0, 1.0, 0.0, "Warp Auto Depth", 2503, 30, 2),
        ParamConfig("OSC:B:WarpAutoType", 0, 10, 0, "Warp Auto Type(Img)", 2504, 30, 2),
        
        ParamConfig("OSC:B:Unison", 0.0, 1.0, 0.0, "Unison Detune", 2505, 30, 2),
        ParamConfig("OSC:B:DetuneAutoRange", -1.0, 1.0, 0.0, "Detune Auto Depth", 2506, 30, 2),
        ParamConfig("OSC:B:DetuneAutoType", 0, 10, 0, "Detune Auto Type(Img)", 2507, 30, 2),
        
        ParamConfig("OSC:B:Semi", -12, 12, 0, "Semi Tone", 2508, 30, 2),
        ParamConfig("OSC:B:Oct", -3, 3, 0, "Octave", 2509, 30, 2),
        ParamConfig("OSC:B:Pan", -1.0, 1.0, 0.0, "Pan (-1.0=L, 1.0=R)", 2510, 30, 2),
        ParamConfig("OSC:B:Phase", 0.0, 1.0, 0.0, "Start Phase (0-1)", 2511, 30, 2),

        # --- Page 3: Filters (New) (Group 20: Golden) ---
        # LPF
        ParamConfig("LPF_Enable", None, None, False, "LPF有効化", 3000, 20, 3),
        ParamConfig("LPF_Cutoff", 20.0, 20000.0, 20000.0, "LPF基本カットオフ(Hz)", 3001, 20, 3),
        ParamConfig("LPF_Resonance", 0.0, 1.0, 0.0, "LPFレゾナンス(Q)", 3002, 20, 3),
        ParamConfig("LPF_AutoRange", -20000.0, 20000.0, 0.0, "LPF Cutoff Auto深さ(Hz)", 3003, 20, 3),
        ParamConfig("LPF_AutoType", 0, 10, 0, "LPF Auto Type(0:Flat,1:Lin,2:Exp,3+:Img)", 3004, 20, 3),
        ParamConfig("LPF_ResAutoRange", -1.0, 1.0, 0.0, "LPF Res Auto深さ", 3005, 20, 3),
        ParamConfig("LPF_ResAutoType", 0, 10, 0, "LPF Res Auto Type(Img)", 3006, 20, 3),
        
        # HPF
        ParamConfig("HPF_Enable", None, None, False, "HPF有効化", 3100, 21, 3),
        ParamConfig("HPF_Cutoff", 20.0, 20000.0, 20.0, "HPF基本カットオフ(Hz)", 3101, 21, 3),
        ParamConfig("HPF_Resonance", 0.0, 1.0, 0.0, "HPFレゾナンス(Q)", 3102, 21, 3),
        ParamConfig("HPF_AutoRange", -20000.0, 20000.0, 0.0, "HPF Cutoff Auto深さ(Hz)", 3103, 21, 3),
        ParamConfig("HPF_AutoType", 0, 10, 0, "HPF Auto Type(Img)", 3104, 21, 3),
        ParamConfig("HPF_ResAutoRange", -1.0, 1.0, 0.0, "HPF Res Auto深さ", 3105, 21, 3),
        ParamConfig("HPF_ResAutoType", 0, 10, 0, "HPF Res Auto Type(Img)", 3106, 21, 3),

        # Filter Env
        ParamConfig("Filter_EnvAmt", -1.0, 1.0, 0.0, "Env->Cutoff 適用量", 3200, 22, 3),
        ParamConfig("Filter_Attack", 0.0, 2000.0, 10.0, "Filter Env Attack(ms)", 3201, 22, 3),
        ParamConfig("Filter_Decay", 0.0, 2000.0, 100.0, "Filter Env Decay(ms)", 3202, 22, 3),
        ParamConfig("Filter_Sustain", 0.0, 1.0, 0.5, "Filter Env Sustain(0-1)", 3203, 22, 3),
        ParamConfig("Filter_Release", 0.0, 5000.0, 300.0, "Filter Env Release(ms)", 3204, 22, 3),

        # --- Page 4: Effects (Moved from Page 3) ---
        ParamConfig("DistortionGain", 0.0, 1.0, 0.0, "ディストーションの歪み量", 4001, "Distortion", 4),
        ParamConfig("DistortionFeed", 0.0, 1.0, 0.0, "ディストーションのフィードバック(Tone)", 4002, "Distortion", 4), 
        ParamConfig("DistortionWet", 0.0, 1.0, 0.0, "ディストーションの原音Mix比率", 4003, "Distortion", 4),

        ParamConfig("PhaserDepth", 0.0, 1.0, 0.0, "フェーザーの深さ", 4101, "Phaser", 4),
        ParamConfig("PhaserSpeed", 0.1, 20.0, 1.0, "フェーザーの速度(Hz)", 4102, "Phaser", 4),
        ParamConfig("PhaserWet", 0.0, 1.0, 0.0, "フェーザーのMix比率", 4103, "Phaser", 4),

        ParamConfig("ReverbTime", 0.1, 10.0, 0.0, "リバーブの長さ(秒)", 4201, "Reverb", 4),
        ParamConfig("ReverbSpread", 0.0, 1.0, 0.0, "リバーブの広がり", 4202, "Reverb", 4),
        ParamConfig("ReverbWet", 0.0, 1.0, 0.0, "リバーブのMix比率", 4203, "Reverb", 4),

        ParamConfig("DelayTime", 0.01, 1.0, 0.0, "ディレイタイム(秒)", 4301, "Delay", 4),
        ParamConfig("DelayFeedback", 0.0, 0.95, 0.0, "ディレイの繰り返し量", 4302, "Delay", 4),
        ParamConfig("DelayWet", 0.0, 1.0, 0.0, "ディレイのMix比率", 4303, "Delay", 4),

        ParamConfig("SpreadRange", 0.0, 1.0, 0.0, "空間の広がり幅", 4401, "Spread", 4),
        ParamConfig("SpreadDensity", 0.0, 1.0, 0.0, "空間の密度(Detune Spread)", 4402, "Spread", 4),
        ParamConfig("SpreadWet", 0.0, 1.0, 0.0, "空間効果のMix比率", 4403, "Spread", 4),

        # --- Page 5: Advanced (Moved from Page 4) ---
        # Amp Envelope (Most important advanced param)
        ParamConfig("AmpAttack", 0.0, 2000.0, 10.0, "アタック時間(ms)", 5001, "Envelope", 5),
        ParamConfig("AmpDecay", 0.0, 2000.0, 100.0, "ディケイ時間(ms)", 5002, "Envelope", 5),
        ParamConfig("AmpSustain", 0, 127, 64, "サスティンレベル", 5003, "Envelope", 5),
        ParamConfig("AmpRelease", 0.0, 5000.0, 300.0, "リリース時間(ms)", 5004, "Envelope", 5),
        
        ParamConfig("Portament", 0.0, 500.0, 0.0, "ポルタメント時間(ms)", 5101, "Pitch", 5),
        ParamConfig("PitchRange", -2400.0, 2400.0, 0.0, "ピッチ変動幅(cent)", 5102, "Pitch", 5),
        ParamConfig("PitchType", 0, 2, 0, "Type(0:Flat,1:Lin,2:Exp,3+:Img)", 5103, "Pitch", 5),
        ParamConfig("PitchCurve", 0, 127, 64, "カーブ/時間の粘り", 5104, "Pitch", 5),
        
        ParamConfig("Pan", 0, 127, 64, "パン(0=L, 64=C, 127=R)", 5201, "Stereo", 5),
        ParamConfig("MasterPan", 0, 127, 64, "全体パン補正", 5202, "Stereo", 5),
        ParamConfig("Normalize", None, None, True, "音量正規化", 5210, 10, 5),
        
        ParamConfig("FadeOutTime", 0.0, 1.0, 0.0, "Fade Out Time (0-1)", 5211, 10, 5),
        ParamConfig("FadeOutCurve", 0.0, 1.0, 0.5, "Fade Out Curve (0=St, 1=Sl)", 5212, 10, 5),
        
        ParamConfig("MasterVolume", 0.0, 1.0, 0.5, "全体音量(0.1-1.0)", 5205, 10, 5),
    ]
    
    @classmethod
    def get_sorted_params(cls):
        return sorted(cls.DEFINITIONS, key=lambda x: x.order)

    @classmethod
    def get_param_names(cls):
        return [p.name for p in cls.get_sorted_params()]
