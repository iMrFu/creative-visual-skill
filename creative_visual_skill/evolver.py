"""
Creative Visual Skill — 模块 G：自进化模块
根据用户反馈 / 错误日志自动调优配置与提示词框架
"""

import os
import json
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime

from utils import (
    PromptPayload,
    run_logger,
    evolution_logger,
    LOGS_DIR,
    read_text_file,
)
from config import load_config, update_config


# ===========================================================================
# 进化上下文结构
# ===========================================================================

@dataclass
class EvolutionContext:
    """自进化上下文"""
    feedback: str = ""
    recent_logs: str = ""
    current_payload: Optional[PromptPayload] = None

    def to_dict(self) -> dict:
        return {
            "feedback": self.feedback,
            "recent_logs": self.recent_logs,
            "current_json_payload": (
                self.current_payload.to_dict() if self.current_payload else None
            ),
        }


# ===========================================================================
# V1 规则映射表
# ===========================================================================

EVOLUTION_RULES: List[Dict[str, Any]] = [
    {
        "keywords": ["太挤", "拥挤", "杂乱", "太多", "密集", "太杂"],
        "description": "画面过于拥挤 → 增加留白权重，减少元素数量",
        "config_updates": {
            "whitespace_weight_delta": 0.2,
            "max_elements_per_image_delta": -2,
        },
    },
    {
        "keywords": ["太空", "太简", "单调", "空旷", "太少", "空洞"],
        "description": "画面过于空旷 → 减少留白权重，增加元素数量",
        "config_updates": {
            "whitespace_weight_delta": -0.2,
            "max_elements_per_image_delta": 2,
        },
    },
    {
        "keywords": ["模糊", "不清晰", "不清楚", "糊", "分辨率低"],
        "description": "图片模糊 → 增加采样步数",
        "config_updates": {
            "comfyui_steps_delta": 5,
        },
    },
    {
        "keywords": ["变形", "扭曲", "畸形", "不自然", "崩坏"],
        "description": "图片变形 → 加强反向提示词",
        "config_updates": {
            "add_negative": ["deformed", "distorted", "disfigured", "bad anatomy"],
        },
    },
    {
        "keywords": ["颜色不对", "配色差", "颜色奇怪", "色调不对"],
        "description": "配色问题 → 记录建议",
        "config_updates": {
            "log_suggestion": "建议手动调整 StyleInfo 中的 colors 字段，或更换风格模板",
        },
    },
    {
        "keywords": ["字叠", "文字重叠", "文字挡住", "留白不够"],
        "description": "文字排版空间不足 → 强制加大封面留白",
        "config_updates": {
            "force_horizontal_whitespace_for_cover": True,
            "whitespace_weight_delta": 0.3,
        },
    },
    {
        "keywords": ["太慢", "速度慢", "卡住", "超时"],
        "description": "生成速度慢 → 减少采样步数",
        "config_updates": {
            "comfyui_steps_delta": -5,
        },
    },
]


# ===========================================================================
# 核心功能
# ===========================================================================

def trigger_evolution(
    feedback: str,
    recent_payload: PromptPayload = None,
    use_llm: bool = False,
    llm_provider: str = "openai",
) -> dict:
    """
    触发自进化：分析反馈，生成配置更新建议。

    Args:
        feedback: 用户反馈文本
        recent_payload: 最近使用的 PromptPayload（可选）
        use_llm: 是否使用 LLM 进行分析（V2）
        llm_provider: LLM 提供商

    Returns:
        配置更新字典
    """
    run_logger.info(f"触发自进化 — 反馈: {feedback}")

    if use_llm:
        try:
            return _trigger_evolution_llm(feedback, recent_payload, llm_provider)
        except Exception as e:
            run_logger.warning(f"LLM 自进化失败，回退到规则模式: {e}")

    return _trigger_evolution_rules(feedback)


def _trigger_evolution_rules(feedback: str) -> dict:
    """V1: 基于规则的自进化"""
    config = load_config()
    updates = {}
    matched_rules = []

    for rule in EVOLUTION_RULES:
        if any(kw in feedback for kw in rule["keywords"]):
            matched_rules.append(rule["description"])
            rule_updates = rule["config_updates"]

            # 处理增量更新
            if "whitespace_weight_delta" in rule_updates:
                current = config.get("whitespace_weight", 1.0)
                new_val = max(0.1, min(3.0, current + rule_updates["whitespace_weight_delta"]))
                updates["whitespace_weight"] = round(new_val, 2)

            if "max_elements_per_image_delta" in rule_updates:
                current = config.get("max_elements_per_image", 8)
                new_val = max(2, min(20, current + rule_updates["max_elements_per_image_delta"]))
                updates["max_elements_per_image"] = new_val

            if "comfyui_steps_delta" in rule_updates:
                current = config.get("comfyui_steps", 25)
                new_val = max(10, min(60, current + rule_updates["comfyui_steps_delta"]))
                updates["comfyui_steps"] = new_val

            if "add_negative" in rule_updates:
                updates["_add_negative"] = rule_updates["add_negative"]

            if "force_horizontal_whitespace_for_cover" in rule_updates:
                updates["force_horizontal_whitespace_for_cover"] = True

            if "log_suggestion" in rule_updates:
                evolution_logger.info(f"建议: {rule_updates['log_suggestion']}")

    if matched_rules:
        run_logger.info(f"匹配到 {len(matched_rules)} 条规则: {matched_rules}")
    else:
        run_logger.info("未匹配到任何规则，记录反馈供后续分析")
        evolution_logger.info(f"未匹配反馈: {feedback}")

    return updates


