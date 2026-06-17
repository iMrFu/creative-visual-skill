"""
Module B: 风格库管理 (Style Library Manager)
从 Markdown 风格模板库中解析、匹配、存储风格信息
"""

import os
import re
import json
from typing import List

from .utils import (
    StyleInfo,
    ArticleInfo,
    STYLES_DIR,
    STYLES_IMAGE_DIR,
    run_logger,
    read_text_file,
    append_text_file,
    copy_file,
    generate_timestamped_filename,
)
from .config import load_config

# ---------------------------------------------------------------------------
# 风格库 Markdown 文件路径
# ---------------------------------------------------------------------------
STYLE_LIBRARY_PATH = os.path.join(STYLES_DIR, "style_library.md")


# ===========================================================================
# 核心解析函数
# ===========================================================================

def _parse_styles_from_markdown(md_text: str) -> List[StyleInfo]:
    """
    从 Markdown 文本中提取所有 ## Style 区块内的 JSON 代码块，
    将每个 JSON 解析为 StyleInfo 对象。

    解析策略：
    - 用正则匹配所有 ```json ... ``` 代码块
    - 每个代码块视为一个独立的风格定义
    """
    styles: List[StyleInfo] = []

    # 匹配 ```json ... ``` 代码块（非贪婪）
    pattern = re.compile(r"```json\s*\n(.*?)\n\s*```", re.DOTALL)
    matches = pattern.findall(md_text)

    for i, raw_json in enumerate(matches):
        try:
            data = json.loads(raw_json)
            style = StyleInfo.from_dict(data)
            styles.append(style)
            run_logger.debug(f"解析风格 #{i+1}: {style.style_name}")
        except (json.JSONDecodeError, KeyError) as e:
            run_logger.warning(f"跳过无效的风格 JSON 块 #{i+1}: {e}")

    run_logger.info(f"从 style_library.md 共解析 {len(styles)} 个风格模板")
    return styles


# ===========================================================================
# 公开 API 函数
# ===========================================================================

def list_styles() -> List[StyleInfo]:
    """
    读取并返回所有风格模板。

    Returns:
        解析后的 StyleInfo 列表
    """
    md_text = read_text_file(STYLE_LIBRARY_PATH)
    if not md_text:
        run_logger.warning(f"风格库文件为空或不存在: {STYLE_LIBRARY_PATH}")
        return []
    return _parse_styles_from_markdown(md_text)


