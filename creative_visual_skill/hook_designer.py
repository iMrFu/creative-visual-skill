"""
Creative Visual Skill — Module B.5: 视觉钩子设计器 (Hook Designer)
根据文章的情绪张力字段，选择钩子策略 + 构图策略，生成视觉概念描述。
在 LLM 模式下直接读取大合并调用产生的数据，在规则模式下进行规则映射与美学保护拼接。
"""

import os
import re
import json
from typing import Tuple, List, Dict, Any, Optional

from .utils import ArticleInfo, StyleInfo, HookPayload, run_logger, read_text_file
from .config import load_config

# ---------------------------------------------------------------------------
# 钩子策略库文件路径
# ---------------------------------------------------------------------------
HOOK_LIBRARY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "styles", "hook_library.md"
)


# ===========================================================================
# 解析钩子策略库
# ===========================================================================

def _parse_hooks_from_markdown(md_text: str) -> Tuple[List[dict], List[dict]]:
    """从 hook_library.md 解析所有钩子策略和构图策略"""
    hooks = []
    comp_strategies = []
    pattern = re.compile(r"```json\s*\n(.*?)\n\s*```", re.DOTALL)
    matches = pattern.findall(md_text)

    for raw_json in matches:
        try:
            data = json.loads(raw_json)
            if "hook_type" in data:
                hooks.append(data)
            elif "composition_strategy" in data:
                comp_strategies.append(data)
        except json.JSONDecodeError:
            pass

    return hooks, comp_strategies


def list_hook_strategies() -> Tuple[List[dict], List[dict]]:
    """读取并返回所有钩子策略和构图策略"""
    md_text = read_text_file(HOOK_LIBRARY_PATH)
    if not md_text:
        run_logger.warning(f"钩子策略库文件为空或不存在: {HOOK_LIBRARY_PATH}")
        return [], []
    return _parse_hooks_from_markdown(md_text)


# ===========================================================================
# V1: 规则映射（兜底与无 LLM 模式）
# ===========================================================================

# emotion → 默认钩子（当张力字段全为空时的降级）
_EMOTION_DEFAULT_HOOK = {
    "温暖": "emotional_mirror",
    "严肃": "contrast",
    "冷静": "isolation",
    "激昂": "scale",
    "悲伤": "fragment",
    "幽默": "contrast",
    "浪漫": "narrative_gap",
    "治愈": "emotional_mirror",
}

# 钩子类型 → 默认构图策略
_HOOK_DEFAULT_COMPOSITION = {
    "contrast": "dominance",
    "scale": "negative_space",
    "isolation": "negative_space",
    "narrative_gap": "asymmetric_tension",
    "color_disrupt": "dominance",
    "emotional_mirror": "close_up",
    "fragment": "close_up",
}


def _select_hook_by_rules(article_info: ArticleInfo) -> Tuple[str, str]:
    """
    V1 规则映射：根据情绪张力字段选择钩子类型和构图策略。
    返回 (hook_type, composition_strategy)
    """
    hook_type = ""

    if article_info.conflict_point:
        hook_type = "contrast"
    elif article_info.curiosity_gap:
        hook_type = "narrative_gap"
    elif article_info.empathy_anchor:
        hook_type = "emotional_mirror"
    elif article_info.emotional_arc:
        arc = article_info.emotional_arc
        if any(w in arc for w in ["渺小", "无力", "压迫", "巨大"]):
            hook_type = "scale"
        elif any(w in arc for w in ["孤独", "独自", "一个人", "孤立"]):
            hook_type = "isolation"
        elif any(w in arc for w in ["不可说", "秘密", "隐藏", "压抑"]):
            hook_type = "fragment"
        elif any(w in arc for w in ["转折", "突然", "打破"]):
            hook_type = "color_disrupt"

    # 降级：用 emotion 字段
    if not hook_type:
        hook_type = _EMOTION_DEFAULT_HOOK.get(article_info.emotion, "emotional_mirror")

    comp_strategy = _HOOK_DEFAULT_COMPOSITION.get(hook_type, "dominance")

    return hook_type, comp_strategy


