# Debug & Development Log

## History
- **[2026-01-16] プロジェクト初期化 (Project Initialization)**
  - ルール策定: 音声サンプリングレートを **48000Hz** に統一。
  - 開発ガイドライン `GEMINI.md` を策定。
  - 計画: Step 1 (Real-time Core) の実装を開始。
- **[2026-01-16] PySerum MIDI接続修正**
  - エラー: `MidiInWinMM::openPort` (ポートの二重オープンによる競合)。
  - 原因: `customtkinter` の `OptionMenu` 設定時に意図せず再接続処理が走っていた、もしくは自動接続ロジックのガード不足。
  - 対応:
    - 接続済みポートへの再接続をガードするロジックを追加。
    - `change_midi_port` 呼び出し時の排他制御を強化。
    - Windows MM エラー時のヒントメッセージを追加。
- **[2026-01-16] Step 2: Wavetable & Unison 実装**
  - **Engine**: モノラルからステレオ(2ch)へ変更。
  - **Wavetable**: `Classic` (Saw-Square) と `Monster` (FM) の2種類をプロシージャル生成する `WavetableGenerator` を実装。
  - **Unison**: 7ボイス・デチューン、ステレオパンニングを含む `UnisonOscillator` を実装。NumPyブロードキャストにより処理負荷を低減。
  - **GUI**: Wavetable選択、Position、Detuneスライダーを追加。オシロスコープをLチャンネル表示に対応。
- **[2026-01-16] Step 3: Graphical Envelope Editor 実装**
  - **GUI分離**: カスタムウィジェット `EnvelopeEditor`（ADSRグラフ描画・操作）を `pyserum_gui_components.py` に分離実装し、保守性を向上。
  - **機能追加**: マウスドラッグでAttack, Decay/Sustain, Releaseを直感的に編集可能に。
  - **音質改善**: エンジン出力段のリミッターを `np.clip` (ハード) から `np.tanh` (ソフト) に変更し、ユニゾン時のサチュレーション感を向上。
- **[2026-01-16] Additional: Virtual Keyboard 実装**
  - **要望対応**: MIDIキーボードが使えない環境向けに、画面下部にピアノスタイルのバーチャルキーボードを実装。
  - **完成**: これにより、Serumライクな音作りと書き出しまでのワークフローが完結。

- **[2026-01-16] Step 6: Tabbed UI & Dual Oscillators**
  - **Engine**: Dual Oscillator (A/B) 構成に変更。各OSCに Wavetable, Unison, Pos, Semi, Level のパラメータを実装。
  - **GUI Refactor**: `CTkTabview` を導入し、OSC (A/B) と FX をタブで切り替え可能に。画面レイアウトをコンパクト化。
  - **UX**: 全スライダーにマウスホイール (`<MouseWheel>`) イベントをバインドし、スムーズなパラメータ調整を実現。

- **[2026-01-16] Step 7: Mod Env & Randomizer**
  - **Mod Envelope**: 第2のエンベロープ(ENV 2)を実装。Filter Cutoff (-100% to +100%) と Pitch (-48 to +48 Semis) へアサインし、レーザー音やKick等の音作りが可能に。
  - **Randomizer**: `[🎲 Generate SFX]` ボタンを実装。ワンクリックでWavetable, LFO, Filter, FX, Envelopeをランダム生成し、即戦力なSFXを作成可能。
  - **GUI Sync**: エンジン側のランダマイズ結果をGUIスライダーに逆反映する `sync_gui_from_engine` 機構を導入。マウスクリック＆ドラッグ（グリッサンド）での演奏に対応。
- **[2026-01-16] Bug Fix: ADSR ZeroDivisionError**
  - **エラー**: `pyserum_engine.py` 内 `ADSR.process` で `release_step` が 0 の際に `float division by zero` 発生。
  - **原因**: エンベロープレベルが 0 (または極小) の状態で Release フェーズへ遷移した際、除数が 0 となっていた。

- **[2026-01-16] Bug Fix: Voice.process ValueError**
  - **エラー**: `generate_block` で `Voice.process` からの戻り値アンパック時に `ValueError: expected 3, got 2` が発生。
  - **原因**: `Voice.process` の早期リターン（音が鳴っていない場合）にて、タプル `(zeros, zeros)` しか返しておらず、Mod Env用の3つ目の戻り値が欠落していた。
  - **修正**: 早期リターン時にも `(zeros, zeros, zeros)` を返すよう修正。

- **[2026-01-16] Bug Fix: EnvelopeEditor.get_params AttributeError**
  - **エラー**: `pyserum_main.py` の `update_mod_env_params` で `AttributeError: 'EnvelopeEditor' object has no attribute 'get_params'` が発生。
  - **原因**: `pyserum_gui_components.py` の `EnvelopeEditor` クラスに `get_params` メソッドが未実装だったため。
  - **修正**: `get_params` メソッドを追加し、現在のADSR設定値を返却するように修正。

