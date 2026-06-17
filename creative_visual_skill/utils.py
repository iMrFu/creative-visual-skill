"""
Creative Visual Skill — 通用工具模块
数据类定义 + 日志 + 文件操作工具
"""

import os
import json
import logging
import shutil
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime

__version__ = "1.0.0"

# ---------------------------------------------------------------------------
# 项目根目录（creative_visual_skill/）
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
STYLES_DIR = os.path.join(PROJECT_ROOT, "styles")
STYLES_IMAGE_DIR = os.path.join(STYLES_DIR, "image")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")
LOGS_DIR = os.path.join(PROJECT_ROOT, "logs")
WORKFLOWS_DIR = os.path.join(PROJECT_ROOT, "workflows")
MEMORY_DIR = os.path.join(PROJECT_ROOT, "memory")
MEMORY_HISTORY_DIR = os.path.join(MEMORY_DIR, "history")
MEMORY_BAD_CASES_DIR = os.path.join(MEMORY_DIR, "bad_cases")

# ---------------------------------------------------------------------------
# 确保关键目录存在
# ---------------------------------------------------------------------------
for _dir in [
    STYLES_DIR,
    STYLES_IMAGE_DIR,
    OUTPUT_DIR,
    LOGS_DIR,
    WORKFLOWS_DIR,
    MEMORY_DIR,
    MEMORY_HISTORY_DIR,
    MEMORY_BAD_CASES_DIR,
]:
    os.makedirs(_dir, exist_ok=True)



# ===========================================================================
# 核心数据结构
# ===========================================================================

@dataclass
class ArticleInfo:
    """文章分析结果"""
    topic: str = ""          # 文章主题类别
    emotion: str = ""        # 情绪基调
    keywords: List[str] = field(default_factory=list)  # 核心关键词
    subject: str = ""        # 视觉主体语义

    # ---- V3 新增：情绪张力字段 ----
    emotional_core: str = ""       # 文章最刺痛/最共鸣的点
    conflict_point: str = ""       # 核心矛盾/冲突
    curiosity_gap: str = ""        # 好奇心/信息缺口
    empathy_anchor: str = ""       # 共鸣锚点
    emotional_arc: str = ""        # 情绪走向 (从X到Y)

    # ---- V3 新增：合并调用输出字段 (仅 LLM 填充，V1 留空) ----
    matched_style: str = ""        # LLM 匹配到的风格名称
    hook_payload_dict: Dict[str, Any] = field(default_factory=dict) # 序列化的钩子策略数据

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ArticleInfo":
        return cls(
            topic=data.get("topic", ""),
            emotion=data.get("emotion", ""),
            keywords=data.get("keywords", []),
            subject=data.get("subject", ""),
            # V3
            emotional_core=data.get("emotional_core", ""),
            conflict_point=data.get("conflict_point", ""),
            curiosity_gap=data.get("curiosity_gap", ""),
            empathy_anchor=data.get("empathy_anchor", ""),
            emotional_arc=data.get("emotional_arc", ""),
            matched_style=data.get("matched_style", ""),
            hook_payload_dict=data.get("hook_payload_dict") or data.get("hook_payload") or {},
        )


@dataclass
class HookPayload:
    """钩子策略选择结果"""
    hook_type: str = ""               # 钩子策略名称 (如 "contrast")
    hook_type_cn: str = ""            # 钩子中文名 (如 "对比矛盾")
    composition_strategy: str = ""    # 构图策略名称 (如 "negative_space")
    composition_strategy_cn: str = ""  # 构图策略中文名 (如 "留白构图")
    visual_concept: str = ""          # 重写后的完整英文视觉概念 (含美学融合)
    visual_concept_cn: str = ""       # 中文概念摘要
    hook_rationale: str = ""          # 策略选择理由

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HookPayload":
        return cls(
            hook_type=data.get("hook_type", ""),
            hook_type_cn=data.get("hook_type_cn", ""),
            composition_strategy=data.get("composition_strategy", ""),
            composition_strategy_cn=data.get("composition_strategy_cn", ""),
            visual_concept=data.get("visual_concept", ""),
            visual_concept_cn=data.get("visual_concept_cn", ""),
            hook_rationale=data.get("hook_rationale", ""),
        )



@dataclass
class StyleInfo:
    """风格模板结构"""
    style_name: str = ""
    subject_placeholder: str = "[SUBJECT]"
    composition: str = ""
    composition_short: str = ""  # CLIP 限制用短描述
    colors: List[str] = field(default_factory=list)
    background: str = ""
    negative: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StyleInfo":
        return cls(
            style_name=data.get("style_name", ""),
            subject_placeholder=data.get("subject_placeholder", "[SUBJECT]"),
            composition=data.get("composition", ""),
            composition_short=data.get("composition_short", ""),
            colors=data.get("colors", []),
            background=data.get("background", ""),
            negative=data.get("negative", []),
            tags=data.get("tags", []),
            examples=data.get("examples", []),
        )



@dataclass
class PromptPayload:
    """JSON 提示词中台结构 — 系统唯一真相源"""
    subject: str = ""
    style: str = ""
    composition: str = ""
    composition_short: str = ""  # CLIP 限制用短描述
    colors: List[str] = field(default_factory=list)
    background: str = ""
    ratio: str = "2.35:1"
    negative: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    overrides: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PromptPayload":
        return cls(
            subject=data.get("subject", ""),
            style=data.get("style", ""),
            composition=data.get("composition", ""),
            composition_short=data.get("composition_short", ""),
            colors=data.get("colors", []),
            background=data.get("background", ""),
            ratio=data.get("ratio", "2.35:1"),
            negative=data.get("negative", []),
            tags=data.get("tags", []),
            examples=data.get("examples", []),
            overrides=data.get("overrides", {}),
        )




@dataclass
class ImageResult:
    """生图结果"""
    success: bool = False
    image_path: str = ""         # 输出图片路径
    prompt_used: str = ""        # 实际使用的提示词
    error_message: str = ""      # 错误信息
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ===========================================================================
# 日志工具
# ===========================================================================

def setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """创建并返回一个带文件 + 控制台输出的 logger"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # 避免重复添加 handler

    logger.setLevel(level)
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 文件 handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # 控制台 handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    return logger


# 全局 logger
run_logger = setup_logger("run", os.path.join(LOGS_DIR, "run.log"))
evolution_logger = setup_logger("evolution", os.path.join(LOGS_DIR, "evolution.log"))


# ===========================================================================
# 文件操作工具
# ===========================================================================

def read_text_file(path: str) -> str:
    """安全读取文本文件"""
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_text_file(path: str, content: str) -> None:
    """写入文本文件（自动创建目录）"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def append_text_file(path: str, content: str) -> None:
    """追加写入文本文件"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)


def read_json_file(path: str) -> dict:
    """安全读取 JSON 文件"""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_file(path: str, data: dict) -> None:
    """写入 JSON 文件"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def copy_file(src: str, dst: str) -> str:
    """复制文件，返回目标路径"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def generate_timestamped_filename(prefix: str = "img", ext: str = ".png") -> str:
    """生成带时间戳的文件名"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{prefix}_{ts}{ext}"
