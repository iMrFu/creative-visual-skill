"""
Creative Visual Skill — Module F: 素材注入 & 二次确认
检测用户保存意图 → 解析风格信息 → 二次确认 → 存入风格库
"""

import os
import re
import json
from typing import Optional

from utils import StyleInfo, run_logger
from config import load_config
from style_library import add_style_to_library, save_image_to_library


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
        "你是一个优秀的自媒体视觉风格解析助手。用户会用自然语言描述一种图片风格，"
        "请你将其解析为以下 JSON 结构，并严格遵守解析原则：\n\n"
        "【解析原则】\n"
        "1. 变量主体抽象：用户描述中用于生图的可变核心主体必须用 `[SUBJECT]` 占位符代替。"
        "如果是用户输入的描述文本（没有占位符 [SUBJECT]），但包含某个具体明确的单数物品主体（如“打字机”、“咖啡杯”、“闹钟”、“绿毛衣”），"
        "你应当智能找出描述中最核心的、适合作为主要生图物品的核心主体，并在生成的 JSON 构图（composition）和背景（background）中将该主体名称用 `[SUBJECT]` 替换。\n"
        "2. 固定场景元素保留：描述中具体指明的道具、陈设、环境要素（如'深绿色羊毛衫'、'木桌'、'蜡烛'、'数据卡片'等）属于此风格不可分割的**固定场景特征**，**必须原样保留**在 `composition` 或 `background` 描述中，作为生成每一张图时的固定视觉元素。\n"
        "3. 字段解释：\n"
        "   - style_name: 风格简称（不超过10字，如'秋日温暖复古风'）\n"
        "   - subject_placeholder: 固定为 '[SUBJECT]'\n"
        "   - composition: 详细的画面构图描述，包含 `[SUBJECT]` 在画面中的位置，以及周围摆放的固定元素\n"
        "   - colors: 包含3-6个契合该风格的英文颜色或色彩描述词\n"
        "   - background: 详细的环境背景氛围描述，可包含固定的背景陈设要素\n"
        "   - negative: 排除的负向元素词列表\n"
        "   - tags: 风格相关的中英文检索标签列表\n\n"
        "【JSON结构】\n"
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
        "只返回合法 JSON，不要添加任何解释性文字或 Markdown 代码块包裹（如 ```json）。"
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
            from google import genai
            from google.genai import types
            model_name = config.get("gemini_llm_model", "gemini-2.0-flash")
            client = genai.Client()
            response = client.models.generate_content(
                model=model_name,
                contents=f"{system_prompt}\n\n用户输入：\n{user_input}",
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


def _is_image_path(text: str) -> bool:
    """检查文本是否是合法的本地图片文件路径"""
    text_stripped = text.strip()
    # 移除首尾引号
    for quote in ['"', "'", "“", "”"]:
        if text_stripped.startswith(quote) and text_stripped.endswith(quote):
            text_stripped = text_stripped[1:-1].strip()
    
    # 检查后缀名
    _, ext = os.path.splitext(text_stripped)
    if ext.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
        # 检查文件是否存在
        return os.path.exists(text_stripped)
    return False


def _parse_style_from_image(
    image_path: str,
    use_llm: bool = False,
    llm_provider: str = "openai",
) -> Optional[StyleInfo]:
    """
    当用户直接提供图片时，调用 Vision LLM 识别该图片的视觉特征并反向工程生成 StyleInfo 结构。
    """
    if not use_llm:
        run_logger.warning("注册图片风格必须启用大模型模型 (--use-llm)")
        print("❌ 错误：注册图片风格必须启用大模型以进行视觉多模态分析，请追加参数 --use-llm")
        return None

    config = load_config()

    system_prompt = (
        "你是一个精通自媒体视觉风格解析的多模态视觉审计专家。\n"
        "请仔细观察这张图片，反推并构思能够完美复现该图片风格的 AI 生图配置参数，"
        "并输出为符合以下 JSON 结构的配置。请严格遵守解析原则：\n\n"
        "【解析原则】\n"
        "1. 核心主体提取与抽象：识别出图片中最显眼的主体，并将其抽象替换为 `[SUBJECT]`。\n"
        "   （例如，如果画面中心是一个老旧的打字机，在 `composition` 或 `background` 描述中将其写为 `[SUBJECT]`，"
        "   表示该位置可以被任何其他主体动态替换。同时，把原主体名称，如“打字机”放入 tags 中）。\n"
        "2. 固定场景元素保留：识别出属于该风格特有且每次都应该保留的固定摆设、道具或环境元素（如木桌、蜡烛、咖啡渍、周围散落的纸张等），原样保留在 `composition` 或 `background` 字段中。\n"
        "3. 构图描述 (composition)：细致描述图片呈现出的空间分布（如主体偏左、三分法、大面积留白、特定视角、特写等）并融入 `[SUBJECT]` 占位符。\n"
        "4. 配色体系 (colors)：列出 3-6 个最能代表该图片主色调、辅助色或氛围色彩的英文词或色彩词。\n"
        "5. 背景描述 (background)：分析背景环境的纹理、材质、虚化程度、光线效果（如微弱烛光、暗影、模糊牛皮纸质感、强对比偏光等）。\n"
        "6. 排除要素 (negative)：提炼出为了防止生图变形或偏离风格需要排除的要素词。\n"
        "7. 检索标签 (tags)：生成 5-10 个便于检索的风格中英文标签。\n\n"
        "【JSON结构】\n"
        "{\n"
        '  "style_name": "风格名称",\n'
        '  "subject_placeholder": "[SUBJECT]",\n'
        '  "composition": "构图描述",\n'
        '  "colors": ["颜色1", "颜色2"],\n'
        '  "background": "背景描述",\n'
        '  "negative": ["不要的元素1"],\n'
        '  "tags": ["标签1", "标签2"],\n'
        '  "examples": []\n'
        "}\n"
        "只返回合法 JSON，不要添加任何解释性文字或 Markdown 代码块包裹（如 ```json）。"
    )

    try:
        if llm_provider == "openai":
            import openai
            import base64
            model = config.get("llm_model", "gpt-4o-mini")
            client = openai.OpenAI()

            with open(image_path, "rb") as f:
                img_bytes = f.read()
            img_b64 = base64.b64encode(img_bytes).decode("utf-8")
            ext = os.path.splitext(image_path)[1].lower()
            mime_type = "image/png" if "png" in ext else "image/jpeg"
            image_url = f"data:{mime_type};base64,{img_b64}"

            user_content = [
                {"type": "text", "text": "请分析下面这张图片的生图视觉风格并转为 JSON"},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.3,
                max_tokens=800,
                response_format={"type": "json_object"} if model != "gpt-3.5-turbo" else None,
            )
            raw = response.choices[0].message.content.strip()

        elif llm_provider == "gemini":
            from google import genai
            from google.genai import types
            from PIL import Image
            model_name = config.get("gemini_llm_model", "gemini-2.0-flash")
            client = genai.Client()
            img = Image.open(image_path)

            response = client.models.generate_content(
                model=model_name,
                contents=[system_prompt, img, "请分析上面这张图片的生图视觉风格并转为 JSON"],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.3,
                )
            )
            raw = response.text.strip()
        else:
            run_logger.warning(f"不支持的多模态提供商: {llm_provider}")
            return None

        # 提取 JSON
        json_match = re.search(r'\{[\s\S]*\}', raw)
        if not json_match:
            run_logger.warning("Vision LLM 解析内容中未找到有效 JSON")
            return None

        data = json.loads(json_match.group())
        style = StyleInfo.from_dict(data)
        run_logger.info(f"Vision LLM 图片解析成功: {style.style_name}")
        return style

    except Exception as e:
        run_logger.error(f"Vision LLM 图片解析失败: {e}")
        return None


