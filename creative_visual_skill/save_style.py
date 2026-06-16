"""
Creative Visual Skill — Module F: 素材注入 & 二次确认
检测用户保存意图 → 解析风格信息 → 二次确认 → 存入风格库
"""

import re
import json
from typing import Optional

from utils import StyleInfo, run_logger
from config import load_config
from style_library import add_style_to_library


# ===========================================================================
# 1. 触发词检测
# ===========================================================================

def check_save_trigger(user_input: str) -> bool:
    """
    检查用户输入中是否包含素材注入触发词。
    触发词列表从 config.json 的 TARGET_KEYWORDS 读取。

    Args:
        user_input: 用户输入文本

    Returns:
        True 如果匹配到任意触发词
    """
    config = load_config()
    keywords = config.get("TARGET_KEYWORDS", [])
    text = user_input.strip()
    return any(kw in text for kw in keywords)


# ===========================================================================
# 2. 风格解析
# ===========================================================================

# --- 预定义关键词词典，用于规则解析 ---
_COMPOSITION_KEYWORDS = [
    "居中构图", "对称构图", "三分法", "黄金分割",
    "留白", "满铺", "对角线构图", "框架构图",
    "centered", "symmetrical", "rule of thirds",
]

_COLOR_KEYWORDS = [
    "暖色", "冷色", "高饱和", "低饱和", "莫兰迪",
    "黑白", "金色", "渐变", "撞色", "同色系",
    "红", "橙", "黄", "绿", "蓝", "紫", "粉",
    "warm tones", "cool tones", "pastel", "vibrant",
]

_BACKGROUND_KEYWORDS = [
    "纯色背景", "渐变背景", "模糊背景", "透明背景",
    "场景背景", "白色背景", "黑色背景", "简约背景",
    "solid background", "gradient background", "blurred background",
]


def _extract_quoted_text(text: str) -> Optional[str]:
    """提取引号内的文本（中文或英文引号）"""
    patterns = [
        r'[「](.+?)[」]',
        r'[『](.+?)[』]',
        r'[《](.+?)[》]',
        r'"(.+?)"',
        r"'(.+?)'",
        r'"(.+?)"',
    ]
    for pat in patterns:
        match = re.search(pat, text)
        if match:
            return match.group(1).strip()
    return None


def _extract_keywords_from_text(text: str, keyword_list: list) -> list:
    """从文本中提取匹配的关键词"""
    return [kw for kw in keyword_list if kw in text]


def _parse_v1_rule_based(user_input: str) -> StyleInfo:
    """
    V1 规则解析：从用户文本中提取风格信息。
    - 风格名：取第一行或引号内文本
    - 构图 / 颜色 / 背景：关键词匹配
    - 缺失字段填充合理默认值
    """
    lines = user_input.strip().split("\n")

    # --- 提取风格名 ---
    style_name = _extract_quoted_text(user_input)
    if not style_name:
        # 取第一行作为风格名（去掉触发词前缀）
        first_line = lines[0].strip()
        # 去掉可能的触发词前缀
        config = load_config()
        for kw in config.get("TARGET_KEYWORDS", []):
            first_line = first_line.replace(kw, "").strip()
        # 去掉标点
        first_line = re.sub(r'^[：:,，\s]+', '', first_line)
        style_name = first_line if first_line else "未命名风格"

    full_text = user_input.lower()

    # --- 构图 ---
    compositions = _extract_keywords_from_text(full_text, _COMPOSITION_KEYWORDS)
    composition = compositions[0] if compositions else "居中构图"

    # --- 颜色 ---
    colors = _extract_keywords_from_text(full_text, _COLOR_KEYWORDS)
    if not colors:
        colors = ["自然配色"]

    # --- 背景 ---
    backgrounds = _extract_keywords_from_text(full_text, _BACKGROUND_KEYWORDS)
    background = backgrounds[0] if backgrounds else "简约背景"

    # --- 标签：汇总所有已提取关键词 ---
    tags = list(set(compositions + colors + backgrounds))
    if not tags:
        tags = [style_name]

    # --- 默认负面提示 ---
    negative = ["低质量", "模糊", "变形", "水印"]

    return StyleInfo(
        style_name=style_name,
        subject_placeholder="[SUBJECT]",
        composition=composition,
        colors=colors,
        background=background,
        negative=negative,
        tags=tags,
        examples=[],
    )


