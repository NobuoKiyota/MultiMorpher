
"""
PyQuartz SFX Factory - Parameter Documentation
Detailed descriptions for GUI hover tooltips.
Structure:
    "ParamName": {
        "desc": "Basic explanation (Normal Text)",
        "effect": "Technical details / Signal flow (Bold/White)",
        "guide": "Min/Max and usage tips (Red/Warning/Emphasis)",
    }
Note: Internal newlines are removed for compact display in GUI.
"""

PARAM_DOCS = {
    # --- Basic ---
    "SimpleOscType": {
        "desc": "Selects the fundamental waveform shape for the primary oscillator.",
        "effect": "0=Sine(Pure), 1=Square(Hollow), 2=Tri(Soft), 3=Saw(Bright). Changes basic timbre.",
        "guide": "Start with Sine/Tri for soft SFX, Saw/Sqr for Retro/Aggressive sounds." 
    },
    "MasterVolume": {
        "desc": "Controls the global output gain of the engine before clipping protection.",
        "effect": "Default 0.5. Higher values increase loudness but reduce headroom.",
        "guide": "Keep around 0.5-0.8. If 'Normalization' is ON, this affects pre-norm signal level."
    },
    "Duration": {
        "desc": "生成されるSFXの全長(秒)を設定します。",
        "effect": "値が大きいほどファイルサイズが増加します。",
        "guide": "通常は 1.0〜3.0秒 が推奨です。長すぎると生成に時間がかかります。"
    },
    "NoteRange": {
        "desc": "基準となる音程(MIDIノート番号)です。(60=Center C)",
        "effect": "生成される音の高さのベースとなります。",
        "guide": "低い値(20-40)は重低音、高い値(80-100)はキラキラした音になります。"
    },
    "Voices": {
        "desc": "ユニゾン(重ねる音)の数を指定します。",
        "effect": "値が大きいほど厚みのある音になりますが、処理が重くなります。",
        "guide": "SFX用途なら 1〜4 で十分です。Cord機能を使う場合は和音の構成音数になります。"
    },
    "Chord": {
        "desc": "和音生成モードを有効化します。",
        "effect": "Voices設定に基づいて、音楽的な和音(メジャー/マイナー等)を自動構成します。",
        "guide": "ONにするとVoicesが自動的に和音構成音に割り当てられます。"
    },
    "Strum": {
        "desc": "発音タイミングのズレ(ストラム)を設定します。",
        "effect": "ギターのストロークのように、各ボイスの発音を時間差で遅らせます。",
        "guide": "0msで同時発音。50ms〜200msでバラつきのある有機的な響きになります。"
    },

    # --- Arpeggio ---
    "Arpeggio": {
        "desc": "アルペジオ(分散和音)モードを有効化します。",
        "effect": "和音を一度に鳴らさず、高速に上昇/下降させます。",
        "guide": "レーザー音やUI音(ピロリン♪)を作るのに最適です。"
    },
    "ArpeggioSplit": {
        "desc": "アルペジオの分割(ステップ)数です。",
        "effect": "1ノートを何分割してピッチを変化させるかを決定します。",
        "guide": "値が大きいほど滑らかに、小さいほど階段状の変化が目立ちます。"
    },

    # --- Envelope ---
    "AmpAttack": {
        "desc": "音が最大音量に達するまでの時間(ms)です。",
        "effect": "立ち上がりの鋭さを制御します。",
        "guide": "0ms:打撃音(ドン！) / 500ms~:下降音(フワッ...)"
    },
    "AmpDecay": {
        "desc": "最大音量からサスティンレベルに下がるまでの時間(ms)です。",
        "effect": "アタック後の減衰感を制御します。",
        "guide": "短くすると歯切れの良い音になります。"
    },
    "AmpSustain": {
        "desc": "音が持続する時の音量レベル(0-127)です。",
        "effect": "鍵盤を押している間の音量を決定します。",
        "guide": "127で減衰なし。0にするとDecay後に無音になります(パーカッション的)。"
    },
    "AmpRelease": {
        "desc": "音が消えるまでの余韻の時間(ms)です。",
        "effect": "ノートオフ後の響きを制御します。",
        "guide": "長くするとリバーブがかかったような残響感が残ります。"
    },

    # --- Pitch ---
    "Portament": {
        "desc": "音程間の滑らかさ(ポルタメント)の時間(ms)です。",
        "effect": "ピッチが変化する際、指定した時間をかけて滑らかに移動します。",
        "guide": "レトロゲームのSEや、滑らかな上昇音を作るのに有効です。"
    },
    "PitchRange": {
        "desc": "ピッチエンベロープの変化幅(cent)です。",
        "effect": "音の始まりから終わりにかけて、ピッチを動かします。",
        "guide": "+1200: 1オクターブ上昇 / -2400: 2オクターブ下降 (落下音など)"
    },
    "PitchCurve": {
        "desc": "ピッチ変化のカーブ特性(Curve)です。",
        "effect": "変化の緩急を制御します。",
        "guide": "64:直線 / >64:指数関数(急) / <64:対数(緩)"
    },

    # --- Stereo ---
    "Pan": {
        "desc": "各ボイスの基本的な定位(左右位置)です。",
        "effect": "0(左) - 64(中央) - 127(右)",
        "guide": "Random有効時: 音が出るたびに左右ランダムに飛び回ります。"
    },
    "MasterPan": {
        "desc": "最終出力の全体的な定位バランスです。",
        "effect": "生成後のオーディオ全体の左右バランスを調整します。",
        "guide": "通常は64(中央)。特殊な定位演出が必要な場合のみ変更してください。"
    },
    "Normalize": {
        "desc": "音量正規化(ノーマライズ)処理です。",
        "effect": "生成後の波形の最大音量を0dB(最大)に合わせて音割れを防ぎます。",
        "guide": "基本は[ON]推奨。意図的に小さな音を作りたい場合はOFFにしてください。"
    },

    # --- Advanced Voice ---
    "RouteVoiceVolume": {
        "desc": "ルート音(基音)の音量バランス(0.0-1.0)です。",
        "effect": "和音の中での基音の存在感を調整します。",
        "guide": "1.0が最大。"
    },
    "MultiVoiceVolume": {
        "desc": "その他のボイス(和音構成音)の音量バランス(0.0-1.0)です。",
        "effect": "和音の厚み部分の音量を調整します。",
        "guide": "小さくすると基音が際立ち、大きくすると重厚になります。"
    },
    "DetuneVoice": {
        "desc": "デチューン(ピッチをずらした複製音)の数です。",
        "effect": "1ノートに対して重ねるユニゾンボイスの数を追加します。",
        "guide": "増やすとSuperSawのような広がりのある音になりますが、負荷が増えます。"
    },
    "DetuneRange": {
        "desc": "デチューンのピッチズレ幅(cent)です。",
        "effect": "どれくらいピッチをずらすかを設定します。",
        "guide": "5-10:自然なコーラス / 20-50:不協和音"
    },
    "DetuneVolume": {
        "desc": "デチューン音の音量比率(0.0-1.0)です。",
        "effect": "メイン音に対するデチューン音の混ざり具合を調整します。",
        "guide": "控えめ(0.3-0.5)にすると隠し味的な広がりが得られます。"
    },

    # --- LFO (Pitch) ---
    "LFO_P_Range": {
        "desc": "ピッチに対するLFO(周期的な揺れ)の深さ(cent)です。",
        "effect": "音程をビブラートさせます。",
        "guide": "10-30:ビブラート / 1200:サイレン"
    },
    "LFO_P_Type": {
        "desc": "LFOの波形タイプを選択します。",
        "effect": "揺れ方のパターンを決定します。",
        "guide": "0:Sine(滑らか) 1:Tri(直線的) 2:Saw(ノコギリ) 3:Sqr(急激な切替) 4:Rnd(不規則)"
    },
    "LFO_P_Speed": {
        "desc": "LFOの揺れる速さ(Hz)です。",
        "effect": "5Hz: ゆっくり / 20Hz: 高速",
        "guide": "音声レート(Audio Rate)変調させることも可能です。"
    },
    "LFO_P_Shape": {
        "desc": "LFO波形の形状変形(Symmetry/Skew)です。",
        "effect": "波形の偏りを調整します。",
        "guide": "50%:標準 / 0% or 100%:パルス幅や傾きが極端になります。"
    },

    # --- LFO (Volume) ---
    "LFO_V_Range": {
        "desc": "音量に対するLFO(トレモロ)の深さ(%)です。",
        "effect": "音量を周期的に変化させます。",
        "guide": "100%: 音が完全に途切れる断続音(ヘリコプター音など)になります。"
    },
    "LFO_V_Type":  {"desc": "LFO(音量)の波形タイプです。内容: 同上", "effect": "", "guide": ""},
    "LFO_V_Speed": {"desc": "LFO(音量)の速さ(Hz)です。", "effect": "", "guide": ""},
    "LFO_V_Shape": {"desc": "LFO(音量)の形状補正です。", "effect": "", "guide": ""},

    # --- LFO (Pan) ---
    "LFO_Pan_Range": {
        "desc": "定位(Pan)に対するLFOの深さ(%)です。",
        "effect": "音を左右に周期的に振ります(オートパン)。",
        "guide": "100%: 左端から右端まで大きく移動します。"
    },
    "LFO_Pan_Type":  {"desc": "LFO(Pan)の波形タイプです。内容: 同上", "effect": "", "guide": ""},
    "LFO_Pan_Speed": {"desc": "LFO(Pan)の速さ(Hz)です。", "effect": "", "guide": ""},
    "LFO_Pan_Shape": {"desc": "LFO(Pan)の形状補正です。", "effect": "", "guide": ""},

    # --- EFFECTS (Page 3) ---
    "DistortionGain": {
        "desc": "ディストーションの入力ゲイン(歪み量)です。",
        "effect": "値を上げると音が激しく歪み、倍音が増加します。",
        "guide": "0.0: 無効 / 1.0: 激しいハードクリップ歪み"
    },
    "DistortionFeed": {
        "desc": "歪みの音色(Tone)またはフィードバック特性です。",
        "effect": "歪みの質感(明るさ/太さ)を調整します。",
        "guide": "種類によって効果が変わります。"
    },
    "DistortionWet": {
        "desc": "ディストーション音と原音のミックス比率です。",
        "effect": "1.0で完全に歪んだ音(Wet)のみを出力します。",
        "guide": "0.5くらいで芯のある歪み音になります。"
    },

    "PhaserDepth": {
        "desc": "フェーザーのシュワシュワした変化の深さです。",
        "effect": "位相をずらして独自のうねりを作り出します。",
        "guide": "深くするとSF的な通過音になります。"
    },
    "PhaserSpeed": {
        "desc": "フェーザーのうねりの速さ(Hz)です。",
        "effect": "LFOによる位相変調の速度を決定します。",
        "guide": "0.5Hz: ジェット機 / 5.0Hz: 震えるような音"
    },
    "PhaserWet": {
        "desc": "フェーザー効果のミックス比率です。",
        "effect": "エフェクト音の強さを調整します。",
        "guide": "0.5-0.8が効果的です。"
    },

    "ReverbTime": {
        "desc": "リバーブ(残響)の持続時間(秒)です。",
        "effect": "空間の広さや壁の反射率をシミュレートします。",
        "guide": "3.0秒以上で巨大なホールや洞窟のような響きになります。"
    },
    "ReverbSpread": {
        "desc": "リバーブのステレオの広がり感です。",
        "effect": "残響音の左右への散らばり具合を調整します。",
        "guide": "値を上げると包み込まれるような音場になります。"
    },
    "ReverbWet": {
        "desc": "リバーブ音の音量比率です。",
        "effect": "空間の残響の強さを決定します。",
        "guide": "上げすぎると音が奥に引っ込んで聞こえます。"
    },

    "DelayTime": {
        "desc": "ディレイ(反響)が返ってくるまでの時間(秒)です。",
        "effect": "山彦のような繰り返し効果を作ります。",
        "guide": "短く(0.05s)するとダブリング効果、長く(0.5s)するとエコーになります。"
    },
    "DelayFeedback": {
        "desc": "ディレイ音が繰り返される回数(減衰率)です。",
        "effect": "値を上げると反響が長く続きます。",
        "guide": "0.9を超えるとハウリング(発振)する可能性があります。注意。"
    },
    "DelayWet": {
        "desc": "ディレイ音のミックス比率です。",
        "effect": "反響音の音量を調整します。",
        "guide": "0.3-0.5が一般的です。"
    },

    "SpreadRange": {
        "desc": "ステレオ空間の拡張幅です。",
        "effect": "音を左右に強制的に広げます(Stereo Enhancer)。",
        "guide": "モノラル音源をワイドにするのに有効です。"
    },
    "SpreadDensity": {
        "desc": "空間の密度(デチューンの厚み)です。",
        "effect": "音が重なり合う密度を調整します。",
        "guide": "高くするとよりリッチなユニゾン効果が得られます。"
    },
    "SpreadWet": {
        "desc": "空間効果の適用比率です。",
        "effect": "エフェクトの強さを調整します。",
        "guide": "原音の芯を残したい場合は0.5以下に設定してください。"
    },
}
