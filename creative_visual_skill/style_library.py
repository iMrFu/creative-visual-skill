"""
Module B: 风格库管理 (Style Library Manager)
从 Markdown 风格模板库中解析、匹配、存储风格信息
"""

import os
import re
import json
from typing import List

from utils import (
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


def select_style(article_info: ArticleInfo) -> StyleInfo:
    """
    根据文章信息自动匹配最佳风格。

    匹配策略：
    - 将文章的 keywords + topic + emotion 合并为候选词集合
    - 对每个风格的 tags 计算与候选词的交集大小作为得分
    - 返回得分最高的风格；若平局则返回第一个匹配项

    Args:
        article_info: 文章分析结果

    Returns:
        匹配得分最高的 StyleInfo；若无风格可用则返回空 StyleInfo
    """
    styles = list_styles()
    if not styles:
        run_logger.warning("风格库为空，返回默认空风格")
        return StyleInfo()

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
