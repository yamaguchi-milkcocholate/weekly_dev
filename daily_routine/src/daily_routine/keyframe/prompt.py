"""C3-I1 キーフレーム生成プロンプトテンプレート."""

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
