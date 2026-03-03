"""C3-I1 キーフレーム生成プロンプトテンプレート."""

from dataclasses import dataclass

# --- deprecated: 旧定数（単一キャラクター時と同等のプロンプトを生成するビルダー関数を推奨） ---
C3I1_FLASH_META_PROMPT = (
    "Analyze both images carefully.\n"
    "Image 1 shows the character. Image 2 shows the environment.\n"
    "Generate an image generation prompt that places the character "
    "naturally in this environment.\n"
    "The character is: {{identity_block}}\n"
    "The character's pose: {{pose_instruction}}\n"
    "Output only the prompt text, nothing else."
)

C3I1_GENERATION_TEMPLATE = (
    "Image 1 shows the character reference. Image 2 shows the environment reference.\n"
    "{{flash_prompt}}\n"
    "Single person only, solo. Photo-realistic, natural lighting."
)


@dataclass(frozen=True)
class ReferenceInfo:
    """参照コンポーネントの情報."""

    purpose: str
    text: str
    has_image: bool


# purpose → Image 説明テンプレート
_IMAGE_DESC_BY_PURPOSE: dict[str, str] = {
    "wearing": "Image {idx} shows an item the character is wearing/putting on: {text}.",
    "holding": "Image {idx} shows an item the character is holding: {text}.",
    "atmosphere": "Image {idx} shows a style/atmosphere reference: {text}.",
    "background": "Image {idx} shows a background object: {text}.",
    "interaction": "Image {idx} shows an object the character is using/interacting with: {text}.",
    "general": "Image {idx} shows additional reference: {text}.",
}

# purpose → 明示的指示テンプレート
_INSTRUCTION_BY_PURPOSE: dict[str, str] = {
    "wearing": "The character MUST be actively wearing/putting on '{text}' as shown in the reference image.",
    "holding": "The character MUST be holding '{text}' as shown in the reference image.",
    "atmosphere": "Use '{text}' as a style/mood reference for the overall scene atmosphere.",
    "background": "Place '{text}' in the background/environment as shown in the reference image.",
    "interaction": "The character MUST be actively using/interacting with '{text}' as shown in the reference image.",
    "general": "Refer to '{text}' for additional context.",
}


def build_flash_meta_prompt(
    identity_blocks: list[str],
    pose_instruction: str,
    num_char_images: int,
    has_env_image: bool,
    reference_infos: list[ReferenceInfo] | None = None,
    *,
    num_reference_images: int = 0,
) -> str:
    """Flash 用メタプロンプトを動的に生成する.

    Args:
        identity_blocks: キャラクターごとの Identity Block テキスト
        pose_instruction: ポーズ指示
        num_char_images: キャラクター画像の枚数
        has_env_image: 環境画像があるか
        reference_infos: 参照情報リスト（推奨）
        num_reference_images: 参照画像の枚数（後方互換、reference_infos 未指定時のフォールバック）
    """
    infos = reference_infos or []

    lines: list[str] = []

    # 画像番号の説明を動的生成
    image_desc = _build_image_description(num_char_images, has_env_image, infos, num_reference_images)
    lines.append(f"Analyze all images carefully.\n{image_desc}")

    lines.append(
        "Generate an image generation prompt that places the character(s) "
        "naturally in this environment."
    )

    # Identity Block を全員分列挙
    if len(identity_blocks) == 1:
        lines.append(f"The character is: {identity_blocks[0]}")
    else:
        for i, block in enumerate(identity_blocks, start=1):
            lines.append(f"Character {i} is: {block}")

    lines.append(f"The character's pose: {pose_instruction}")

    # 参照指示を追加
    ref_instructions = _build_reference_instructions(infos)
    if ref_instructions:
        lines.append(ref_instructions)

    lines.append("Output only the prompt text, nothing else.")

    return "\n".join(lines)


def build_generation_prompt(
    flash_prompt: str,
    num_char_images: int,
    has_env_image: bool,
    reference_infos: list[ReferenceInfo] | None = None,
    *,
    num_reference_images: int = 0,
) -> str:
    """Pro 用生成プロンプトを動的に生成する.

    Args:
        flash_prompt: Flash が生成したシーンプロンプト
        num_char_images: キャラクター画像の枚数
        has_env_image: 環境画像があるか
        reference_infos: 参照情報リスト（推奨）
        num_reference_images: 参照画像の枚数（後方互換、reference_infos 未指定時のフォールバック）
    """
    infos = reference_infos or []

    lines: list[str] = []

    image_desc = _build_image_description(num_char_images, has_env_image, infos, num_reference_images)
    lines.append(image_desc)
    lines.append(flash_prompt)

    # 単一キャラクター時のみ solo 制約を付与
    if num_char_images <= 1:
        lines.append("Single person only, solo. Photo-realistic, natural lighting.")
    else:
        lines.append("Photo-realistic, natural lighting.")

    return "\n".join(lines)


def _build_image_description(
    num_char_images: int,
    has_env_image: bool,
    reference_infos: list[ReferenceInfo],
    num_reference_images_fallback: int = 0,
) -> str:
    """画像番号の説明テキストを生成する."""
    parts: list[str] = []
    idx = 1

    if num_char_images == 1:
        parts.append(f"Image {idx} shows the character reference.")
        idx += 1
    else:
        for i in range(num_char_images):
            if i == 0:
                parts.append(f"Image {idx} shows the primary character.")
            else:
                parts.append(f"Image {idx} shows character {i + 1}.")
            idx += 1

    if has_env_image:
        parts.append(f"Image {idx} shows the environment reference.")
        idx += 1

    if reference_infos:
        # ReferenceInfo ベースの説明（画像付きのもののみ Image 番号を振る）
        for info in reference_infos:
            if info.has_image:
                template = _IMAGE_DESC_BY_PURPOSE.get(info.purpose, _IMAGE_DESC_BY_PURPOSE["general"])
                parts.append(template.format(idx=idx, text=info.text))
                idx += 1
    else:
        # 後方互換: num_reference_images のみ指定されたケース
        for i in range(num_reference_images_fallback):
            parts.append(f"Image {idx} shows additional reference {i + 1}.")
            idx += 1

    return " ".join(parts)


def _build_reference_instructions(reference_infos: list[ReferenceInfo]) -> str:
    """purpose に応じた明示的な指示を生成する."""
    instructions: list[str] = []
    for info in reference_infos:
        if info.purpose == "general":
            continue
        template = _INSTRUCTION_BY_PURPOSE.get(info.purpose)
        if template:
            instructions.append(f"- {template.format(text=info.text)}")

    if not instructions:
        return ""

    return "IMPORTANT reference instructions:\n" + "\n".join(instructions)
