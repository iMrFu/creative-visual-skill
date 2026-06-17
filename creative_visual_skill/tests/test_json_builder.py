"""
test_json_builder.py — json_builder 模块单元测试
"""

import os
import sys
import pytest

# 将项目根目录加入 sys.path，以便直接 import 项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import ArticleInfo, StyleInfo, PromptPayload
from json_builder import build_payload


# ===========================================================================
# 测试夹具（fixtures）
# ===========================================================================

@pytest.fixture
def sample_article():
    """模拟文章分析结果"""
    return ArticleInfo(
        topic="technology",
        emotion="inspiring",
        keywords=["AI", "future", "innovation"],
        subject="a futuristic robot arm assembling microchips",
    )


@pytest.fixture
def sample_style():
    """模拟风格模板"""
    return StyleInfo(
        style_name="cyberpunk",
        subject_placeholder="[SUBJECT]",
        composition="[SUBJECT] centered in a neon-lit cityscape",
        colors=["electric blue", "hot pink"],
        background="dark metropolitan skyline with holographic billboards",
        negative=["blurry", "low quality", "watermark"],
        tags=["neon glow", "high contrast"],
        examples=["cyberpunk_ref_01.png"],
    )


# ===========================================================================
# 测试用例
# ===========================================================================

class TestBuildPayloadBasic:
    """验证所有字段被正确合并到 PromptPayload"""

    def test_build_payload_basic(self, sample_article, sample_style):
        payload = build_payload(sample_article, sample_style)

        assert isinstance(payload, PromptPayload)
        assert payload.subject == sample_article.subject
        assert payload.style == sample_style.style_name
        assert payload.colors == sample_style.colors
        assert payload.background == sample_style.background
        assert payload.negative == sample_style.negative
        assert payload.tags == sample_style.tags
        assert payload.examples == sample_style.examples


class TestBuildPayloadSubjectReplacement:
    """验证 [SUBJECT] 占位符被替换为文章 subject"""

    def test_build_payload_subject_replacement(self, sample_article, sample_style):
        payload = build_payload(sample_article, sample_style)

        # composition 中不应再包含占位符
        assert "[SUBJECT]" not in payload.composition
        # composition 中应包含实际主体
        assert sample_article.subject in payload.composition
        # 验证完整替换结果
        expected = "a futuristic robot arm assembling microchips centered in a neon-lit cityscape"
        assert payload.composition == expected


class TestBuildPayloadCoverRatio:
    """验证封面比例 ratio='2.35:1'"""

    def test_build_payload_cover_ratio(self, sample_article, sample_style):
        # 默认 ratio 就是 '2.35:1'
        payload = build_payload(sample_article, sample_style)
        assert payload.ratio == "2.35:1"

        # 显式传入 '2.35:1'
        payload_explicit = build_payload(sample_article, sample_style, ratio="2.35:1")
        assert payload_explicit.ratio == "2.35:1"


class TestBuildPayloadContentRatio:
    """验证内容图比例 ratio='16:9'"""

    def test_build_payload_content_ratio(self, sample_article, sample_style):
        payload = build_payload(sample_article, sample_style, ratio="16:9")
        assert payload.ratio == "16:9"


class TestBuildPayloadBackgroundReplacement:
    """验证 [SUBJECT] 占位符在 background 字段中也被正确替换"""

    def test_build_payload_background_replacement(self, sample_article):
        style_with_sub_in_bg = StyleInfo(
            style_name="watercolor",
            subject_placeholder="[SUBJECT]",
            composition="[SUBJECT] running in the rain",
            background="a rainy street reflecting [SUBJECT]'s shadow",
        )
        payload = build_payload(sample_article, style_with_sub_in_bg)
        
        assert "[SUBJECT]" not in payload.background
        assert sample_article.subject in payload.background
        assert "a rainy street reflecting a futuristic robot arm assembling microchips's shadow" in payload.background