- **[2026-01-16] Bug Fix: Preset Load AttributeError**
  - **エラー**: プリセット読み込み(`set_patch_state`)時に `AttributeError: 'SerumEngine' object has no attribute 'osc_a'` が発生。
  - **原因**: エンジンクラス内から `self.osc_a` に直接アクセスしようとしたが、OSCは `Voice` クラス内に存在する。
  - **修正**: `self.voices` をループして各ボイスの `osc_a/b` を設定するように修正。

- **[2026-01-16] Step 8: UI Compactness & Parameter Locking**
  - **Rotary Knob**: スライダーをカスタムウィジェット `RotaryKnob` に置き換え、省スペース化とアナログシンセ風の操作感を実現。
  - **Parameter Locking**: 各ノブの横にロック用チェックボックスを配置。`[Generate SFX]` 実行時にチェックされたパラメータは値を保持するように変更。
  - **Master Volume**: ヘッダーに Master Level ノブを追加。
  - **UI Polish**: エンベロープタブのサイズ統一やレイアウト調整を実施。

- **[2026-01-16] Step 9: Preset System (Save/Load)**
  - **Save/Open**: パッチの状態（全てのパラメータ）を JSON ファイルとして保存・読み込み可能に。
  - **Directory**: `presets/` ディレクトリを自動作成し、管理を容易化。
  - **Recorder Removed**: **[● REC]** ボタンが **[💾 Save]** に置き換わり、音声録音機能は削除（仕様変更）。
  - **GUI Sync**: プリセット読み込み時にGUI全体を更新するロジックを実装。
  - **修正**: `release_step` が 0 以下の場合は即座に IDLE 状態へ遷移するガード処理を追加。

- **[2026-01-16] MultiMorpher (lazy_gui) Maintenance**
  - **エラー**: `ModuleNotFoundError: No module named 'customtkinter'`
  - **対応**: `lazy_gui_launcher.bat` に依存ライブラリ (`customtkinter`, `librosa` 等) の自動インストールコマンドを追加。
- **[2026-01-16] MultiMorpher Feature Update**
  - **Source Search**: ソースフォルダの検索を再帰的（サブフォルダを含む）に変更しました (`glob recursive=True`)。これで孫フォルダなどのファイルも読み込まれます。

- **[2026-01-16] Step 10: UI Design Overhaul**
  - **Serum Dark Theme**: メイン背景を `#16181c`、パネルを `#23262b`、アクセントに Cyan(A) / Orange(B) を採用したモダンな配色に変更。
  - **Dense Layout**: パディングを詰め、各モジュールをパネルフレームで囲むことで密度感を向上。
  - **Filled Scope**: オシロスコープの波形表示をライン＋下部塗りつぶしに変更。

- **[2026-01-16] Step 11: Oscillator Deep Dive**
  - **Basic Shapes**: "Basic Shapes" Wavetable (Sine->Tri->Saw->Square->Pulse) を実装。
  - **Expanded OSC Params**: Octave (±3), Fine (±100 cents), Pan (-1.0 ~ 1.0), Phase (0-1), Random Phase を追加。
  - **Waveform Preview**: `WT Pos` 操作時に波形形状をスコープへプレビュー表示。
  - **Engine Logic**: `Voice` クラス内でのピッチ・パンニング処理を強化。

- **[2026-01-16] Step 12: Level Meter & Bug Fix**
  - **Bug Fix (Crash)**: `generate_random_patch` 実行時に `after_cancel` が無効なIDを受け取ってクラッシュする不具合（ValueError）を修正。
  - **Level Meter**: アプリケーション上部（Masterノブ横）にステレオレベルメーター（Peak）を追加。
  - **Bug Fix (NaN)**: Sustain Level が 1.0 の場合に `decay_step` が 0 となり、`ADSR` 処理中に `ValueError (NaN)` が発生する問題を修正。

- **[2026-01-16] Step 13: UI Refinement (Contextual Value & Visuals)**
  - **Contextual Value Display**: 各ノブの数値を非表示にし、マウスオーバー時にセクションヘッダ横（例: `OSC A [ 0.50 ]`）へ一元表示する方式に変更。視認性とスッキリ感を両立。
  - **Dynamic Visuals**: ノブのグラフィック（Arc）の明るさが値の大きさに応じて変化するよう調整（低＝暗、高＝明）。
  - **Minimal Checkboxes**: ロック用チェックボックスを 12x12 サイズに縮小し、レイアウトへの干渉を最小化。

