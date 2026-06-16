"""
Creative Visual Skill — Module C: JSON 中台构建
将 ArticleInfo（文章分析结果）和 StyleInfo（风格模板）
合并为系统唯一真相源 PromptPayload。
"""

from utils import ArticleInfo, StyleInfo, PromptPayload, run_logger


# ===========================================================================
# 核心构建函数
# ===========================================================================

def build_payload(
    article_info: ArticleInfo,
    style_info: StyleInfo,
    ratio: str = "2.35:1",
) -> PromptPayload:
    """
    构建 PromptPayload —— JSON 中台唯一入口。

    处理逻辑:
    1. 将 StyleInfo.composition 中的 [SUBJECT] 占位符替换为
       article_info.subject（实际视觉主体语义）。
    2. 合并 ArticleInfo 与 StyleInfo 的全部字段，生成 PromptPayload。
    3. 使用传入的 ratio（默认 '2.35:1' 封面比例）。

    Args:
        article_info: 文章分析结果，包含 topic / emotion / keywords / subject。
        style_info:   风格模板结构，包含 composition / colors / background 等。
        ratio:        画面宽高比，'2.35:1'（封面）或 '16:9'（内容图）等。

    Returns:
        PromptPayload: 填充完毕的提示词中台结构。
    """
    # ---- 1. 替换 [SUBJECT] 占位符 ----
    placeholder = style_info.subject_placeholder or "[SUBJECT]"
    composition = style_info.composition.replace(placeholder, article_info.subject)

    run_logger.info(
        "build_payload | subject='%s', style='%s', ratio='%s'",
        article_info.subject,
        style_info.style_name,
        ratio,
    )
    run_logger.debug(
        "build_payload | composition after replacement: '%s'", composition
    )

    # ---- 2. 组装 PromptPayload ----
    payload = PromptPayload(
        subject=article_info.subject,
        style=style_info.style_name,
        composition=composition,
        colors=list(style_info.colors),       # 防止引用共享
        background=style_info.background,
        ratio=ratio,
        negative=list(style_info.negative),
        tags=list(style_info.tags),
        examples=list(style_info.examples),
    )

    run_logger.info(
        "build_payload | payload built successfully — %d colors, %d tags, %d negative terms",
        len(payload.colors),
        len(payload.tags),
        len(payload.negative),
    )

    return payload
