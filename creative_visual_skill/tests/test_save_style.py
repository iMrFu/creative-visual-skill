"""
Tests for Module F: save_style — 素材注入 & 占位符自愈/图片反推
"""

import sys
import os
import pytest
from unittest import mock

from creative_visual_skill.utils import StyleInfo, STYLES_DIR
from creative_visual_skill.save_style import (
    _is_image_path,
    _parse_v1_rule_based,
    check_save_trigger,
    parse_style_from_input,
    confirm_and_save,
    process_save_request,
)
from creative_visual_skill.style_library import STYLE_LIBRARY_PATH, read_text_file


class TestSaveStyleTriggers:
    """测试素材注入的触发词机制"""

    def test_check_save_trigger(self):
        # 应该匹配配置中的触发词，如 "保存到内容库"
        assert check_save_trigger("保存到内容库：极简科技风")
        assert not check_save_trigger("这只是一条普通的生图命令")


class TestIsImagePath:
    """测试图片文件路径检测"""

    def test_is_image_path_invalid(self):
        assert not _is_image_path("not_a_file.png")
        assert not _is_image_path("style description without path")

    def test_is_image_path_valid(self, tmp_path):
        # 创建一个临时测试图片文件
        test_img = tmp_path / "test_style.png"
        test_img.write_bytes(b"dummy image data")
        
        # 转换成绝对路径字符串进行检测
        img_path_str = str(test_img)
        assert _is_image_path(img_path_str)
        # 测试带引号的路径
        assert _is_image_path(f'"{img_path_str}"')


class TestSubjectSelfHealing:
    """测试缺少占位符的自愈与重构"""

    @mock.patch("creative_visual_skill.save_style._add_subject_placeholder_via_llm")
    @mock.patch("creative_visual_skill.save_style.add_style_to_library")
    def test_confirm_and_save_placeholder_auto_insert(self, mock_add_to_lib, mock_llm_insert):
        # 构造一个没有 [SUBJECT] 的风格
        style_without_subject = StyleInfo(
            style_name="无主体风格",
            subject_placeholder="[SUBJECT]",
            composition="一个复古电话放在木桌上",
            colors=["red", "yellow"],
            background="模糊背景",
            negative=[],
            tags=[],
            examples=[],
        )

        # 模拟 AI 智能提取注入的结果
        healed_style = StyleInfo(
            style_name="无主体风格",
            subject_placeholder="[SUBJECT]",
            composition="一个 [SUBJECT] 放在木桌上",
            colors=["red", "yellow"],
            background="模糊背景",
            negative=[],
            tags=["电话"],
            examples=[],
        )
        mock_llm_insert.return_value = healed_style

        # 模拟用户在建议操作选项中选择 [2] (自动注入)
        with mock.patch("builtins.input", side_effect=["2", "y"]):
            success = confirm_and_save(style_without_subject, interactive=True)
            assert success
            # 应该调用 mock_llm_insert
            mock_llm_insert.assert_called_once()
            # 最终被保存的应该是 healed_style
            mock_add_to_lib.assert_called_once_with(healed_style)

    @mock.patch("creative_visual_skill.save_style.add_style_to_library")
    def test_confirm_and_save_keep_fixed(self, mock_add_to_lib):
        # 构造一个没有 [SUBJECT] 的风格
        style_without_subject = StyleInfo(
            style_name="固定风格",
            subject_placeholder="[SUBJECT]",
            composition="复古打字机放在牛皮纸上",
            colors=["warm"],
            background="暗色调",
            negative=[],
            tags=[],
            examples=[],
        )

        # 模拟用户选择 [1] (直接保存为固定无主体风格)
        with mock.patch("builtins.input", side_effect=["1", "y"]):
            success = confirm_and_save(style_without_subject, interactive=True)
            assert success
            # 直接把原风格保存
            mock_add_to_lib.assert_called_once_with(style_without_subject)


class TestImageToStyleFlow:
    """测试从图片反推风格的完整流程"""

    @mock.patch("creative_visual_skill.save_style._parse_style_from_image")
    @mock.patch("creative_visual_skill.save_style.save_image_to_library")
    @mock.patch("creative_visual_skill.save_style.confirm_and_save")
    def test_process_save_request_with_image(
        self, mock_confirm, mock_save_img, mock_parse_img, tmp_path
    ):
        # 创建临时测试图片
        test_img = tmp_path / "avatar.png"
        test_img.write_bytes(b"data")
        img_path = str(test_img)

        # 模拟 Vision LLM 返回结果
        parsed_style = StyleInfo(
            style_name="水彩风",
            subject_placeholder="[SUBJECT]",
            composition="一个 [SUBJECT] 居中",
            colors=["blue"],
            background="水彩纸",
            negative=[],
            tags=[],
            examples=[],
        )
        mock_parse_img.return_value = parsed_style
        mock_save_img.return_value = "image/style_ref_123.png"
        mock_confirm.return_value = True

        # 运行流程
        success = process_save_request(img_path, use_llm=True, interactive=False)
        
        assert success
        # 应该触发视觉反推
        mock_parse_img.assert_called_once_with(img_path, use_llm=True, llm_provider="openai")
        # 应该拷贝图片至风格库
        mock_save_img.assert_called_once_with(img_path)
        # 解析结果的 examples 应该被更新为拷贝后的相对路径
        assert parsed_style.examples == ["image/style_ref_123.png"]


class TestStyleLibraryRestoration:
    """测试时备份与恢复 style_library.md"""

    @pytest.fixture(autouse=True)
    def _cleanup_added_style(self):
        original_content = read_text_file(STYLE_LIBRARY_PATH)
        yield
        with open(STYLE_LIBRARY_PATH, "w", encoding="utf-8") as f:
            f.write(original_content)