- **[2026-01-16] Step 14: Automation System**
  - **Automation Engine**: `AutomationLane` クラスを実装し、時間補間によるパラメータ変調を実現。`SerumEngine` と統合し、`get_automated_value` 経由で各パラメータへ適用。
  - **Automation Editor**: GUI右側にオートメーションエディタ（オレンジテーマ）を追加。ポイントの追加・移動・削除、ループ長の設定が可能。
  - **Integration**: 全ノブをクリックするとフォーカスされ、エディタが該当パラメータのオートメーション編集モードに切り替わる機能を実装。

- **[2026-01-16] Step 15: Bug Fix & Layout Overhaul (1:1:2)**
  - **Critical Fix**: `pyserum_engine.py` で `UnboundLocalError` (vl referenced before assignment) が発生するバグを修正。ボイス処理ループのインデントを適正化。
  - **UI Refactor**: メイン画面を 3カラム・グリッド (OSC Tabs / FX Tabs / Automation) に刷新。幅比率を `1:1:2` に設定し、操作性と一覧性を向上。
  - **Big Value Indicator**: ヘッダーにパラメータ値を大きく表示するインジケーターを追加。ノブの操作・フォーカス時に即座に値が反映されるよう配線。

- **[2026-01-16] Step 16: GUI Configuration System**
  - **Config**: `GUI_CONFIG` 辞書を `pyserum_main.py` 冒頭に導入し、GUIサイズ定義（ウィンドウ解像度、ウィジェットサイズ、パディング等）を一元管理化。
  - **Comments**: 各設定値にデフォルト値をコメントとして併記し、これらを変更することでGUI全体のサイズ感を容易に調整可能に改修。

- **[2026-01-17] Step 17: Dashboard Layout Overhaul**
  - **Grid Layout**: 既存のTab(OSC/FX)を廃止し、OSC A/B, FXを横一列に並べるダッシュボードスタイルに変更。
  - **Right Panel**: 画面最右翼に `LevelMeter` を実装。AudioCallbackでのモノラルRMS/Peakを視覚化。
  - **Dense Design**: パディングを最小限に抑え、AutomationEditor, Envelopes, Scopeを中央部に集約。LFOパネルは一時的に非表示化。

- **[2026-01-17] Step 18: Layout Fix (Density Optimization)**
  - **Density Optimization**: Recalculated component widths to fully utilize the 1200px window width.
  - **Header Balance**: Expanded the central Indicator to 420px to eliminate empty space.
  - **Widget Sizing**: Increased knob and button sizes for better usability and professional look.

- **[2026-01-17] Step 19: Exact Pixel Layout Implementation**
  - **Layout Const**: Defined `LAYOUT_CFG` with precise pixel values for row heights and column widths.
  - **Fixed Layout**: Rebuilt `_init_ui` using `grid_propagate(False)` on all main containers to enforce strict 1200x840 dimensions.
  - **Zoning**: Applied background colors to structural frames to match the blueprint design zones.

- **[2026-01-20] MultiMorpher Pro (Integrated Rack) Implementation**
  - **Architecture**:
    - `morph_core.py`: Hybrid Audio Engine (STFT/PyWorld).
    - `processors.py`: Vectorized morphing logic (Blend, Interp, CrossSyn, Formant).
    - `protomorph_gui.py`: Rack-style CustomTkinter GUI.
  - **Verification**:
    - Created `test_pro.py` for import and logic verification.
    - Note: Dependency installation was blocking final verification.

- **[2026-01-20] Live Mode (Real-time Streaming) Implementation**
  - **Feature**: Added "Live Monitor" toggle to `protomorph_gui.py`.
  - **Engine**: Created `realtime_engine.py` using `sounddevice`.
    - Implemented block-based STFT processing pipeline (FFT -> Effect -> IFFT).
    - Supports Spectral Blending, Interpolation, Cross Synth, and Formant Shifting in near real-time.
    - Added input buffering and simple looping for continuous preview.
  - **Optimization**:
    - WORLD engine is disabled in Live Mode (CPU cost too high for Python streaming).
    - STFT block size set to 2048 for balance between latency (~42ms) and frequency resolution.

- **[2026-01-20] Performance & Export Features**
  - **XY Pad Performance Mode**:
    - Implemented `XYPad` custom widget (Canvas-based) for intuitive control.
    - X-Axis: Maps to primary morph parameter depending on mode (Split Freq, Mix, Shift).
    - Y-Axis: Maps to a new **Spectral Lowpass Filter** implemented in `realtime_engine.py` (Spectral Roll-off).
    - Added 30ms throttling (debounce) to mouse events to ensure UI responsiveness.
  - **Recording System**:
    - **Live Mode**: Added `[● REC STREAM]` button. Captures the real-time buffer stream to WAV (`output/rec_live_*.wav`).
    - **Render Mode**: Added `[EXPORT WAV]` button. Saves the last processed result to WAV (`output/render_*.wav`).