def select_style(
    article_info: ArticleInfo,
    use_llm: bool = False,
    llm_provider: str = "openai",
) -> StyleInfo:
    """
    根据文章信息自动匹配最佳风格。

    匹配策略：
    - V2 LLM 模式（use_llm=True）：调用大模型进行意图路由并生成视觉策划说明。
    - V1 规则模式（use_llm=False / 失败回退）：基于关键词与标签的交集匹配。

    Args:
        article_info: 文章分析结果
        use_llm:      是否使用大模型进行匹配
        llm_provider: 大模型服务商

    Returns:
        匹配得分最高的 StyleInfo；若无风格可用则返回空 StyleInfo
    """
    styles = list_styles()
    if not styles:
        run_logger.warning("风格库为空，返回默认空风格")
        return StyleInfo()

    # V3: 如果合并大模型调用已经匹配了风格，则直接使用
    if use_llm and article_info.matched_style:
        matched_name = article_info.matched_style.strip()
        for s in styles:
            if s.style_name.strip() == matched_name:
                run_logger.info(f"select_style | 使用合并大模型提取的风格: 【{s.style_name}】")
                return s
        run_logger.warning(f"select_style | 合并大模型推荐的风格 '{matched_name}' 未在库中找到，执行重新选择")

    if use_llm:
        config = load_config()

        # 提取可用风格的基本信息，用于传递给大模型减小 token 并防止越界
        style_list_for_llm = []
        for s in styles:
            style_list_for_llm.append({
                "style_name": s.style_name,
                "tags": s.tags,
                "composition_short": s.composition_short or s.composition[:100],
            })

        system_prompt = (
            "你是一个顶尖的自媒体视觉创意总监。\n"
            "用户会给你一篇自媒体文章的解析信息（ArticleInfo JSON），以及当前风格库中可用的生图风格列表。\n"
            "请分析文章的主题和情感，在可用的风格列表中选择一个最能表达文章内涵、甚至能产生奇妙跨界视觉张力的最佳风格，并给出你的专业策划理由。\n\n"
            "【大模型匹配原则】\n"
            "1. 行业与语义对齐：当文章主题涉及汽车、宝马、车等，智能匹配「汽车广告大片风」；当涉及科技、AI，优先匹配「赛博朋克霓虹风」；涉及自然、唯美，匹配「清新水彩插画风」等。\n"
            "2. 跨界创意推荐（如果合适）：你可以在“保守匹配”与“跨界碰撞”之间权衡。如果跨界碰撞（例如冷酷数据匹配温馨手绘，或者亲子陪伴匹配赛博朋克）能带来惊艳反差感，且契合情绪，你可以做出大胆提议。\n"
            "3. 选取的风格必须是当前风格列表中已经存在的名字，不可凭空捏造。\n\n"
            "请严格返回以下 JSON 格式（不要有任何解释性文字或 Markdown 代码块包裹）：\n"
            "{\n"
            '  "selected_style_name": "选中的风格名称（必须是风格列表里已有的精确名字）",\n'
            '  "match_strategy": "conservative" 或 "creative_clash",\n'
            '  "artistic_rationale": "用一两句充满策划设计感的话，解释为什么选择这种风格，以及这种风格将如何提升文章的视觉表现力和创意度。"\n'
            "}"
        )

        user_prompt = (
            f"【文章解析信息 (ArticleInfo)】\n"
            f"{json.dumps(article_info.to_dict(), ensure_ascii=False, indent=2)}\n\n"
            f"【可用风格选项列表】\n"
            f"{json.dumps(style_list_for_llm, ensure_ascii=False, indent=2)}"
        )

        try:
            raw = ""
            if llm_provider == "openai":
                import openai
                model = config.get("llm_model", "gpt-4o-mini")
                client = openai.OpenAI(base_url=config.get("openai_base_url", "") or None)
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.3,
                    max_tokens=600,
                    response_format={"type": "json_object"} if model != "gpt-3.5-turbo" else None,
                )
                raw = response.choices[0].message.content.strip()
            elif llm_provider == "gemini":
                from google import genai
                from google.genai import types
                model_name = config.get("gemini_llm_model", "gemini-2.0-flash")
                client = genai.Client()
                response = client.models.generate_content(
                    model=model_name,
                    contents=[system_prompt, user_prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.3,
                    )
                )
                raw = response.text.strip()

            if raw:
                # 提取 JSON（防止有外部 markdown 代码块）
                json_match = re.search(r'\{[\s\S]*\}', raw)
                if json_match:
                    res_data = json.loads(json_match.group())
                    sel_name = res_data.get("selected_style_name", "").strip()
                    rationale = res_data.get("artistic_rationale", "").strip()
                    strategy = res_data.get("match_strategy", "conservative").strip()

                    # 在 styles 中寻找匹配的风格
                    for s in styles:
                        if s.style_name.strip() == sel_name:
                            # 控制台打印高亮策划词
                            strategy_cn = "经典契合" if strategy == "conservative" else "跨界碰撞"
                            print("\n" + "🎨" * 35)
                            print(f"💡 CVSkill 创意策划（AI 视觉总监提议）：")
                            print(f"   - 匹配风格：【{s.style_name}】")
                            print(f"   - 匹配策略：【{strategy_cn}】")
                            print(f"   - 策划理由：{rationale}")
                            print("🎨" * 35 + "\n")

                            run_logger.info(f"LLM 智能风格选择成功: 「{s.style_name}」, 策略: {strategy}")
                            return s

                    run_logger.warning(f"LLM 返回了未知的风格名字: '{sel_name}'，将退避到 V1 匹配")
        except Exception as e:
            run_logger.warning(f"LLM 智能风格选择失败 ({llm_provider}): {e}，将退避到 V1 匹配")

    # ---- V1 规则匹配（降级通道） ----
    # 构建文章候选词集合（全部转小写以统一比较）
    candidate_words: set = set()
    for kw in article_info.keywords:
        candidate_words.add(kw.lower().strip())
    if article_info.topic:
        candidate_words.add(article_info.topic.lower().strip())
    if article_info.emotion:
        candidate_words.add(article_info.emotion.lower().strip())

    run_logger.debug(f"文章候选词: {candidate_words}")

    best_style: StyleInfo = styles[0]
    best_score: int = -1

    for style in styles:
        # 风格 tags 也转小写比较
        style_tags = {t.lower().strip() for t in style.tags}
        score = len(candidate_words & style_tags)

        run_logger.debug(
            f"  风格「{style.style_name}」得分={score}  "
            f"(交集: {candidate_words & style_tags})"
        )

        if score > best_score:
            best_score = score
            best_style = style

    run_logger.info(
        f"风格匹配结果: 「{best_style.style_name}」(得分={best_score})"
    )
    return best_style


def save_image_to_library(image_path: str) -> str:
    """
    将图片复制到风格库的 image/ 目录，使用时间戳重命名。

    Args:
        image_path: 源图片的绝对路径

    Returns:
        相对于 STYLES_DIR 的路径，如 "image/img_20260101_120000_000000.png"
    """
    if not os.path.exists(image_path):
        run_logger.error(f"源图片不存在: {image_path}")
        return ""

    # 保留原始扩展名
    _, ext = os.path.splitext(image_path)
    ext = ext if ext else ".png"

    new_name = generate_timestamped_filename(prefix="style_ref", ext=ext)
    dst_path = os.path.join(STYLES_IMAGE_DIR, new_name)

    copy_file(image_path, dst_path)
    relative_path = os.path.join("image", new_name)

    run_logger.info(f"图片已保存至风格库: {relative_path}")
    return relative_path


def add_style_to_library(style_info: StyleInfo) -> None:
    """
    将新风格追加到 style_library.md 文件末尾。

    使用与现有条目相同的 Markdown 格式：
    ## Style + ```json 代码块

    Args:
        style_info: 要添加的风格信息
    """
    # 将 StyleInfo 转为格式化 JSON
    style_dict = style_info.to_dict()
    json_str = json.dumps(style_dict, ensure_ascii=False, indent=2)

    # 构建 Markdown 条目
    entry = f"\n\n## Style\n\n```json\n{json_str}\n```\n"

    append_text_file(STYLE_LIBRARY_PATH, entry)
    run_logger.info(f"已添加新风格至库: 「{style_info.style_name}」")


# ===========================================================================
# 直接运行时的快速验证
# ===========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("风格库管理模块 — 快速验证")
    print("=" * 60)

    all_styles = list_styles()
    print(f"\n共加载 {len(all_styles)} 个风格:")
    for s in all_styles:
        print(f"  • {s.style_name}  (tags: {', '.join(s.tags[:4])}...)")

    # 测试匹配
    test_article = ArticleInfo(
        topic="科技",
        emotion="futuristic",
        keywords=["neon", "tech", "cyberpunk"],
        subject="智能机器人",
    )
    matched = select_style(test_article)
    print(f"\n匹配测试 (科技/futuristic/neon) → 「{matched.style_name}」")
