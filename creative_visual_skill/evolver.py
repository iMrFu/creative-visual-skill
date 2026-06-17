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
    MEMORY_HISTORY_DIR,
    MEMORY_BAD_CASES_DIR,
    copy_file,
    generate_timestamped_filename,
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

def evaluate_generation(
    image_path: str,
    prompt_text: str,
    payload: PromptPayload,
    feedback: str = "",
    use_llm: bool = False,
    llm_provider: str = "openai",
) -> dict:
    """
    自进化诊断评估主入口。
    
    支持三种诊断路径：
    1. 视觉多模态评估 (use_llm=True, feedback为空, image_path存在)
    2. LLM 文本解析评估 (use_llm=True, feedback不为空)
    3. 本地规则匹配评估 (use_llm=False, feedback不为空)

    Returns:
        dict: {
            "has_issue": bool,
            "issue_type": "skill" | "model" | "none",
            "explanation": str,
            "proposed_changes": dict  # 需要修改的配置项增量或具体新值
        }
    """
    run_logger.info(f"评估生图结果 | use_llm={use_llm} | provider={llm_provider} | feedback={feedback}")

    if use_llm and not feedback and image_path and os.path.exists(image_path):
        return _evaluate_generation_vision(image_path, prompt_text, payload, llm_provider)
    elif feedback:
        if use_llm:
            return _evaluate_generation_text_llm(feedback, payload, llm_provider)
        else:
            return _evaluate_generation_text_rules(feedback)

    return {
        "has_issue": False,
        "issue_type": "none",
        "explanation": "画面未发现明显异常。",
        "proposed_changes": {}
    }


def trigger_evolution(
    feedback: str,
    recent_payload: PromptPayload = None,
    use_llm: bool = False,
    llm_provider: str = "openai",
) -> dict:
    """
    触发自进化——向后兼容接口。
    """
    report = evaluate_generation(
        image_path="",
        prompt_text="",
        payload=recent_payload or PromptPayload(),
        feedback=feedback,
        use_llm=use_llm,
        llm_provider=llm_provider,
    )
    return report.get("proposed_changes", {})


