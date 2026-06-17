"""
Creative Visual Skill — Module C: JSON 中台构建
将 ArticleInfo（文章分析结果）和 StyleInfo（风格模板）
合并为系统唯一真相源 PromptPayload。
"""

from .utils import ArticleInfo, StyleInfo, PromptPayload, run_logger


# ===========================================================================
# 核心构建函数
# ===========================================================================

def check_memory_for_overrides(style_name: str) -> dict:
    """
    检查 memory/history 中是否有针对特定风格的优化经验记录。
    如果存在多条记录，按时间顺序（即文件名顺序）合并更新。

    Args:
        style_name: 当前匹配到的风格名称

    Returns:
        dict: 合并后的配置覆盖参数字典，如 {"whitespace_weight": 1.4}
    """
    import os
    from .utils import MEMORY_HISTORY_DIR, read_json_file

    overrides = {}
    if not os.path.exists(MEMORY_HISTORY_DIR):
        return overrides

    try:
        files = sorted([f for f in os.listdir(MEMORY_HISTORY_DIR) if f.endswith(".json")])
        matched_count = 0
        reasons = []

        for filename in files:
            path = os.path.join(MEMORY_HISTORY_DIR, filename)
            record = read_json_file(path)
            
            if record.get("style_name") == style_name:
                action = record.get("action_taken", {})
                updates = action.get("config_updates", {})
                if updates:
                    overrides.update(updates)
                    matched_count += 1
                    desc = record.get("issue_description", "")
                    if desc:
                        reasons.append(desc)

        if matched_count > 0:
            run_logger.info(
                f"记忆库检索成功：为风格「{style_name}」找到 {matched_count} 条历史优化记录。已应用调优参数: {overrides}"
            )
            # 在控制台高亮打印提示
            print("\n" + "💡" * 30)
            print(f"CVSkill 提示：检测到该风格历史生图曾出现过以下问题：")
            for r in set(reasons):
                print(f"  - {r}")
            print(f"系统已自动应用历史调优记忆，临时重写本次生图参数: {overrides}")
            print("💡" * 30 + "\n")

    except Exception as e:
        run_logger.error(f"检索记忆库失败: {e}")

    return overrides


def build_payload(
    article_info: ArticleInfo,
    style_info: StyleInfo,
    ratio: str = "2.35:1",
    hook_payload = None,
) -> PromptPayload:
    """
    构建 PromptPayload —— JSON 中台唯一入口。

    V3 变更:
    - 引入可选的 hook_payload 参数。
    - 若 hook_payload 存在且其 visual_concept 非空，则完全替换原始的 composition
      和 composition_short，注入具有高点击驱动力的视觉钩子概念。
    """
    # ---- 1. 替换 [SUBJECT] 占位符 ----
    placeholder = style_info.subject_placeholder or "[SUBJECT]"
    composition = style_info.composition.replace(placeholder, article_info.subject)
    background = style_info.background.replace(placeholder, article_info.subject)
    composition_short = (style_info.composition_short or "").replace(placeholder, article_info.subject)

    # ---- 2. V3: 视觉钩子动态重写 ----
    if hook_payload and hook_payload.visual_concept:
        composition = hook_payload.visual_concept
        if len(composition) > 400:
            composition_short = composition[:397] + "..."
        else:
            composition_short = composition
        run_logger.info(
            "build_payload | composition 已被视觉钩子 [%s](%s) 动态重写",
            hook_payload.hook_type_cn,
            hook_payload.hook_type,
        )

    run_logger.info(
        "build_payload | subject='%s', style='%s', ratio='%s'",
        article_info.subject,
        style_info.style_name,
        ratio,
    )
    run_logger.debug(
        "build_payload | composition after replacement: '%s', composition_short: '%s'",
        composition,
        composition_short,
    )

    # ---- 3. 检索记忆库获取覆盖项 ----
    overrides = check_memory_for_overrides(style_info.style_name)

    # ---- 4. 组装 PromptPayload ----
    payload = PromptPayload(
        subject=article_info.subject,
        style=style_info.style_name,
        composition=composition,
        composition_short=composition_short,
        colors=list(style_info.colors),       # 防止引用共享
        background=background,
        ratio=ratio,
        negative=list(style_info.negative),
        tags=list(style_info.tags),
        examples=list(style_info.examples),
        overrides=overrides,
    )

    run_logger.info(
        "build_payload | payload built successfully — %d colors, %d tags, %d negative terms",
        len(payload.colors),
        len(payload.tags),
        len(payload.negative),
    )

    return payload