def _add_subject_placeholder_via_llm(
    style_info: StyleInfo,
    llm_provider: str = "openai",
) -> Optional[StyleInfo]:
    """
    当风格中没有 [SUBJECT] 时，让 AI 智能识别构图或背景中的核心物品，
    并自动替换为 [SUBJECT]。
    """
    config = load_config()
    system_prompt = (
        "你是一个生图参数改写专家。这有一个 AI 生图风格卡片的 JSON，"
        "它的 composition 或 background 缺乏 `[SUBJECT]` 占位符。\n"
        "你的任务是：\n"
        "1. 智能推断出当前描述中哪一个具体的名词最适合作为可变主体（例如“老旧打字机”、“咖啡杯”、“闹钟”）。\n"
        "2. 将 composition 或 background 中对应的名词替换为 `[SUBJECT]` 占位符（例如将'一个老式闹钟放在桌上'改写为'一个 [SUBJECT] 放在桌上'）。\n"
        "3. 把被替换掉的名词原词放入 tags 列表中以作保留，然后输出改写后的完整 JSON。\n\n"
        "只返回合法 JSON，不要有任何 markdown 格式或解释文本。"
    )

    try:
        style_json = json.dumps(style_info.to_dict(), ensure_ascii=False)
        
        if llm_provider == "openai":
            import openai
            model = config.get("llm_model", "gpt-4o-mini")
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": style_json},
                ],
                temperature=0.2,
                max_tokens=600,
                response_format={"type": "json_object"} if model != "gpt-3.5-turbo" else None,
            )
            raw = response.choices[0].message.content.strip()

        elif llm_provider == "gemini":
            from google import genai
            from google.genai import types
            model_name = config.get("gemini_llm_model", "gemini-2.0-flash")
            client = genai.Client()
            response = client.models.generate_content(
                model=model_name,
                contents=f"{system_prompt}\n\n当前JSON：\n{style_json}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                )
            )
            raw = response.text.strip()
        else:
            return None

        json_match = re.search(r'\{[\s\S]*\}', raw)
        if not json_match:
            return None
        
        data = json.loads(json_match.group())
        return StyleInfo.from_dict(data)

    except Exception as e:
        run_logger.error(f"注入占位符失败: {e}")
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

