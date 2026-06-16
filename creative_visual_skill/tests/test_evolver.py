"""
测试 — 模块 G：自进化模块
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evolver import trigger_evolution, apply_evolution, get_evolution_history
from utils import PromptPayload, LOGS_DIR
from config import load_config, CONFIG_PATH


class TestEvolverRules:
    """规则匹配测试"""

    def test_rule_based_crowded(self):
        """反馈'画面太挤了'应增加留白权重"""
        updates = trigger_evolution("画面太挤了，元素太多")
        assert "whitespace_weight" in updates or "max_elements_per_image" in updates

    def test_rule_based_empty(self):
        """反馈'太空旷了'应减少留白权重"""
        updates = trigger_evolution("太空旷了，画面太简单了")
        assert "whitespace_weight" in updates or "max_elements_per_image" in updates

    def test_rule_based_blurry(self):
        """反馈'图片模糊'应增加步数"""
        updates = trigger_evolution("生成的图片很模糊，不清晰")
        assert "comfyui_steps" in updates

    def test_rule_based_deformed(self):
        """反馈'变形扭曲'应添加反向词"""
        updates = trigger_evolution("画面变形了，人物扭曲")
        assert "_add_negative" in updates

    def test_rule_based_no_match(self):
        """无匹配反馈应返回空更新"""
        updates = trigger_evolution("不知道该怎么说")
        assert isinstance(updates, dict)


class TestEvolverApply:
    """进化应用测试"""

    def test_apply_evolution(self):
        """验证配置更新"""
        # 保存原始配置
        original_config = load_config()

        try:
            updates = {"whitespace_weight": 1.5}
            apply_evolution(updates)
            new_config = load_config()
            assert new_config["whitespace_weight"] == 1.5
        finally:
            # 恢复原始配置
            from config import save_config
            save_config(original_config)

    def test_apply_empty_evolution(self):
        """空更新不应报错"""
        apply_evolution({})

    def test_evolution_logging(self):
        """验证进化日志写入"""
        updates = {"comfyui_steps": 30}
        apply_evolution(updates)

        log_path = os.path.join(LOGS_DIR, "evolution.log")
        assert os.path.exists(log_path)
        content = open(log_path, "r", encoding="utf-8").read()
        assert "自进化已应用" in content


class TestEvolverHistory:
    """进化历史测试"""

    def test_get_history(self):
        """获取进化历史"""
        history = get_evolution_history()
        assert isinstance(history, list)