def _parse_v2_llm_enhanced(user_input: str, llm_provider: str = "openai") -> Optional[StyleInfo]:
    """
    V2 LLM 增强解析：调用大语言模型将自然语言描述解析为 StyleInfo JSON。
    支持 OpenAI / Gemini 两种 provider。

    Returns:
        StyleInfo 或 None（失败时回退到 V1）
    """
    config = load_config()

    system_prompt = (
        "你是一个视觉风格解析助手。用户会用自然语言描述一种图片风格，"
        "请你将其解析为以下 JSON 结构（字段全部必填）：\n"
        "{\n"
        '  "style_name": "风格名称",\n'
        '  "subject_placeholder": "[SUBJECT]",\n'
        '  "composition": "构图方式",\n'
        '  "colors": ["颜色1", "颜色2"],\n'
        '  "background": "背景描述",\n'
        '  "negative": ["不需要的元素1"],\n'
        '  "tags": ["标签1", "标签2"],\n'
        '  "examples": []\n'
        "}\n"
        "只返回合法 JSON，不要添加其他文字。"
    )

    try:
        if llm_provider == "openai":
            import openai
            model = config.get("llm_model", "gpt-4o-mini")
            response = openai.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            raw = response.choices[0].message.content.strip()

        elif llm_provider == "gemini":
            import google.generativeai as genai
            model_name = config.get("gemini_llm_model", "gemini-2.0-flash")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                f"{system_prompt}\n\n用户输入：\n{user_input}"
            )
            raw = response.text.strip()

        else:
            run_logger.warning(f"不支持的 LLM provider: {llm_provider}，回退到规则解析")
            return None

        # 提取 JSON（可能被 ```json ``` 包裹）
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if not json_match:
            run_logger.warning("LLM 返回内容中未找到有效 JSON")
            return None

        data = json.loads(json_match.group())
        style = StyleInfo.from_dict(data)
        run_logger.info(f"LLM 解析成功: {style.style_name}")
        return style

    except Exception as e:
        run_logger.warning(f"LLM 解析失败 ({llm_provider}): {e}，将回退到规则解析")
        return None


def parse_style_from_input(
    user_input: str,
    use_llm: bool = False,
    llm_provider: str = "openai",
) -> StyleInfo:
    """
    解析用户输入为 StyleInfo 对象。

    Args:
        user_input:    用户的自然语言描述
        use_llm:       是否启用 LLM 增强解析 (V2)
        llm_provider:  LLM 服务商 ('openai' | 'gemini')

    Returns:
        解析后的 StyleInfo
    """
    if use_llm:
        result = _parse_v2_llm_enhanced(user_input, llm_provider)
        if result is not None:
            return result
        run_logger.info("LLM 解析失败，回退到 V1 规则解析")

    return _parse_v1_rule_based(user_input)


# ===========================================================================
# 3. 二次确认 & 保存
# ===========================================================================

def confirm_and_save(style_info: StyleInfo, interactive: bool = True) -> bool:
    """
    展示解析结果并请求用户确认保存。

    Args:
        style_info:  待保存的风格信息
        interactive: True 时等待用户输入确认；False 时自动确认（程序化调用）

    Returns:
        True 如果成功保存，False 如果取消
    """
    # 展示格式化 JSON
    formatted = json.dumps(style_info.to_dict(), ensure_ascii=False, indent=2)
    print("=" * 50)
    print("📋 解析结果：")
    print(formatted)
    print("=" * 50)

    if interactive:
        answer = input(
            "⚠️ 检测到专属存库请求。以上为 AI 解析出的风格结构，\n"
            "是否确认保存到本 Skill 的内容库中？(y/n): "
        )
        if answer.strip().lower() not in ("y", "yes"):
            print("❌ 已取消，未修改任何文件。")
            run_logger.info(f"用户取消保存风格: {style_info.style_name}")
            return False

    # 执行保存
    try:
        add_style_to_library(style_info)
        print(f"✅ 风格「{style_info.style_name}」已成功保存到内容库！")
        run_logger.info(f"风格已保存: {style_info.style_name}")
        return True
    except Exception as e:
        print(f"❌ 保存失败: {e}")
        run_logger.error(f"保存风格失败: {e}")
        return False


# ===========================================================================
# 4. 完整流程入口
# ===========================================================================

def process_save_request(
    user_input: str,
    use_llm: bool = False,
    interactive: bool = True,
) -> bool:
    """
    完整的素材注入流程：触发检测 → 解析 → 确认 → 保存。

    Args:
        user_input:  用户输入文本
        use_llm:     是否使用 LLM 增强解析
        interactive: 是否需要交互式确认

    Returns:
        True 如果成功保存，False 如果未触发 / 取消 / 失败
    """
    # Step 1: 检测触发词
    if not check_save_trigger(user_input):
        run_logger.debug("未检测到素材注入触发词")
        return False

    run_logger.info("检测到素材注入触发词，开始解析...")

    # Step 2: 解析风格
    style_info = parse_style_from_input(user_input, use_llm=use_llm)

    # Step 3: 确认并保存
    return confirm_and_save(style_info, interactive=interactive)
