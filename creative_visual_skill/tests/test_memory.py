"""
Tests for CVSkill Memory Library - 记忆库自愈及防重复错误系统
"""

import sys
import os
import shutil
import pytest
from unittest import mock

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import (
    PromptPayload,
    ArticleInfo,
    StyleInfo,
    MEMORY_HISTORY_DIR,
    MEMORY_BAD_CASES_DIR,
    read_json_file,
)
from evolver import record_evolution_memory
from json_builder import check_memory_for_overrides, build_payload


@pytest.fixture(autouse=True)
def clean_memory_dirs():
    """
    在每个测试之前清空 memory/history 和 memory/bad_cases 目录，
    避免测试受到历史残留数据或并行运行的干扰。
    """
    for folder in [MEMORY_HISTORY_DIR, MEMORY_BAD_CASES_DIR]:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception:
                    pass
    yield
    # 测试结束后再次清理，保持工作区整洁
    for folder in [MEMORY_HISTORY_DIR, MEMORY_BAD_CASES_DIR]:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception:
                    pass


class TestMemoryLibraryFlows:
    """测试记忆库的全链路操作"""

    def test_record_evolution_memory_without_image(self):
        payload = PromptPayload(
            subject="科技发展",
            style="赛博朋克霓虹风",
            composition="一个 [SUBJECT] 居中",
        )
        proposed_changes = {"whitespace_weight": 1.5, "max_elements_per_image": 4}
        
        json_path = record_evolution_memory(
            style_name="赛博朋克霓虹风",
            payload=payload,
            issue_description="画面太拥挤了",
            proposed_changes=proposed_changes,
        )

        assert os.path.exists(json_path)
        record = read_json_file(json_path)
        assert record["style_name"] == "赛博朋克霓虹风"
        assert record["article_subject"] == "科技发展"
        assert record["issue_description"] == "画面太拥挤了"
        assert record["action_taken"]["config_updates"]["whitespace_weight"] == 1.5
        assert record["bad_image_ref"] == ""

    def test_record_evolution_memory_with_image(self, tmp_path):
        # 创建一个临时测试坏图文件
        bad_img = tmp_path / "bad_image.png"
        bad_img.write_bytes(b"bad pixel data")

        payload = PromptPayload(
            subject="温暖亲子",
            style="日系治愈手绘风",
            composition="一个 [SUBJECT] 抱枕",
        )
        proposed_changes = {"comfyui_steps": 35}

        json_path = record_evolution_memory(
            style_name="日系治愈手绘风",
            payload=payload,
            issue_description="图片稍微有些模糊",
            proposed_changes=proposed_changes,
            bad_image_path=str(bad_img),
        )

        assert os.path.exists(json_path)
        record = read_json_file(json_path)
        assert record["bad_image_ref"] != ""
        
        # 提取拷贝目标图片的实际绝对路径进行验证
        copied_img_name = os.path.basename(record["bad_image_ref"])
        copied_img_path = os.path.join(MEMORY_BAD_CASES_DIR, copied_img_name)
        assert os.path.exists(copied_img_path)
        with open(copied_img_path, "rb") as f:
            assert f.read() == b"bad pixel data"

    def test_check_memory_for_overrides_matching(self):
        payload1 = PromptPayload(subject="测试主体1", style="清新水彩插画风")
        # 写入两条调优记忆，前一条和后一条对同一个风格进行迭代
        record_evolution_memory(
            style_name="清新水彩插画风",
            payload=payload1,
            issue_description="画面太挤",
            proposed_changes={"whitespace_weight": 1.4},
        )
        record_evolution_memory(
            style_name="清新水彩插画风",
            payload=payload1,
            issue_description="还是有点糊",
            proposed_changes={"comfyui_steps": 35, "whitespace_weight": 1.5},
        )

        # 检查清新水彩插画风，应按时间合并，最终 whitespace_weight 为 1.5，comfyui_steps 为 35
        overrides = check_memory_for_overrides("清新水彩插画风")
        assert overrides.get("whitespace_weight") == 1.5
        assert overrides.get("comfyui_steps") == 35

        # 检查未受影响的其它风格，应返回空 overrides
        overrides_other = check_memory_for_overrides("赛博朋克霓虹风")
        assert overrides_other == {}

    def test_build_payload_injects_overrides(self):
        # 先注入历史调优教训
        payload_ref = PromptPayload(subject="文章", style="极简扁平设计风")
        record_evolution_memory(
            style_name="极简扁平设计风",
            payload=payload_ref,
            issue_description="色调单调",
            proposed_changes={"whitespace_weight": 0.8},
        )

        # 构建新的 Payload
        article = ArticleInfo(subject="笔记本电脑")
        style = StyleInfo(style_name="极简扁平设计风", composition="画一个 [SUBJECT]")
        
        payload = build_payload(article, style)
        
        # 验证 Payload 中已成功写入 overrides 映射
        assert payload.overrides == {"whitespace_weight": 0.8}