def _trigger_evolution_llm(
    feedback: str,
    recent_payload: PromptPayload = None,
    llm_provider: str = "openai",
) -> dict:
    """V2: 使用 LLM 分析反馈并生成优化建议"""
    config = load_config()

    # 读取最近日志
    run_log_path = os.path.join(LOGS_DIR, "run.log")
    recent_logs = ""
    if os.path.exists(run_log_path):
        lines = read_text_file(run_log_path).strip().split("\n")
        recent_logs = "\n".join(lines[-50:])

    context = EvolutionContext(
        feedback=feedback,
        recent_logs=recent_logs,
        current_payload=recent_payload,
    )

    system_prompt = """你是一个图片生成系统的自进化优化专家。
根据用户反馈、最近日志和当前配置，输出优化建议。

请严格输出以下 JSON 格式（不要包含其他内容）：
{
  "config_updates": {
    "whitespace_weight": <float>,
    "max_elements_per_image": <int>,
    "comfyui_steps": <int>,
    "comfyui_cfg": <float>,
    "force_horizontal_whitespace_for_cover": <bool>
  },
  "prompt_rules": {
    "additional_positive_tags": ["tag1", "tag2"],
    "additional_negative_tags": ["tag1", "tag2"]
  },
  "explanation": "简短说明优化理由"
}

只输出需要修改的字段，不需要修改的字段请省略。"""

    user_prompt = f"""用户反馈: {feedback}

当前配置:
- whitespace_weight: {config.get('whitespace_weight', 1.0)}
- max_elements_per_image: {config.get('max_elements_per_image', 8)}
- comfyui_steps: {config.get('comfyui_steps', 25)}
- comfyui_cfg: {config.get('comfyui_cfg', 7.0)}

最近日志:
{recent_logs[:2000]}

当前 Payload:
{json.dumps(context.to_dict().get('current_json_payload', {}), ensure_ascii=False, indent=2) if recent_payload else '无'}"""

    if llm_provider == "openai":
        return _call_openai_evolution(system_prompt, user_prompt, config)
    elif llm_provider == "gemini":
        return _call_gemini_evolution(system_prompt, user_prompt, config)
    else:
        raise ValueError(f"不支持的 LLM 提供商: {llm_provider}")


def _call_openai_evolution(system_prompt: str, user_prompt: str, config: dict) -> dict:
    """通过 OpenAI 进行自进化分析"""
    try:
        from openai import OpenAI
        client = OpenAI()
        response = client.chat.completions.create(
            model=config.get("llm_model", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("config_updates", {})
    except Exception as e:
        run_logger.error(f"OpenAI 自进化调用失败: {e}")
        raise


def _call_gemini_evolution(system_prompt: str, user_prompt: str, config: dict) -> dict:
    """通过 Gemini 进行自进化分析"""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client()
        response = client.models.generate_content(
            model=config.get("gemini_llm_model", "gemini-2.0-flash"),
            contents=[f"{system_prompt}\n\n{user_prompt}"],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        result = json.loads(response.text)
        return result.get("config_updates", {})
    except Exception as e:
        run_logger.error(f"Gemini 自进化调用失败: {e}")
        raise


# ===========================================================================
# 应用进化
# ===========================================================================

def apply_evolution(updates: dict) -> None:
    """
    将进化结果应用到配置文件。

    Args:
        updates: 配置更新字典
    """
    if not updates:
        evolution_logger.info("无需更新配置")
        return

    # 移除内部标记字段
    clean_updates = {k: v for k, v in updates.items() if not k.startswith("_")}

    # 应用更新
    new_config = update_config(clean_updates)

    # 记录进化日志
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    evolution_logger.info(
        f"[{timestamp}] 自进化已应用 | "
        f"更新字段: {list(clean_updates.keys())} | "
        f"更新值: {json.dumps(clean_updates, ensure_ascii=False)}"
    )

    run_logger.info(f"自进化配置已更新: {clean_updates}")

    # 如果有需要添加的反向词
    if "_add_negative" in updates:
        evolution_logger.info(
            f"建议添加反向词到风格模板: {updates['_add_negative']}"
        )


def get_evolution_history() -> List[dict]:
    """
    解析 evolution.log 获取进化历史。

    Returns:
        进化记录列表
    """
    log_path = os.path.join(LOGS_DIR, "evolution.log")
    content = read_text_file(log_path)
    if not content:
        return []

    history = []
    for line in content.strip().split("\n"):
        if "自进化已应用" in line:
            try:
                parts = line.split("] ", 2)
                timestamp = parts[0].split("[")[-1] if len(parts) > 1 else ""
                detail = parts[-1] if len(parts) > 1 else line
                history.append({
                    "timestamp": timestamp,
                    "detail": detail,
                    "raw": line,
                })
            except Exception:
                history.append({"raw": line})

    return history
