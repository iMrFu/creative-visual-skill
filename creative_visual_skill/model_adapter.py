"""
Creative Visual Skill — Module D: 模型适配器
将统一的 PromptPayload 转换为各提供商所需的 prompt 格式：
  - local  (ComfyUI): 英文逗号分隔标签流  → (positive, negative)
  - openai           : 英文自然语言叙事描述 → str
  - gemini           : 自然语言描述（可含中文语境提示） → str
"""

from typing import Union, Tuple

from utils import PromptPayload, run_logger
from config import load_config


# ===========================================================================
# 公开接口
# ===========================================================================

def build_prompt(
    provider: str,
    payload: PromptPayload,
) -> Union[Tuple[str, str], str]:
    """
    根据 provider 将 PromptPayload 适配为目标模型的 prompt。

    Args:
        provider: 'local' | 'openai' | 'gemini'
        payload:  JSON 中台结构体。

    Returns:
        local  → (positive_prompt, negative_prompt)
        openai → prompt_text (str)
        gemini → prompt_text (str)

    Raises:
        ValueError: 不支持的 provider。
    """
    provider = provider.strip().lower()
    run_logger.info("build_prompt | provider='%s', ratio='%s'", provider, payload.ratio)

    if provider == "local":
        return _build_local_prompt(payload)
    elif provider == "openai":
        return _build_openai_prompt(payload)
    elif provider == "gemini":
        return _build_gemini_prompt(payload)
    else:
        raise ValueError(f"Unsupported provider: '{provider}'")


# ===========================================================================
# Local / ComfyUI  —  英文标签流
# ===========================================================================

def _build_local_prompt(payload: PromptPayload) -> Tuple[str, str]:
    """
    ComfyUI 正向/负向提示词。

    格式:
        {subject}, {style} style, {composition}, {color} color palette,
        {background} background, masterpiece, best quality, high resolution,
        [+ 比例布局标签] [+ 自定义 tags]
    """
    # ---- 色彩描述 ----
    color_desc = " and ".join(payload.colors) if payload.colors else "harmonious"

    # ---- 缩减超长 composition ----
    short_comp = _shorten_composition(payload.composition, max_chars=400)

    # ---- 基础标签序列 ----
    parts = [
        payload.subject,
        f"{payload.style} style",
        short_comp,
        f"{color_desc} color palette",
        f"{payload.background} background",
        "masterpiece",
        "best quality",
        "high resolution",
    ]

    # ---- 比例/布局标签 ----
    ratio_tags = _ratio_tags(payload.ratio)
    parts.extend(ratio_tags)

    # ---- 额外自定义 tags ----
    if payload.tags:
        parts.extend(payload.tags)

    # ---- 拼装 positive ----
    positive_prompt = ", ".join(p for p in parts if p)

    # ---- 拼装 negative ----
    negative_prompt = ", ".join(payload.negative) if payload.negative else ""

    run_logger.debug("local positive: %s", positive_prompt)
    run_logger.debug("local negative: %s", negative_prompt)

    return positive_prompt, negative_prompt


def _ratio_tags(ratio: str) -> list:
    """根据画面比例返回附加布局标签。"""
    if ratio == "2.35:1":
        return [
            "horizontal layout",
            "ultra-wide cinematic composition",
            "right side large whitespace area for text overlay",
            "asymmetric composition with subject on left third",
        ]
    elif ratio == "16:9":
        return [
            "wide angle shot",
            "cinematic widescreen ratio",
            "balanced composition",
        ]
    # 其他比例暂不追加特殊标签
    return []


# ===========================================================================
# OpenAI  —  英文自然语言叙事
# ===========================================================================

def _build_openai_prompt(payload: PromptPayload) -> str:
    """
    为 OpenAI gpt-image-1 构造故事化描述（纯英文）。
    包含：subject, style, composition, color palette, background, ratio hint。
    """
    color_desc = " and ".join(payload.colors) if payload.colors else "a harmonious"
    ratio_hint = _ratio_narrative_en(payload.ratio)

    prompt = (
        f"Create an illustration of {payload.subject} "
        f"in a {payload.style} style. "
        f"The composition features {payload.composition}. "
        f"Use a {color_desc} color palette "
        f"with a {payload.background} background atmosphere. "
        f"{ratio_hint}"
    )

    # 追加否定约束 (DALL-E)
    if payload.negative:
        prompt += " The image should not contain any of the following: " + ", ".join(payload.negative) + "."

    # 追加额外 tags 作为风格细节
    if payload.tags:
        prompt += " Additional style details: " + ", ".join(payload.tags) + "."

    # 追加示例参考说明
    if payload.examples:
        prompt += " Reference style examples: " + ", ".join(payload.examples) + "."

    run_logger.debug("openai prompt: %s", prompt)
    return prompt.strip()


# ===========================================================================
# Gemini  —  自然语言（可含中文语境）
# ===========================================================================

def _build_gemini_prompt(payload: PromptPayload) -> str:
    """
    为 Gemini 构造自然语言描述。
    英文为主，可附加中文语境提示以提升语义理解。
    """
    color_desc = " and ".join(payload.colors) if payload.colors else "a harmonious"
    ratio_hint = _ratio_narrative_en(payload.ratio)

    prompt = (
        f"Generate an image depicting {payload.subject} "
        f"rendered in {payload.style} style. "
        f"Composition: {payload.composition}. "
        f"Color palette: {color_desc}. "
        f"Background: {payload.background}. "
        f"{ratio_hint}"
    )

    # 追加否定约束 (Gemini)
    if payload.negative:
        prompt += " The image should not contain any of the following: " + ", ".join(payload.negative) + "."

    # 追加额外 tags
    if payload.tags:
        prompt += " Style tags: " + ", ".join(payload.tags) + "."

    # 中文语境补充（帮助 Gemini 理解意图）
    prompt += f" （视觉主体：{payload.subject}，画面风格：{payload.style}）"

    run_logger.debug("gemini prompt: %s", prompt)
    return prompt.strip()


# ===========================================================================
# 内部辅助
# ===========================================================================

def _ratio_narrative_en(ratio: str) -> str:
    """将比例转换为英文布局叙事段落。"""
    if ratio == "2.35:1":
        return (
            "The image should be in an ultra-wide cinematic 2.35:1 aspect ratio "
            "with a horizontal layout. Leave a large whitespace area on the right side "
            "for text overlay. Place the main subject on the left third of the frame "
            "using asymmetric composition."
        )
    elif ratio == "16:9":
        return (
            "The image should be in a 16:9 widescreen aspect ratio "
            "with a wide-angle cinematic feel and balanced composition."
        )
    elif ratio == "1:1":
        return "The image should be in a square 1:1 aspect ratio with centered composition."
    elif ratio == "3:2":
        return "The image should be in a classic 3:2 aspect ratio."
    elif ratio == "21:9":
        return "The image should be in an ultra-wide 21:9 aspect ratio with panoramic composition."
    return f"The image aspect ratio is {ratio}."


def _shorten_composition(composition: str, max_chars: int = 400) -> str:
    """如果 composition 超过 max_chars，截断至句尾或直接截断，避免 ComfyUI/CLIP 编码过载"""
    if len(composition) <= max_chars:
        return composition
    
    # 尝试在句号、分号或换行处截断
    truncated = composition[:max_chars]
    last_period = max(truncated.rfind("."), truncated.rfind(";"), truncated.rfind("\n"))
    if last_period > max_chars // 2:
        return composition[:last_period + 1].strip()
    return truncated.strip() + "..."
