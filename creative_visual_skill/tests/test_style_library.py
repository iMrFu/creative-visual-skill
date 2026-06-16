"""
Tests for Module B: style_library — 风格库管理
"""

import sys
import os
import pytest

# 将项目根目录加入 sys.path，确保能导入项目模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import StyleInfo, ArticleInfo, STYLES_DIR, read_text_file
from style_library import (
    list_styles,
    select_style,
    add_style_to_library,
    STYLE_LIBRARY_PATH,
)


# ===========================================================================
# 测试用例
# ===========================================================================

class TestListStyles:
    """测试 list_styles 加载风格数量"""

    def test_list_styles(self):
        """验证能加载 6 个预设风格"""
        styles = list_styles()
        assert len(styles) == 6, f"期望 6 个风格，实际得到 {len(styles)}"

    def test_style_names_are_unique(self):
        """验证风格名称不重复"""
        styles = list_styles()
        names = [s.style_name for s in styles]
        assert len(names) == len(set(names)), "存在重复的风格名称"


class TestStyleFields:
    """测试风格数据完整性"""

    def test_style_has_required_fields(self):
        """验证每个风格的必填字段均已填写"""
        styles = list_styles()
        for style in styles:
            assert style.style_name, f"style_name 为空"
            assert style.subject_placeholder == "[SUBJECT]", (
                f"「{style.style_name}」的 subject_placeholder 应为 [SUBJECT]"
            )
            assert style.composition, f"「{style.style_name}」的 composition 为空"
            assert len(style.colors) >= 3, (
                f"「{style.style_name}」的 colors 少于 3 个: {style.colors}"
            )
            assert style.background, f"「{style.style_name}」的 background 为空"
            assert len(style.negative) >= 3, (
                f"「{style.style_name}」的 negative 少于 3 个: {style.negative}"
            )
            assert len(style.tags) >= 5, (
                f"「{style.style_name}」的 tags 少于 5 个: {style.tags}"
            )


class TestSelectStyle:
    """测试风格匹配算法"""

    def test_select_style_warm(self):
        """温暖/复古/亲子 关键词应匹配「复古剪贴簿拼贴风」"""
        article = ArticleInfo(
            topic="parenting",
            emotion="warm",
            keywords=["warm", "vintage", "retro", "温暖", "家庭"],
            subject="母子合影",
        )
        matched = select_style(article)
        assert matched.style_name == "复古剪贴簿拼贴风", (
            f"期望匹配复古剪贴簿拼贴风，实际: {matched.style_name}"
        )

    def test_select_style_tech(self):
        """科技/未来/赛博 关键词应匹配「赛博朋克霓虹风」"""
        article = ArticleInfo(
            topic="科技",
            emotion="futuristic",
            keywords=["neon", "tech", "cyberpunk", "赛博"],
            subject="智能机器人",
        )
        matched = select_style(article)
        assert matched.style_name == "赛博朋克霓虹风", (
            f"期望匹配赛博朋克霓虹风，实际: {matched.style_name}"
        )

    def test_select_style_watercolor(self):
        """清新/水彩 关键词应匹配「清新水彩插画风」"""
        article = ArticleInfo(
            topic="生活",
            emotion="soft",
            keywords=["watercolor", "fresh", "清新", "柔和"],
            subject="花束",
        )
        matched = select_style(article)
        assert matched.style_name == "清新水彩插画风", (
            f"期望匹配清新水彩插画风，实际: {matched.style_name}"
        )

    def test_select_style_returns_something_with_no_match(self):
        """即使没有任何关键词匹配，也应返回一个风格（第一个）"""
        article = ArticleInfo(
            topic="zzz_unknown",
            emotion="zzz_none",
            keywords=["zzz_random"],
            subject="unknown",
        )
        matched = select_style(article)
        assert matched.style_name, "应返回一个非空风格"


class TestAddStyle:
    """测试添加新风格"""

    def test_add_style(self):
        """添加新风格后，重新读取应多出一个"""
        original_styles = list_styles()
        original_count = len(original_styles)

        # 构造一个测试风格
        new_style = StyleInfo(
            style_name="测试风格_pytest",
            subject_placeholder="[SUBJECT]",
            composition="Test composition layout.",
            colors=["red", "blue", "green"],
            background="Solid white background for testing.",
            negative=["blur", "noise", "distortion"],
            tags=["test", "pytest", "测试"],
            examples=[],
        )

        # 添加
        add_style_to_library(new_style)

        # 重新读取
        updated_styles = list_styles()
        assert len(updated_styles) == original_count + 1, (
            f"添加后应有 {original_count + 1} 个风格，实际 {len(updated_styles)}"
        )

        # 验证最后一个就是新增的
        last = updated_styles[-1]
        assert last.style_name == "测试风格_pytest"

    @pytest.fixture(autouse=True)
    def _cleanup_added_style(self):
        """
        在测试前记录原始文件内容，测试后恢复。
        确保测试不会污染真实的风格库。
        """
        original_content = read_text_file(STYLE_LIBRARY_PATH)
        yield
        # 恢复原始内容
        with open(STYLE_LIBRARY_PATH, "w", encoding="utf-8") as f:
            f.write(original_content)
