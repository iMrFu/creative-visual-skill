"""测试视觉钩子设计器"""
import os
import sys
import pytest

# Ensure the parent directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from creative_visual_skill.utils import ArticleInfo, StyleInfo, HookPayload
from creative_visual_skill.hook_designer import (
    design_hook,
    list_hook_strategies,
    _select_hook_by_rules,
)


class TestHookLibrary:
    """钩子策略库解析测试"""

    def test_list_hook_strategies(self):
        hooks, comp_strategies = list_hook_strategies()
        assert len(hooks) >= 7, f"应至少有 7 种钩子策略，实际 {len(hooks)}"
        assert len(comp_strategies) >= 4, f"应至少有 4 种构图策略，实际 {len(comp_strategies)}"

    def test_hook_structure(self):
        hooks, _ = list_hook_strategies()
        for h in hooks:
            assert "hook_type" in h
            assert "hook_type_cn" in h
            assert "principle" in h
            assert "compatible_composition_strategies" in h
            assert isinstance(h["compatible_composition_strategies"], list)


class TestRuleMapping:
    """V1 规则映射测试"""

    def test_conflict_point_triggers_contrast(self):
        info = ArticleInfo(
            topic="教育", emotion="温暖",
            keywords=["孩子", "教育"],
            subject="亲子",
            conflict_point="管也不行不管也不行",
        )
        hook_type, comp = _select_hook_by_rules(info)
        assert hook_type == "contrast"

    def test_curiosity_gap_triggers_narrative_gap(self):
        info = ArticleInfo(
            topic="科技", emotion="冷静",
            keywords=["AI", "未来"],
            subject="机器人",
            curiosity_gap="AI 为什么能写代码",
        )
        hook_type, comp = _select_hook_by_rules(info)
        assert hook_type == "narrative_gap"

    def test_empathy_anchor_triggers_emotional_mirror(self):
        info = ArticleInfo(
            topic="情绪/心理", emotion="温暖",
            keywords=["焦虑", "共鸣"],
            subject="疲惫的人",
            empathy_anchor="你也曾深夜崩溃",
        )
        hook_type, comp = _select_hook_by_rules(info)
        assert hook_type == "emotional_mirror"

    def test_emotional_arc_scale(self):
        info = ArticleInfo(
            topic="教育", emotion="悲伤",
            keywords=["孩子"],
            subject="学生",
            emotional_arc="从渺小到看见光",
        )
        hook_type, comp = _select_hook_by_rules(info)
        assert hook_type == "scale"

    def test_fallback_to_emotion(self):
        info = ArticleInfo(topic="生活/健康", emotion="激昂", keywords=[], subject="运动")
        hook_type, comp = _select_hook_by_rules(info)
        assert hook_type == "scale"  # 激昂 → scale


class TestDesignHook:
    """集成与兜底测试"""

    def test_design_hook_v1_returns_hook_payload(self):
        info = ArticleInfo(
            topic="教育", emotion="温暖",
            keywords=["孩子", "抽动症"],
            subject="拥抱孩子的母亲",
            emotional_core="管也不行不管也不行",
            conflict_point="爱与规则之间进退两难",
        )
        style = StyleInfo(
            style_name="日系治愈手绘风",
            composition="[SUBJECT] in warm light",
        )
        result = design_hook(info, style, use_llm=False)
        assert isinstance(result, HookPayload)
        assert result.hook_type == "contrast"
        # 确保 V1 美学融合正常工作（带原风格 composition 痕迹）
        assert "warm light" in result.visual_concept
        assert "主导构图 layout" in result.visual_concept

    def test_design_hook_consolidated_extracted(self):
        """测试直接从大合并提取出的钩子荷载"""
        hook_dict = {
            "hook_type": "scale",
            "hook_type_cn": "尺度悬殊",
            "composition_strategy": "negative_space",
            "composition_strategy_cn": "留白构图",
            "visual_concept": "A tiny child in watercolor style",
            "visual_concept_cn": "水彩画里的渺小孩子",
            "hook_rationale": "test rationale"
        }
        info = ArticleInfo(
            topic="教育", emotion="温暖",
            keywords=["孩子"],
            subject="孩子",
            hook_payload_dict=hook_dict
        )
        style = StyleInfo(style_name="日系治愈手绘风")
        result = design_hook(info, style, use_llm=True)
        assert isinstance(result, HookPayload)
        assert result.hook_type == "scale"
        assert result.visual_concept == "A tiny child in watercolor style"