def _build_visual_concept_by_rules(
    article_info: ArticleInfo,
    hook_type: str,
    comp_strategy: str,
    hooks: List[dict],
    comp_strategies: List[dict],
    style_info: StyleInfo,
) -> str:
    """
    V1 规则兜底：结合原风格进行美学防走样保护的视觉概念拼接。
    拼接逻辑：[原风格 composition，已替换 [SUBJECT]] + [非对称/留白构图规则描述] + [具体钩子视觉设计说明]。
    """
    # 查找钩子和构图策略的详细信息
    hook_info = next((h for h in hooks if h["hook_type"] == hook_type), {})
    comp_info = next((c for c in comp_strategies if c["composition_strategy"] == comp_strategy), {})

    layout_keywords = comp_info.get("layout_keywords", "")
    example_visual = hook_info.get("example_visual", "")

    # 1. 获取带有主体的原始风格构图设计作为美学基底
    placeholder = style_info.subject_placeholder or "[SUBJECT]"
    style_base = style_info.composition.replace(placeholder, article_info.subject)

    # 2. 规则混合：把原风格的美学描述和钩子结合
    concept = (
        f"{style_base}, modified with {comp_info.get('composition_strategy_cn', comp_strategy)} layout: {layout_keywords}. "
        f"Visual narrative: {example_visual} representing {article_info.subject}."
    )

    # 3. 针对特定张力字段注入细节
    if hook_type == "contrast" and article_info.conflict_point:
        concept += f" Highlighting the conflict of {article_info.conflict_point}."
    elif hook_type == "narrative_gap" and article_info.curiosity_gap:
        concept += f" Leaving a visual question: {article_info.curiosity_gap} without revealing the direct outcome."
    elif hook_type == "emotional_mirror" and article_info.empathy_anchor:
        concept += f" Mirroring the feeling of: {article_info.empathy_anchor}."

    return concept.strip()


# ===========================================================================
# 公共接口
# ===========================================================================

def design_hook(
    article_info: ArticleInfo,
    style_info: StyleInfo,
    use_llm: bool = False,
    llm_provider: str = "openai",
) -> HookPayload:
    """
    设计视觉钩子策略与构图策略。
    
    优先级：
    1. 大合并路由读取：若 article_info 中已包含 hook_payload_dict，则直接重组返回。
    2. V1 规则推导：若无合并路由数据或未启用 LLM，基于规则引擎完成映射并执行美学保护拼接。
    """
    hooks, comp_strategies = list_hook_strategies()
    if not hooks:
        run_logger.warning("钩子策略库为空，返回默认钩子")
        return HookPayload(
            hook_type="emotional_mirror",
            hook_type_cn="情绪镜像",
            composition_strategy="close_up",
            composition_strategy_cn="特写构图",
            visual_concept="",
            visual_concept_cn="",
            hook_rationale="钩子策略库为空，使用默认兜底策略",
        )

    # 1. 大合并路由读取 (LLM 模式下)
    if use_llm and article_info.hook_payload_dict:
        try:
            payload = HookPayload.from_dict(article_info.hook_payload_dict)
            run_logger.info(
                f"CVSkill V3 载入合并大模型生成的视觉钩子: 【{payload.hook_type_cn}】+【{payload.composition_strategy_cn}】"
            )
            return payload
        except Exception as e:
            run_logger.error(f"反序列化合并大模型的 hook_payload_dict 失败: {e}，将采用 V1 规则兜底")

    # 2. V1 规则映射 (use_llm=False 或 LLM 异常兜底)
    hook_type, comp_strategy = _select_hook_by_rules(article_info)

    # 检索中文名称
    hook_info = next((h for h in hooks if h["hook_type"] == hook_type), {})
    comp_info = next((c for c in comp_strategies if c["composition_strategy"] == comp_strategy), {})

    visual_concept = _build_visual_concept_by_rules(
        article_info, hook_type, comp_strategy, hooks, comp_strategies, style_info
    )

    result = HookPayload(
        hook_type=hook_type,
        hook_type_cn=hook_info.get("hook_type_cn", hook_type),
        composition_strategy=comp_strategy,
        composition_strategy_cn=comp_info.get("composition_strategy_cn", comp_strategy),
        visual_concept=visual_concept,
        visual_concept_cn=f"基于 V1 规则引擎【{hook_info.get('hook_type_cn', hook_type)}】的视觉概念",
        hook_rationale=f"规则映射：文章张力检测 -> 触发 {hook_type} 钩子 -> 应用 {comp_strategy} 构图并混合风格美学基底",
    )

    # 控制台高亮输出
    print("\n" + "🎯" * 35)
    print(f"💡 CVSkill 视觉钩子策略 (规则推导 & 美学融合)：")
    print(f"   - 钩子策略：【{result.hook_type_cn}】({result.hook_type})")
    print(f"   - 构图策略：【{result.composition_strategy_cn}】({result.composition_strategy})")
    print(f"   - 视觉概念：{result.visual_concept_cn}")
    print(f"   - 策略理由：{result.hook_rationale}")
    print("🎯" * 35 + "\n")

    return result
