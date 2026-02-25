"""Scenario Engine 用のプロンプト構築."""

from daily_routine.schemas.intelligence import TrendReport


class ScenarioPromptBuilder:
    """Scenario Engine 用のプロンプト構築."""

    def build_system_prompt(self, trend_report: TrendReport) -> str:
        """TrendReport の情報を含むシステムプロンプトを構築する.

        以下の情報を構造化してプロンプトに埋め込む:
        - シーン構成トレンド（シーン数、フック手法、遷移パターン）
        - テロップトレンド（スタイル傾向）
        - 映像トレンド（シチュエーション、小物、カメラワーク、色調）
        - 音響トレンド（BPM、ジャンル、SE使用箇所）
        - 素材要件（キャラクター、小物、背景リスト）
        - シナリオ生成ルール

        Args:
            trend_report: Intelligence Engine が生成したトレンド分析レポート

        Returns:
            システムプロンプト文字列
        """
        ss = trend_report.scene_structure
        ct = trend_report.caption_trend
        vt = trend_report.visual_trend
        at = trend_report.audio_trend
        ar = trend_report.asset_requirements

        return f"""あなたは YouTube Shorts「〇〇の一日」ジャンルの動画シナリオを生成する専門家です。
トレンド分析データに基づき、視聴者を引きつける魅力的なシナリオを構造化して出力してください。

## トレンド分析データ

### シーン構成トレンド
- 分析動画数: {trend_report.analyzed_video_count}
- 平均シーン数: {ss.total_scenes}
- 平均シーン尺: {ss.avg_scene_duration_sec}秒
- 冒頭フック手法: {", ".join(ss.hook_techniques)}
- シーン遷移パターン: {", ".join(ss.transition_patterns)}

### テロップトレンド
- フォントスタイル: {", ".join(ct.font_styles)}
- 配色: {", ".join(ct.color_schemes)}
- アニメーション: {", ".join(ct.animation_types)}
- 配置位置: {", ".join(ct.positions)}
- 強調手法: {", ".join(ct.emphasis_techniques)}

### 映像トレンド
- シチュエーション: {", ".join(vt.situations)}
- 登場小物: {", ".join(vt.props)}
- カメラワーク: {", ".join(vt.camera_works)}
- 色調: {", ".join(vt.color_tones)}

### 音響トレンド
- BPM帯: {at.bpm_range[0]}〜{at.bpm_range[1]}
- ジャンル: {", ".join(at.genres)}
- 音量パターン: {", ".join(at.volume_patterns)}
- SE使用箇所: {", ".join(at.se_usage_points)}

### 素材要件
- キャラクター: {", ".join(ar.characters)}
- 小物: {", ".join(ar.props)}
- 背景: {", ".join(ar.backgrounds)}

## シナリオ生成ルール

### 1. 全体構成
- title はキーワードを含む魅力的なタイトル（日本語）
- total_duration_sec は指定された duration_range 内に収める
- 冒頭シーンはトレンド分析の hook_techniques を活用してフックを効かせる

### 2. キャラクター仕様（characters）
- asset_requirements.characters から名前を導出する
- appearance: 年齢、髪型、髪色、体型などの具体的な外見描写（英語）
- outfit: 服装の具体的な描写（英語）
- reference_prompt: Asset Generator が正面リファレンス画像を生成するための詳細プロンプト（英語）。\
白背景、スタジオライティング、全身立ちポーズを含む。\
このプロンプトは正面画像の起点用であり、横・背面・表情バリエーションは別途派生させる

### 3. 小物仕様（props）
- asset_requirements.props からリストを導出し、各小物の詳細説明と画像生成プロンプトを付与
- name: 小物名（日本語）
- description: 小物の詳細説明（日本語）。シナリオ内での用途・特徴を含む
- image_prompt: Asset Generator 向け小物画像生成プロンプト（英語）。白背景、スタジオライティング、商品撮影風

### 4. シーン仕様（scenes）
- scene_number: 1始まりの連番
- duration_sec: トレンド分析の avg_scene_duration_sec を参考に配分。合計が total_duration_sec と一致するようにする
- situation: シーンの状況を具体的に説明（日本語）
- camera_work: トレンド分析の camera_works を参考に、シーンに適したカメラワークを指定
- caption_text: 視聴者の興味を引くテロップ文言（日本語）。トレンド分析の emphasis_techniques を参考
- image_prompt: Asset Generator 向け背景画像生成プロンプト（英語）。\
キャラクター不在、背景のみ。色調はトレンドの color_tones を反映

### 5. BGM方向性（bgm_direction）
- トレンド分析の audio_trend（BPM帯、ジャンル）を反映した自然言語の指示（日本語）

### 6. プロンプト言語ルール
- 英語で書くフィールド: image_prompt, reference_prompt, appearance, outfit
- 日本語で書くフィールド: title, situation, caption_text, bgm_direction, PropSpec.name, PropSpec.description"""

    def build_user_prompt(
        self,
        keyword: str,
        duration_range: tuple[int, int],
        user_direction: str | None = None,
    ) -> str:
        """キーワードと動画尺レンジを含むユーザープロンプトを構築する.

        Args:
            keyword: 検索キーワード
            duration_range: 動画尺の範囲（秒）[min, max]
            user_direction: ユーザーのクリエイティブディレクション（自由テキスト）

        Returns:
            ユーザープロンプト文字列
        """
        min_dur, max_dur = duration_range

        prompt = f"""以下の条件でシナリオを生成してください。

キーワード: {keyword}
動画尺: {min_dur}〜{max_dur}秒"""

        if user_direction:
            prompt += f"""

## ユーザーの創作意図
{user_direction}

上記の創作意図を考慮し、トレンド分析データと合わせてシナリオを生成してください。"""

        return prompt

    def build_retry_prompt(self, errors: list[str]) -> str:
        """バリデーションエラーのフィードバックプロンプトを構築する.

        Args:
            errors: バリデーションエラーのリスト

        Returns:
            リトライ用のプロンプト文字列
        """
        error_list = "\n".join(f"- {e}" for e in errors)
        return f"""前回の生成結果に以下のエラーがありました。修正してください:
{error_list}"""