def confirm_and_save(
    style_info: StyleInfo,
    interactive: bool = True,
    llm_provider: str = "openai",
) -> bool:
    """
    展示解析结果并请求用户确认保存。

    Args:
        style_info:  待保存的风格信息
        interactive: True 时等待用户输入确认；False 时自动确认（程序化调用）
        llm_provider: 用于二次推断 [SUBJECT] 的模型提供商

    Returns:
        True 如果成功保存，False 如果取消
    """
    # 检查 [SUBJECT] 是否存在于 composition 或 background
    has_placeholder = (
        style_info.subject_placeholder in style_info.composition or
        style_info.subject_placeholder in style_info.background
    )

    if not has_placeholder:
        print("\n" + "!" * 50)
        print("⚠️ 警报：解析后的风格中没有检测到 '[SUBJECT]' 占位符！")
        print("这意味未来的生图任务中，画面主体将无法根据文章内容进行动态替换（主体将写死）。")
        print("!" * 50)
        
        if interactive:
            print("\n建议操作选项：")
            print("  [1] 作为【固定无主体风格】直接保存")
            print("  [2] 启动 AI 自动推断并插入 '[SUBJECT]' 占位符")
            print("  [3] 取消保存，重新输入描述词")
            choice = input("请输入您的选择 (1/2/3, 默认为 2): ").strip()
            
            if choice == "3":
                print("❌ 已取消，未修改任何文件。")
                return False
            elif choice == "1":
                print("ℹ️ 确认以完全写死的固定场景风格保存。")
            else:
                # 默认为 2 或用户选 2
                print("🔄 正在调用 AI 智能识别并注入 '[SUBJECT]'...")
                updated_style = _add_subject_placeholder_via_llm(style_info, llm_provider)
                if updated_style:
                    style_info = updated_style
                    print("✅ 智能注入完成！已为您重新生成风格定义。")
                else:
                    print("⚠️ AI 智能注入失败，将按原稿展示。")

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
    完整的素材注入流程：图片/文本检测 → 触发检测 → 解析 → 确认 → 保存。

    Args:
        user_input:  用户输入文本或图片路径
        use_llm:     是否使用 LLM 增强解析
        interactive: 是否需要交互式确认

    Returns:
        True 如果成功保存，False 如果未触发 / 取消 / 失败
    """
    # 1. 检查是否为合法的图片路径
    is_img = _is_image_path(user_input)

    # 2. 如果不是图片，检查文本触发词
    if not is_img and not check_save_trigger(user_input):
        run_logger.debug("未检测到素材注入触发词或合法的图片路径")
        return False

    config = load_config()
    llm_provider = config.get("llm_provider", "openai")

    if is_img:
        run_logger.info(f"检测到输入为图片路径: {user_input}，开始 Vision 风格反推...")
        print(f"📷 检测到本地图片：{user_input}\n🔍 正在通过 {llm_provider} 视觉多模态进行反推解析，请稍候...")
        style_info = _parse_style_from_image(user_input, use_llm=use_llm, llm_provider=llm_provider)
        if not style_info:
            print("❌ 图片风格反推解析失败，请检查模型配置与 API Key。")
            return False
        
        # 将输入图片拷贝到风格库的 image 目录
        rel_img_path = save_image_to_library(user_input)
        if rel_img_path:
            style_info.examples = [rel_img_path]
    else:
        run_logger.info("检测到素材注入触发词，开始文本风格解析...")
        style_info = parse_style_from_input(user_input, use_llm=use_llm, llm_provider=llm_provider)

    # 3. 确认并保存
    return confirm_and_save(style_info, interactive=interactive, llm_provider=llm_provider)
