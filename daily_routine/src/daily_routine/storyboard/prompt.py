"""Storyboard Engine 用のプロンプト構築."""

from daily_routine.schemas.scenario import Scenario


class StoryboardPromptBuilder:
    """Storyboard Engine 用のプロンプト構築."""

    def build_system_prompt(self) -> str:
        """システムプロンプトを構築する.

        I2V モデルの特性・YouTube Shorts のテンポ・プロンプト品質ルールを含む。

        Returns:
            システムプロンプト文字列
        """
        return """あなたは YouTube Shorts 向けの絵コンテ（Storyboard）を作成する映像演出の専門家です。
シナリオの各シーンを Image-to-Video（I2V）生成に最適なカット単位に分解してください。

## I2V モデルの特性と制約

- 1枚の静止画から連続フレームを予測する技術（Runway Gen-4 Turbo）
- 得意: 小さな動き（1-2アクション）、カメラワーク、微細な変化
- 苦手: 大きな構図変更、場面転換、複数アクションの連続
- 最適な尺: 2-3秒（最大5秒）
- 生成可能な尺: 2〜10秒（整数指定）
- 1カット = 1枚のキーフレーム画像から動画を生成

## 複雑なアクションの分割ルール

- 1カットに含めるアクションは1つまで
- 複雑な動作は「動作前の構え」「動作中」「動作後の状態」に分割する
- カット切り替えで不自然さを吸収する（ショート動画のテンポに合致）
- 例: 「鞄を持って立ち上がる」→ カット1「立ち上がる動作」+ カット2「鞄を手に取る」

## YouTube Shorts のテンポ

- 冒頭1-2秒でフック（高速ダイジェスト or インパクトカット）
- 平均カット尺: 2-5秒
- 1分動画で15-25カットが目安
- 単調なカットが3つ以上続かないようにする

## カメラワーク語彙

Static, Slow zoom-in, Slow zoom-out, Pan left/right, Tilt up/down,
Dolly in/out, Track left/right, Crane up/down, Orbit, Handheld (subtle shake)

## プロンプト品質ルール

### keyframe_prompt（キーフレーム画像生成プロンプト）
- 英語で記述する
- 自然言語の完全な文章で記述する
- @char タグでキャラクターを参照する（例: "@char sits at a cafe table"）
- 場所・環境、照明・雰囲気、構図・カメラアングルを含める
- 1プロンプトにつき1シーンのみ記述する

### motion_prompt（動画生成プロンプト）
- 英語で記述する
- Subject Motion + Scene Motion + Camera Motion の3要素で構成する
- 入力画像に既にある情報（外見・服装・場所）は記述しない
- 能動態の精密な動詞を使う（walks, sips, glances, tilts, leans）
- 否定表現を使わない（"no camera movement" ではなく "The camera remains still"）
- 1ショットにつき1つの連続した動きのみ記述する

## 生成ルール

1. 各シーンを1〜5カットに分解する
2. カットの合計尺がシーンの duration_sec と一致すること
3. 全カットの合計尺が total_duration_sec と一致すること
4. 1カットの尺は 2〜5秒（整数）
5. 1カットのアクションは1つまで。複雑な動作は複数カットに分割する
6. keyframe_prompt には @char タグを使用してキャラクターを参照する
7. motion_prompt は英語、action_description は日本語
8. motion_prompt に被写体の外見・服装・場所の説明を含めない（キーフレーム画像に反映済み）
9. 冒頭シーンのカットは短め（2秒）にしてテンポを出す
10. トランジションの使い分け:
    - 同一シーン内のカット間: cut（ハードカット）を基本とする
    - シーン間の切り替え: cross_fade または fade_out → fade_in
    - 冒頭: 最初のカットに fade_in を設定可能
    - エンディング: 最後のカットに fade_out を設定可能
11. cut_id は scene_{NN}_cut_{NN} 形式（例: scene_01_cut_01, scene_02_cut_03）"""

    def build_user_prompt(self, scenario: Scenario) -> str:
        """シナリオ情報を含むユーザープロンプトを構築する.

        Args:
            scenario: Scenario Engine が生成したシナリオ

        Returns:
            ユーザープロンプト文字列
        """
        chars_section = ""
        for char in scenario.characters:
            chars_section += f"- {char.name}: {char.appearance}, {char.outfit}\n"

        scenes_section = ""
        for scene in scenario.scenes:
            scenes_section += (
                f"Scene {scene.scene_number}: {scene.situation} "
                f"({scene.duration_sec}秒, {scene.camera_work.type})\n"
                f"  テロップ: {scene.caption_text}\n"
                f"  背景: {scene.image_prompt}\n"
            )

        return f"""以下のシナリオをカット分解してください。

タイトル: {scenario.title}
全体尺: {scenario.total_duration_sec}秒

キャラクター:
{chars_section}
シーン一覧:
{scenes_section}"""

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
