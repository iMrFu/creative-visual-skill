"""
Creative Visual Skill — 配置管理模块
读取 config.json，提供全局配置 & 默认值
"""

import os
from utils import PROJECT_ROOT, read_json_file, write_json_file

CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

# ===========================================================================
# 默认配置
# ===========================================================================
DEFAULT_CONFIG = {
    # --- 通用 ---
    "version": "1.0.0",
    "default_provider": "local",
    "default_cover_ratio": "2.35:1",
    "default_content_ratio": "16:9",

    # --- 本地 ComfyUI ---
    "comfyui_server": "http://127.0.0.1:8188",
    "comfyui_timeout": 300,
    "comfyui_poll_interval": 2,
    "comfyui_workflow": "sdxl_basic",      # "sdxl_basic" | "flux_basic"
    "comfyui_checkpoint": "",               # 留空则使用工作流默认值
    "comfyui_steps": 25,
    "comfyui_cfg": 7.0,
    "comfyui_sampler": "euler_ancestral",
    "comfyui_scheduler": "normal",

    # --- 云端 OpenAI ---
    "openai_model": "gpt-image-1",
    "openai_size_cover": "1536x1024",
    "openai_size_content": "1536x1024",
    "openai_quality": "high",

    # --- 云端 Gemini ---
    "gemini_model": "gemini-2.0-flash-preview-image-generation",
    "gemini_aspect_cover": "16:9",
    "gemini_aspect_content": "16:9",

    # --- LLM 文章分析 (V2) ---
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "gemini_llm_model": "gemini-2.0-flash",

    # --- 素材注入触发词 ---
    "TARGET_KEYWORDS": [
        "保存到视觉库",
        "添加封面素材",
        "保存素材",
        "保存到内容库",
        "存入素材",
        "视觉策划加入内容库",
    ],

    # --- 生图参数（可被自进化调优）---
    "whitespace_weight": 1.0,
    "max_elements_per_image": 8,
    "force_horizontal_whitespace_for_cover": True,

    # --- 尺寸映射（像素）---
    "ratio_dimensions": {
        "2.35:1": {"width": 1024, "height": 440},
        "16:9":   {"width": 1344, "height": 768},
        "1:1":    {"width": 1024, "height": 1024},
        "3:2":    {"width": 1216, "height": 832},
        "21:9":   {"width": 1536, "height": 640},
    },
}


# ===========================================================================
# 配置加载 / 保存
# ===========================================================================

def load_config() -> dict:
    """
    加载配置：以 DEFAULT_CONFIG 为基础，合并 config.json 中的覆盖值。
    如果 config.json 不存在，则创建默认配置文件。
    """
    if not os.path.exists(CONFIG_PATH):
        write_json_file(CONFIG_PATH, DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    user_config = read_json_file(CONFIG_PATH)
    merged = dict(DEFAULT_CONFIG)
    _deep_merge(merged, user_config)
    return merged


def save_config(config: dict) -> None:
    """保存配置到 config.json"""
    write_json_file(CONFIG_PATH, config)


def update_config(updates: dict) -> dict:
    """
    部分更新配置：读取现有配置，合并 updates，写回文件。
    返回更新后的完整配置。
    """
    config = load_config()
    _deep_merge(config, updates)
    save_config(config)
    return config


def get_config_value(key: str, default=None):
    """获取单个配置值"""
    config = load_config()
    return config.get(key, default)


# ===========================================================================
# 辅助
# ===========================================================================

def _deep_merge(base: dict, override: dict) -> None:
    """递归合并字典，override 中的值覆盖 base"""
    for key, value in override.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            _deep_merge(base[key], value)
        else:
            base[key] = value
