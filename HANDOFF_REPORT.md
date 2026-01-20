# Handoff Report: SFX Automation Project (Mass Production Ready)
**Date:** 2026-01-20
**To:** Workspace (Production Team)

## 本日の成果 (Mass Production Setup)

### 1. 3台体制での量産環境構築
*   **インストーラー整備**: `install_dependencies.bat` を強化。
    *   Pythonのパスが見つからない場合の診断機能を追加。
    *   `python-3.12.7-amd64.exe` でのセットアップ手順を確立（**Add to PATH** 必須）。
*   **PC間競合の回避**:
    *   Launcher: Batch Name を `[HostName]_Batch_[Date]` 形式で自動生成するように変更。
    *   これにより、3台のPCで同時に「Run」を押してもフォルダ名が被りません。

### 2. データ集約フローの確立 (Sync to Cloud)
*   Reviewerアプリに **[☁ Sync to Cloud]** ボタンを実装しました。
*   ボタン一発で以下の処理を行います：
    1.  `HighScore` (8-10点) のWAVファイルを、Google Drive の中間プール (`SFX_Raw_Candidates`) へコピー。
    2.  `LowScore` (1-3点) のWAVファイルを、別フォルダ (`SFX_Negative_Samples`) へコピー。
    3.  **Excelログ**: `[PC名]_[Batch名]_manifest.xlsx` にリネームしてコピー（情報の上書き防止）。
*   **前回状態の記憶**: Launcher（Batch Name）と Reviewer（開いたフォルダ）の入力状態を保持するようにしました。

## 正しい運用フロー (3-PC Workflow)

### Phase 1: Local Generation & Review
### 1. Local Generation & Review
各PCローカルで行います。
1.  **Launch**: `launch_gui.bat` (デスクトップショートカット) でランチャー起動。
2.  **Generate**: "Run Pipeline" で生成 (例: `PC1_Batch_20260120...`)。
3.  **Review**: 生成完了後、"Open Reviewer" で採点 (Hotkeys: `.` to Play, `Numpad 1-9` to Score).
    *   *※この段階ではまだタグ付けは不要。単に「音として良いか悪いか」だけを判断。*

### 2. Cloud Sync (Data Pool)
1.  Reviewer左下の **[☁ Sync to Cloud]** をクリック。
2.  (初回のみ) Google Drive上の **「中間プールフォルダ」** (例: `SFX_Raw_Candidates`) を選択。
3.  データがクラウドに集約されます。

### 3. Setup Instructions (3-PC Workflow)

> **Note:** Run `install_dependencies.bat` first to ensure all libraries are installed.

1.  **Configure PC Name:** The script automatically uses the hostname (PC1, PC2, PC3). No manual config needed.
2.  **Launch:** Double-click `launch_gui.bat`.
3.  **Run Pipeline:** Set "Total Production Target" and "Asset Pool Size", then click **RUN PIPELINE**.
4.  **Review:** Click **OPEN REVIEWER** to audition and score sounds.
5.  **Sync:** Click **Sync to Cloud** to upload valid assets to GDrive.

### 4. Excel-Based Parameter Control (New!)

The pipeline now supports parameter control via an Excel file, allowing for precise tuning of the generation process without code changes.

*   **Configuration File:** `Factory_Parameters.xlsx`
    *   **Sheet 1 (Factory):** Controls synthesis parameters (Probability, Min/Max values).
    *   **Sheet 2 (Effects):** Configures Slicer, Masker, and Normalizer settings.
    *   **Sheet 3 (Weights):** Defines the probability weights for different processing routes (Transformer, Masker, Through, etc.).
*   **Loader Logic:** `pysfx_excel_loader.py` reads this file at runtime. If the file is missing, a template will be auto-generated.

### 5. Final Annotation (Tagging)
人間（管理者）が時間のある時に実施。
1.  `Quartz Suite` の `WAV Extractor` を起動。
2.  Inputとして `SFX_Raw_Candidates` を指定。
3.  タグ・コメントを付与し、正規の **`QuartzAnnotation`** フォルダへエクスポート。

## Key Components
*   `sfx_launcher_app.py` : Main GUI for 3-PC Mass Production.
*   `sfx_reviewer_app.py` : Efficient review tool with "Sync to Cloud".
*   `sfx_pipeline_manager.py` : Orchestrates the "Gacha" generation loop.
*   `pysfx_excel_loader.py` : Loads parameters from `Factory_Parameters.xlsx`.
*   `Factory_Parameters.xlsx` : User-editable configuration file.
*   `install_dependencies.bat` : One-click setup script.
*   `launch_gui.bat` : Launcher shortcut.

以上、量産体制は整いました。各PCでの稼働をお願いします。