def _evaluate_generation_vision(
    image_path: str,
    prompt_text: str,
    payload: PromptPayload,
    llm_provider: str = "openai",
) -> dict:
    """多模态视觉诊断"""
    config = load_config()
    
    system_prompt = """你是一个图片生成系统的多模态视觉审计专家。
你的任务是评估一张由AI生成的图片，对照它所使用的提示词（Prompt）与配置参数，审计生成质量，并决定是否进行调参优化。

请分析图片是否存在以下两类问题：

1. Skill（系统配置）问题：
   - 构图拥挤度：如果画面元素堆积过多、太挤、文字区域（封面图右侧）被杂物遮挡，这属于留白权重不足的问题。
   - 分辨率与细节：如果画面模糊、精细度不足。
   如果是这类问题，你需要在 `proposed_changes` 中建议对 `config.json` 进行对应的修改。

2. Model（模型能力限制）问题：
   - 严重的肢体/面部畸形、英文字母错乱、文字写错。这是模型本身的表达能力上限所致，无法仅通过调整留白权重或步数解决。
   如果是这类问题，请将问题归类为 `model`，说明是模型问题，并在解释中建议用户切换更高级的生图后端（例如切换为 DALL-E 3 或 ComfyUI 中的 Flux 模型），`proposed_changes` 保持为空。

如果不满意且属于 Skill 问题，你可以推荐以下调参修改建议（返回增量或最终的目标配置值，支持的配置字段包括 whitespace_weight, max_elements_per_image, comfyui_steps, comfyui_cfg 等）：
- whitespace_weight 留白权重：调节画面留白比例。画面太挤时调高（如调高 0.2，上限 3.0），太单调时调低（如调低 0.2，下限 0.1）。
- max_elements_per_image 元素数上限：画面太杂时调小（如减少 2），太单调时调大（如增加 2）。
- comfyui_steps 采样步数：画面模糊时调大（如增加 5 步）。

请严格输出以下 JSON 格式（不要包含任何解释性文字或 Markdown 代码块包裹）：
{
  "has_issue": <bool>,
  "issue_type": "skill" | "model" | "none",
  "explanation": "中文的详细诊断归因解释",
  "proposed_changes": {
    "whitespace_weight": <float>,
    "max_elements_per_image": <int>,
    "comfyui_steps": <int>,
    "comfyui_cfg": <float>
  }
}
"""
    import base64
    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        if llm_provider == "openai":
            from openai import OpenAI
            client = OpenAI()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            ext = os.path.splitext(image_path)[1].lower()
            mime_type = "image/png" if "png" in ext else "image/jpeg"
            image_url = f"data:{mime_type};base64,{img_b64}"

            user_content = [
                {"type": "text", "text": f"Original Prompt: {prompt_text}\nPayload: {json.dumps(payload.to_dict(), ensure_ascii=False)}"},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]

            response = client.chat.completions.create(
                model=config.get("llm_model", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()

        elif llm_provider == "gemini":
            from google import genai
            from google.genai import types
            from PIL import Image

            client = genai.Client()
            img = Image.open(image_path)

            user_content = [
                img,
                f"Original Prompt: {prompt_text}\nPayload: {json.dumps(payload.to_dict(), ensure_ascii=False)}"
            ]

            response = client.models.generate_content(
                model=config.get("gemini_llm_model", "gemini-2.0-flash"),
                contents=[system_prompt] + user_content,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            raw = response.text.strip()
        else:
            return {
                "has_issue": False,
                "issue_type": "none",
                "explanation": f"不支持的 LLM 提供商: {llm_provider}",
                "proposed_changes": {}
            }

        data = json.loads(raw)
        return {
            "has_issue": data.get("has_issue", False),
            "issue_type": data.get("issue_type", "none"),
            "explanation": data.get("explanation", ""),
            "proposed_changes": data.get("proposed_changes", {})
        }
    except Exception as e:
        run_logger.error(f"视觉多模态分析失败: {e}")
        return {
            "has_issue": False,
            "issue_type": "none",
            "explanation": f"多模态视觉审计分析失败: {e}",
            "proposed_changes": {}
        }


def _evaluate_generation_text_llm(
    feedback: str,
    payload: PromptPayload = None,
    llm_provider: str = "openai",
) -> dict:
    """通过 LLM 分析文本反馈进行进化诊断"""
    config = load_config()
    system_prompt = """你是一个图片生成系统的自进化调优专家。
请根据用户的负向反馈（如'画面太挤了'、'人脸变形了'），分析这是属于 Skill（配置参数）问题，还是 Model（模型底层能力限制）问题，并给出诊断报告与具体的修改配置参数。

请分析并分类：
1. Skill（系统配置）问题：如果用户吐槽太挤、太杂、太空旷、模糊等。
   对应的 proposed_changes 可以包含更新 whitespace_weight, max_elements_per_image, comfyui_steps, comfyui_cfg。
2. Model（模型能力）问题：如果用户吐槽字写错了、人脸变形、多出手指等。
   设置 issue_type 为 'model'，不返回 proposed_changes。

请严格输出以下 JSON 格式（不要包含任何解释性文字或 Markdown 代码块包裹）：
{
  "has_issue": true,
  "issue_type": "skill" | "model",
  "explanation": "中文的详细诊断归因解释",
  "proposed_changes": {
    "whitespace_weight": <float>,
    "max_elements_per_image": <int>,
    "comfyui_steps": <int>,
    "comfyui_cfg": <float>
  }
}
"""
    user_prompt = f"用户反馈: {feedback}\n"
    if payload:
        user_prompt += f"Payload: {json.dumps(payload.to_dict(), ensure_ascii=False)}"

    try:
        if llm_provider == "openai":
            from openai import OpenAI
            client = OpenAI()
            response = client.chat.completions.create(
                model=config.get("llm_model", "gpt-4o-mini"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content.strip()
        elif llm_provider == "gemini":
            from google import genai
            from google.genai import types
            client = genai.Client()
            response = client.models.generate_content(
                model=config.get("gemini_llm_model", "gemini-2.0-flash"),
                contents=[system_prompt, user_prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            raw = response.text.strip()
        else:
            return _evaluate_generation_text_rules(feedback)

        data = json.loads(raw)
        return {
            "has_issue": data.get("has_issue", True),
            "issue_type": data.get("issue_type", "skill"),
            "explanation": data.get("explanation", ""),
            "proposed_changes": data.get("proposed_changes", {})
        }
    except Exception as e:
        run_logger.error(f"LLM 文本自进化失败: {e}")
        return _evaluate_generation_text_rules(feedback)


def _evaluate_generation_text_rules(feedback: str) -> dict:
    """V1: 基于本地规则匹配的文本反馈诊断"""
    config = load_config()
    proposed_changes = {}
    explanation = ""
    issue_type = "none"
    has_issue = False

    matched_desc = []
    for rule in EVOLUTION_RULES:
        if any(kw in feedback for kw in rule["keywords"]):
            has_issue = True
            rule_updates = rule["config_updates"]
            matched_desc.append(rule["description"])

            # 优先判断是否属于模型变形问题
            if "变形" in rule["description"] or "畸形" in rule["description"]:
                issue_type = "model"
                explanation = "画面存在形变或畸变，此为模型本身生成能力的限制。建议尝试更换更高级的生图后端（如切换至 DALL-E 3 或 ComfyUI 中的 Flux 模型）。"
                proposed_changes = {}
                break

            issue_type = "skill"

            # 计算修改后的具体目标配置值
            if "whitespace_weight_delta" in rule_updates:
                current = config.get("whitespace_weight", 1.0)
                new_val = max(0.1, min(3.0, current + rule_updates["whitespace_weight_delta"]))
                proposed_changes["whitespace_weight"] = round(new_val, 2)

            if "max_elements_per_image_delta" in rule_updates:
                current = config.get("max_elements_per_image", 8)
                new_val = max(2, min(20, current + rule_updates["max_elements_per_image_delta"]))
                proposed_changes["max_elements_per_image"] = new_val

            if "comfyui_steps_delta" in rule_updates:
                current = config.get("comfyui_steps", 25)
                new_val = max(10, min(60, current + rule_updates["comfyui_steps_delta"]))
                proposed_changes["comfyui_steps"] = new_val

            if "force_horizontal_whitespace_for_cover" in rule_updates:
                proposed_changes["force_horizontal_whitespace_for_cover"] = True

            if "log_suggestion" in rule_updates:
                explanation = f"配色诊断建议：{rule_updates['log_suggestion']}"

    if has_issue:
        if not explanation:
            explanation = f"检测到问题: {'; '.join(matched_desc)}。已生成对应的优化调参建议。"
    else:
        explanation = "未检测到明显问题或未匹配到已知反馈模式。"

    return {
        "has_issue": has_issue,
        "issue_type": issue_type,
        "explanation": explanation,
        "proposed_changes": proposed_changes
    }


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


def record_evolution_memory(
    style_name: str,
    payload: PromptPayload,
    issue_description: str,
    proposed_changes: dict,
    bad_image_path: str = None,
) -> str:
    """
    当触发自进化配置参数更新时，将对应的“教训记录”以结构化 JSON 保存至 memory/history 目录，
    并把引发问题的坏图片拷贝至 memory/bad_cases 目录下。

    Args:
        style_name: 发生问题的风格模板名称
        payload: 生图时的中台 PromptPayload
        issue_description: 用户的吐槽反馈或 Agent 视觉诊断内容
        proposed_changes: 本次调优修改的参数增量/目标值
        bad_image_path: (可选) 引发抱怨的 AI 生成的坏图文件路径

    Returns:
        保存的 JSON 文件绝对路径，若失败返回空字符串
    """
    if not style_name:
        style_name = payload.style or "未知风格"

    # 1. 如果提供了坏图，且该图片在本地存在，则将其拷贝至 memory/bad_cases/ 下，使用时间戳重命名
    saved_bad_image_ref = ""
    if bad_image_path and os.path.exists(bad_image_path):
        try:
            _, ext = os.path.splitext(bad_image_path)
            ext = ext if ext else ".png"
            new_bad_img_name = generate_timestamped_filename(prefix="bad_ref", ext=ext)
            dst_bad_img_path = os.path.join(MEMORY_BAD_CASES_DIR, new_bad_img_name)
            copy_file(bad_image_path, dst_bad_img_path)
            # 记录相对或绝对路径，这里使用相对于项目根目录的相对路径
            saved_bad_image_ref = os.path.join("creative_visual_skill", "memory", "bad_cases", new_bad_img_name)
            run_logger.info(f"坏图案例已保存至记忆库: {saved_bad_image_ref}")
        except Exception as e:
            run_logger.error(f"复制坏图至记忆库失败: {e}")

    # 2. 组装 JSON 记录
    timestamp = datetime.now().isoformat()
    record = {
        "timestamp": timestamp,
        "style_name": style_name,
        "article_subject": payload.subject,
        "prompt_used": payload.composition,
        "config_state_before": {
            "whitespace_weight": load_config().get("whitespace_weight", 1.2),
            "max_elements_per_image": load_config().get("max_elements_per_image", 6),
            "comfyui_steps": load_config().get("comfyui_steps", 30),
            "comfyui_cfg": load_config().get("comfyui_cfg", 7.0),
        },
        "bad_image_ref": saved_bad_image_ref,
        "issue_type": "skill" if proposed_changes else "model",
        "issue_description": issue_description,
        "action_taken": {
            "config_updates": proposed_changes
        }
    }

    # 3. 写入 json 文件，文件名如 memory_ref_2026xxxx_xxxxxx.json
    filename = generate_timestamped_filename(prefix="memory_ref", ext=".json")
    save_path = os.path.join(MEMORY_HISTORY_DIR, filename)

    try:
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        run_logger.info(f"已向记忆库写入问题记录: {save_path}")
        return save_path
    except Exception as e:
        run_logger.error(f"写入记忆库记录失败: {e}")
        return ""

