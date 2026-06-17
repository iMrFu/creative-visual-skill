"""
test_model_adapter.py — model_adapter 模块单元测试
"""

import os
import sys
import pytest

# 将项目根目录加入 sys.path
from creative_visual_skill.utils import PromptPayload
from creative_visual_skill.model_adapter import build_prompt


# ===========================================================================
# 测试夹具
# ===========================================================================

@pytest.fixture
def cover_payload():
    """封面图 payload（2.35:1）"""
    return PromptPayload(
        subject="a futuristic robot arm assembling microchips",
        style="cyberpunk",
        composition="a futuristic robot arm centered in a neon-lit cityscape",
        colors=["electric blue", "hot pink"],
        background="dark metropolitan skyline with holographic billboards",
        ratio="2.35:1",
        negative=["blurry", "low quality", "watermark"],
        tags=["neon glow", "high contrast"],
        examples=["cyberpunk_ref_01.png"],
    )


@pytest.fixture
def content_payload():
    """内容图 payload（16:9）"""
    return PromptPayload(
        subject="a cozy coffee shop interior",
        style="watercolor",
        composition="a cozy coffee shop seen from a window seat",
        colors=["warm brown", "cream white"],
        background="rainy afternoon cityscape outside the window",
        ratio="16:9",
        negative=["blurry", "distorted"],
        tags=["soft lighting", "gentle mood"],
        examples=[],
    )


# ===========================================================================
# Local (ComfyUI) 测试
# ===========================================================================

class TestLocalPrompt:
    """验证 local provider 输出逗号分隔标签"""

    def test_local_prompt_format(self, cover_payload):
        result = build_prompt(cover_payload, "local")

        # 返回 tuple: (positive, negative)
        assert isinstance(result, tuple)
        assert len(result) == 2

        positive, negative = result

        # positive 是逗号分隔的字符串
        assert isinstance(positive, str)
        assert ", " in positive

        # 基本元素必须存在
        assert cover_payload.subject in positive
        assert "cyberpunk style" in positive
        assert "masterpiece" in positive
        assert "best quality" in positive
        assert "high resolution" in positive

        # 色彩描述
        assert "electric blue and hot pink color palette" in positive

    def test_local_cover_horizontal(self, cover_payload):
        """ratio='2.35:1' 时应追加 horizontal layout 相关标签"""
        positive, _ = build_prompt(cover_payload, "local")

        assert "horizontal layout" in positive
        assert "ultra-wide cinematic composition" in positive
        assert "right side large whitespace area for text overlay" in positive
        assert "asymmetric composition with subject on left third" in positive

    def test_local_content_widescreen(self, content_payload):
        """ratio='16:9' 时应追加 widescreen 相关标签"""
        positive, _ = build_prompt(content_payload, "local")

        assert "wide angle shot" in positive
        assert "cinematic widescreen ratio" in positive
        assert "balanced composition" in positive

        # 不应出现 2.35:1 专属标签
        assert "horizontal layout" not in positive
        assert "ultra-wide cinematic composition" not in positive


# ===========================================================================
# OpenAI 测试
# ===========================================================================

class TestOpenAIPrompt:
    """验证 openai provider 输出自然语言字符串"""

    def test_openai_prompt_format(self, cover_payload):
        result = build_prompt(cover_payload, "openai")

        # 返回纯字符串
        assert isinstance(result, str)

        # 包含关键语义元素
        assert cover_payload.subject in result
        assert "cyberpunk" in result.lower()
        assert "color palette" in result.lower()
        assert "background" in result.lower()

        # 包含比例提示
        assert "2.35:1" in result


# ===========================================================================
# Gemini 测试
# ===========================================================================

class TestGeminiPrompt:
    """验证 gemini provider 输出自然语言字符串（含中文语境）"""

    def test_gemini_prompt_format(self, cover_payload):
        result = build_prompt(cover_payload, "gemini")

        # 返回纯字符串
        assert isinstance(result, str)

        # 包含英文核心语义
        assert cover_payload.subject in result
        assert "cyberpunk" in result.lower()

        # 包含中文语境提示
        assert "视觉主体" in result
        assert "画面风格" in result


# ===========================================================================
# Negative prompt 测试
# ===========================================================================

class TestNegativePrompt:
    """验证 negative 条目被正确包含在 local 负向提示词中"""

    def test_negative_prompt(self, cover_payload):
        _, negative = build_prompt(cover_payload, "local")

        assert isinstance(negative, str)
        assert "blurry" in negative
        assert "low quality" in negative
        assert "watermark" in negative

        # 负向提示词也是逗号分隔
        assert ", " in negative


class TestPromptBuildingEdgeCases:
    """验证 prompt 构建中的边缘情况（Type C bug 修复）"""

    def test_local_prompt_shortening(self):
        # 构造一个极长（超过 400 字符）的 composition
        long_comp = "A very long detailed composition description " * 15
        assert len(long_comp) > 400

        payload = PromptPayload(
            subject="dog",
            style="cartoon",
            composition=long_comp,
            colors=["red"],
            background="grass",
            ratio="1:1"
        )
        positive, _ = build_prompt(payload, "local")
        
        # 提取 composition 在 positive prompt 中的部分，验证其被截断且长度合理
        assert "A very long detailed composition description" in positive
        # 整体长度不应该无限长，且保留了截断标志或者比原本更短
        assert len(positive) < len(long_comp)

    def test_openai_negative_formatting(self):
        payload = PromptPayload(
            subject="dog",
            style="cartoon",
            composition="dog on grass",
            colors=["red"],
            background="grass",
            negative=["ugly", "deformed", "mutated"],
            ratio="1:1"
        )
        prompt = build_prompt(payload, "openai")
        assert "The image should not contain any of the following: ugly, deformed, mutated" in prompt

    def test_gemini_negative_formatting(self):
        payload = PromptPayload(
            subject="dog",
            style="cartoon",
            composition="dog on grass",
            colors=["red"],
            background="grass",
            negative=["ugly", "deformed", "mutated"],
            ratio="1:1"
        )
        prompt = build_prompt(payload, "gemini")
        assert "The image should not contain any of the following: ugly, deformed, mutated" in prompt

    def test_local_prompt_with_composition_short(self):
        payload = PromptPayload(
            subject="dog",
            style="cartoon",
            composition="a very long composition that should be ignored",
            composition_short="a short composition",
            colors=["red"],
            background="grass",
            ratio="1:1"
        )
        positive, _ = build_prompt(payload, "local")
        assert "a short composition" in positive
        assert "a very long composition" not in positive

