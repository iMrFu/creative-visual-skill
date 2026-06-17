"""
Creative Visual Skill — Module A: 文章分析器 (Article Analyzer)
V1: 基于 jieba 分词 + 关键词词典的规则分析
V2: LLM 增强分析（OpenAI / Gemini），失败时回退到 V1
"""

import json
import re
from collections import Counter
from typing import List, Dict, Optional

from .utils import ArticleInfo, run_logger
from .config import load_config


# ---------------------------------------------------------------------------
# jieba 分词：优雅降级
# ---------------------------------------------------------------------------
try:
    import jieba
    import jieba.posseg as pseg  # 词性标注
    _HAS_JIEBA = True
except ImportError:
    _HAS_JIEBA = False
    run_logger.warning("jieba 未安装，将使用简单空格分词作为降级方案")


# ===========================================================================
# 主题词典 — 关键词 → 主题类别
# ===========================================================================
TOPIC_DICT: Dict[str, str] = {
    # 科技
    "人工智能": "科技", "AI": "科技", "机器学习": "科技", "深度学习": "科技",
    "算法": "科技", "编程": "科技", "代码": "科技", "芯片": "科技",
    "互联网": "科技", "数据": "科技", "科技": "科技", "技术": "科技",
    "软件": "科技", "硬件": "科技", "创新": "科技", "数字化": "科技",
    "机器人": "科技", "自动驾驶": "科技", "大模型": "科技", "云计算": "科技",
    "区块链": "科技", "量子": "科技", "5G": "科技", "智能": "科技",
    # 教育
    "教育": "教育", "学习": "教育", "学校": "教育", "老师": "教育",
    "学生": "教育", "课程": "教育", "考试": "教育", "高考": "教育",
    "大学": "教育", "阅读": "教育", "知识": "教育", "成长": "教育",
    "育儿": "教育", "孩子": "教育", "家庭教育": "教育", "培训": "教育",
    "启蒙": "教育", "陪伴": "教育", "亲子": "教育", "幼儿园": "教育",
    # 情绪/心理
    "焦虑": "情绪/心理", "抑郁": "情绪/心理", "压力": "情绪/心理",
    "心理": "情绪/心理", "情绪": "情绪/心理", "内耗": "情绪/心理",
    "自愈": "情绪/心理", "疗愈": "情绪/心理", "冥想": "情绪/心理",
    "正念": "情绪/心理", "幸福": "情绪/心理", "孤独": "情绪/心理",
    "心理健康": "情绪/心理", "自我": "情绪/心理",
    # 商业/金融
    "创业": "商业/金融", "商业": "商业/金融", "经济": "商业/金融",
    "投资": "商业/金融", "股票": "商业/金融", "基金": "商业/金融",
    "金融": "商业/金融", "市场": "商业/金融", "品牌": "商业/金融",
    "营销": "商业/金融", "管理": "商业/金融", "融资": "商业/金融",
    "上市": "商业/金融", "利润": "商业/金融", "消费": "商业/金融",
    # 生活/健康
    "健康": "生活/健康", "运动": "生活/健康", "减肥": "生活/健康",
    "饮食": "生活/健康", "睡眠": "生活/健康", "养生": "生活/健康",
    "生活": "生活/健康", "日常": "生活/健康", "习惯": "生活/健康",
    "锻炼": "生活/健康", "瑜伽": "生活/健康", "跑步": "生活/健康",
    "医疗": "生活/健康", "保健": "生活/健康",
    # 文化/艺术
    "文化": "文化/艺术", "艺术": "文化/艺术", "音乐": "文化/艺术",
    "电影": "文化/艺术", "绘画": "文化/艺术", "文学": "文化/艺术",
    "诗歌": "文化/艺术", "设计": "文化/艺术", "摄影": "文化/艺术",
    "书法": "文化/艺术", "戏剧": "文化/艺术", "舞蹈": "文化/艺术",
    "展览": "文化/艺术", "博物馆": "文化/艺术",
    # 社会/政治
    "社会": "社会/政治", "政策": "社会/政治", "法律": "社会/政治",
    "公共": "社会/政治", "民生": "社会/政治", "政治": "社会/政治",
    "改革": "社会/政治", "制度": "社会/政治", "权利": "社会/政治",
    "公平": "社会/政治", "正义": "社会/政治", "舆论": "社会/政治",
    # 旅行/美食
    "旅行": "旅行/美食", "旅游": "旅行/美食", "美食": "旅行/美食",
    "风景": "旅行/美食", "景点": "旅行/美食", "酒店": "旅行/美食",
    "民宿": "旅行/美食", "攻略": "旅行/美食", "自驾": "旅行/美食",
    "餐厅": "旅行/美食", "烹饪": "旅行/美食", "食谱": "旅行/美食",
    "小吃": "旅行/美食", "探店": "旅行/美食",
}


# ===========================================================================
# 情绪词典 — 关键词 → 情绪基调
# ===========================================================================
EMOTION_DICT: Dict[str, str] = {
    # 温暖
    "温暖": "温暖", "感动": "温暖", "温馨": "温暖", "幸福": "温暖",
    "陪伴": "温暖", "爱": "温暖", "拥抱": "温暖", "善良": "温暖",
    "关怀": "温暖", "守护": "温暖", "亲情": "温暖",
    # 严肃
    "严肃": "严肃", "严谨": "严肃", "深刻": "严肃", "反思": "严肃",
    "批判": "严肃", "警醒": "严肃", "责任": "严肃", "使命": "严肃",
    # 冷静
    "冷静": "冷静", "理性": "冷静", "客观": "冷静", "分析": "冷静",
    "逻辑": "冷静", "思考": "冷静", "专业": "冷静", "务实": "冷静",
    # 激昂
    "激昂": "激昂", "热血": "激昂", "奋斗": "激昂", "拼搏": "激昂",
    "梦想": "激昂", "突破": "激昂", "挑战": "激昂", "激情": "激昂",
    "燃": "激昂", "振奋": "激昂",
    # 悲伤
    "悲伤": "悲伤", "难过": "悲伤", "痛苦": "悲伤", "失去": "悲伤",
    "离别": "悲伤", "遗憾": "悲伤", "怀念": "悲伤", "泪": "悲伤",
    "哀": "悲伤", "惋惜": "悲伤",
    # 幽默
    "幽默": "幽默", "搞笑": "幽默", "有趣": "幽默", "段子": "幽默",
    "笑": "幽默", "调侃": "幽默", "吐槽": "幽默", "梗": "幽默",
    # 浪漫
    "浪漫": "浪漫", "诗意": "浪漫", "唯美": "浪漫", "梦幻": "浪漫",
    "星空": "浪漫", "花": "浪漫", "月光": "浪漫", "美好": "浪漫",
    # 治愈
    "治愈": "治愈", "放松": "治愈", "宁静": "治愈", "平和": "治愈",
    "舒适": "治愈", "慢": "治愈", "安静": "治愈", "自然": "治愈",
    "释然": "治愈", "岁月静好": "治愈",
}


# ===========================================================================
# 名词词性集合（用于提取视觉主体）
# ===========================================================================
_NOUN_POS_TAGS = {"n", "nr", "ns", "nt", "nz", "ng", "vn"}

# 停用词（不作为关键词的常见词）
_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "他", "她", "它",
    "们", "那", "被", "从", "把", "让", "之", "个", "能", "可以",
    "过", "对", "而", "还", "与", "但", "为", "所", "其", "中",
    "或", "这个", "那个", "什么", "怎么", "如何", "因为", "所以",
    "虽然", "但是", "如果", "可能", "应该", "已经", "正在",
}


# ===========================================================================
# V1: 规则分析核心函数
# ===========================================================================

def _segment_text(text: str) -> List[str]:
    """使用 jieba 分词；降级时按空格 + 单字符拆分"""
    if _HAS_JIEBA:
        return list(jieba.cut(text))
    # 降级方案：按空格 / 标点粗切
    tokens = re.split(r'[\s,，。！？!?;；：:""''""、\n\r\t]+', text)
    return [t for t in tokens if t]


def _segment_with_pos(text: str) -> List[tuple]:
    """带词性标注的分词，返回 [(word, pos), ...]"""
    if _HAS_JIEBA:
        return [(w.word, w.flag) for w in pseg.cut(text)]
    # 降级方案：所有 token 标为 'x'（未知）
    tokens = _segment_text(text)
    return [(t, "x") for t in tokens]


def _extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """提取关键词：分词 → 去停用词 → 频率排序"""
    words = _segment_text(text)
    # 过滤：去停用词、去短词（单字符）、去纯标点/数字
    filtered = [
        w for w in words
        if w not in _STOPWORDS
        and len(w) >= 2
        and not re.match(r'^[\d\W]+$', w)
    ]
    counter = Counter(filtered)
    return [word for word, _ in counter.most_common(top_n)]


def _detect_topic(keywords: List[str]) -> str:
    """根据关键词匹配主题词典，返回得票最多的主题"""
    topic_votes: Counter = Counter()
    for kw in keywords:
        if kw in TOPIC_DICT:
            topic_votes[TOPIC_DICT[kw]] += 1
    if topic_votes:
        return topic_votes.most_common(1)[0][0]
    return "生活/健康"  # 默认主题


def _detect_emotion(text: str, keywords: List[str]) -> str:
    """根据文本和关键词匹配情绪词典，返回得票最多的情绪"""
    emotion_votes: Counter = Counter()
    # 先用全文扫描情绪词（覆盖面更广）
    for emo_word, emo_label in EMOTION_DICT.items():
        if emo_word in text:
            emotion_votes[emo_label] += 1
    # 再用关键词补充
    for kw in keywords:
        if kw in EMOTION_DICT:
            emotion_votes[EMOTION_DICT[kw]] += 1
    if emotion_votes:
        return emotion_votes.most_common(1)[0][0]
    return "冷静"  # 默认情绪


def _extract_subject(text: str, keywords: List[str]) -> str:
    """
    提取视觉主体：
    1. 优先从词性标注中取权重最高的名词短语
    2. 降级时取频率最高的关键词
    """
    if _HAS_JIEBA:
        # 用词性标注找名词
        pos_words = _segment_with_pos(text)
        noun_counter: Counter = Counter()
        for word, pos in pos_words:
            if pos in _NOUN_POS_TAGS and len(word) >= 2 and word not in _STOPWORDS:
                noun_counter[word] += 1
        # 关键词中的名词额外加权
        for kw in keywords:
            if kw in noun_counter:
                noun_counter[kw] += 2
        if noun_counter:
            return noun_counter.most_common(1)[0][0]
    # 降级：取第一个关键词
    if keywords:
        return keywords[0]
    return "抽象概念"


def _infer_emotional_tension(text: str, keywords: List[str], emotion: str) -> dict:
    """
    V1 规则兜底：从文本中推导情绪张力字段。
    策略：
    1. emotional_core：找文中的转折句（"但"/"然而"/"可是"后面的内容）
    2. conflict_point：找二选一句式（"要么...要么"/"不是...就是"）
    3. curiosity_gap：找疑问句（"为什么"/"如何"/"怎么"）
    4. empathy_anchor：找第二人称+情绪词组合（"你一定也..."/"你是不是也..."）
    5. emotional_arc：首段情绪词 vs 尾段情绪词，构造"从X到Y"
    """
    tension = {
        "emotional_core": "",
        "conflict_point": "",
        "curiosity_gap": "",
        "empathy_anchor": "",
        "emotional_arc": "",
    }

    # --- emotional_core: 转折句提取 ---
    turn_patterns = [
        r'[但然而可是却](.+?)[。！？\n]',
        r'不是(.+?)，而是(.+?)[。！？]',
    ]
    for pat in turn_patterns:
        matches = re.findall(pat, text)
        if matches:
            core = matches[0] if isinstance(matches[0], str) else matches[0][-1]
            tension["emotional_core"] = core.strip()[:50]
            break

    # --- conflict_point: 二选一句式 ---
    conflict_patterns = [
        r'要么(.+?)要么(.+?)[。！？]',
        r'不是(.+?)就是(.+?)[。！？]',
        r'管也不是，不管也不是',
        r'进退两难',
        r'左右为难',
    ]
    for pat in conflict_patterns:
        matches = re.findall(pat, text)
        if matches:
            val = matches[0] if isinstance(matches[0], str) else "".join(matches[0])
            tension["conflict_point"] = val.strip()[:50]
            break

    # --- curiosity_gap: 疑问句提取 ---
    question_matches = re.findall(r'(为什么|如何|怎么|凭什么|难道)(.+?)[？\?]', text)
    if question_matches:
        tension["curiosity_gap"] = (question_matches[0][0] + question_matches[0][1])[:50]
    else:
        any_q = re.findall(r'(.+?)[？\?]', text)
        if any_q:
            tension["curiosity_gap"] = any_q[0][:50]

    # --- empathy_anchor: 第二人称+情绪词 ---
    empathy_patterns = [
        r'你(一定也|是不是也|也曾|也许也)(.+?)[。！？]',
        r'我们(都|也)(.+?)[。！？]',
    ]
    for pat in empathy_patterns:
        matches = re.findall(pat, text)
        if matches:
            tension["empathy_anchor"] = ("你" + matches[0][0] + matches[0][1])[:50]
            break

    # --- emotional_arc: 首尾段情绪词对比 ---
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    if len(paragraphs) >= 2:
        first_emotion = _detect_emotion(paragraphs[0], keywords)
        last_emotion = _detect_emotion(paragraphs[-1], keywords)
        if first_emotion != last_emotion:
            tension["emotional_arc"] = f"从{first_emotion}到{last_emotion}"
        else:
            tension["emotional_arc"] = f"始终{first_emotion}"
    elif paragraphs:
        tension["emotional_arc"] = _detect_emotion(paragraphs[0], keywords)

    return tension


def _analyze_rule_based(text: str) -> ArticleInfo:
    """V1 规则分析入口"""
    if not text or not text.strip():
        run_logger.warning("文章文本为空，返回默认 ArticleInfo")
        return ArticleInfo(
            topic="生活/健康",
            emotion="冷静",
            keywords=[],
            subject="抽象概念",
        )

    keywords = _extract_keywords(text)
    topic = _detect_topic(keywords)
    emotion = _detect_emotion(text, keywords)
    subject = _extract_subject(text, keywords)

    # V3: 规则推导情绪张力
    tension = _infer_emotional_tension(text, keywords, emotion)

    run_logger.info(
        f"[V1 规则分析] topic={topic}, emotion={emotion}, "
        f"subject={subject}, keywords={keywords[:5]}"
    )
    return ArticleInfo(
        topic=topic,
        emotion=emotion,
        keywords=keywords,
        subject=subject,
        emotional_core=tension["emotional_core"],
        conflict_point=tension["conflict_point"],
        curiosity_gap=tension["curiosity_gap"],
        empathy_anchor=tension["empathy_anchor"],
        emotional_arc=tension["emotional_arc"],
    )



# ===========================================================================
# V2: LLM 增强分析
# ===========================================================================

_LLM_SYSTEM_PROMPT = """你是一位资深的中文文章分析专家。请分析以下文章，并以严格的 JSON 格式输出分析结果。

要求：
1. topic: 文章主题类别，从以下选项中选择一个：
   科技、教育、情绪/心理、商业/金融、生活/健康、文化/艺术、社会/政治、旅行/美食
2. emotion: 文章的情绪基调，从以下选项中选择一个：
   温暖、严肃、冷静、激昂、悲伤、幽默、浪漫、治愈
3. keywords: 5-8 个核心关键词（中文），以列表形式输出
4. subject: 一个最能代表文章核心视觉意象的名词短语（2-6 个字），用于生成封面配图

只输出 JSON，不要添加任何其他文字或 markdown 格式。
示例输出：
{"topic": "教育", "emotion": "温暖", "keywords": ["孩子", "成长", "陪伴", "阅读", "家庭"], "subject": "亲子阅读"}
"""


def _parse_llm_json(raw_text: str) -> Optional[dict]:
    """从 LLM 返回的文本中提取 JSON 对象"""
    # 尝试直接解析
    text = raw_text.strip()
    # 移除可能的 markdown 代码块标记
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试从文本中找到 JSON 对象
    match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def _build_merged_llm_system_prompt() -> str:
    """
    动态构建五合一大合并大模型系统提示词，
    将风格库、钩子库定义注入上下文，并声明美学防走样和封面排版规则。
    """
    try:
        from .style_library import list_styles
        from .hook_designer import list_hook_strategies

        styles = list_styles()
        hooks, comp_strategies = list_hook_strategies()

        # 简化风格列表以节约 Token
        styles_summary = []
        for s in styles:
            styles_summary.append({
                "style_name": s.style_name,
                "colors": s.colors,
                "background": s.background,
                "composition_template": s.composition,
                "tags": s.tags
            })

        hooks_summary = []
        for h in hooks:
            hooks_summary.append({
                "hook_type": h["hook_type"],
                "hook_type_cn": h["hook_type_cn"],
                "principle": h["principle"],
                "compatible_composition_strategies": h["compatible_composition_strategies"]
            })

        comp_summary = []
        for c in comp_strategies:
            comp_summary.append({
                "composition_strategy": c["composition_strategy"],
                "composition_strategy_cn": c["composition_strategy_cn"],
                "principle": c["principle"],
                "layout_keywords": c["layout_keywords"]
            })
    except Exception as e:
        run_logger.warning(f"动态构建大合并 Prompt 失败: {e}，将降级到静态系统提示词。")
        return _LLM_SYSTEM_PROMPT

    prompt = (
        "你是一位顶级中文文章分析专家、视觉创意总监和读者点击心理学专家。\n"
        "你的任务是：深入分析给定的中文文章，为其设计一张能够引发情感共鸣、制造悬念、有极强“点击驱动力”的公众号封面视觉概念 JSON，并将选定的艺术画风完美融入其中（美学融合保护）。\n\n"
        "【分析与设计步骤】\n"
        "1. 提取基础属性 (topic, emotion, keywords, subject)。\n"
        "2. 提取文章的情绪张力 (emotional_core, conflict_point, curiosity_gap, empathy_anchor, emotional_arc)。\n"
        "3. 匹配最合适的风格：从以下可用的风格列表中选择一个 (必须是已有的名字，不可凭空捏造)。\n"
        "4. 选择一个最具点击吸引力的视觉钩子策略，以及与其兼容的一个构图策略。\n"
        "5. 完全重写英文视觉概念 (visual_concept) 并实施“美学融合保护”：\n"
        "   - 重写的 visual_concept（英文）必须直接用作生图模型的核心提示词描述。\n"
        "   - 【美学融合保护】：重写的概念绝不能只描述构图与动作。必须将所选风格的媒介特质（如 watercolor elements, cyber neon glow, classic oil texture, scrapbook paper collage）、配色方案（colors）和背景基调（background）以英文修饰词的形式自然、有机地融入视觉概念的描述中。让重写后的概念在保留原始风格画风基底的基础上，加入钩子故事性。\n"
        "   - 【封面排版留白】：对于 2.35:1 比例，必须在右侧或左侧预留大面积用于放置标题的空白（whitespace / large empty space for text overlay）。\n\n"
        "【可用风格列表】\n"
        f"{json.dumps(styles_summary, ensure_ascii=False, indent=2)}\n\n"
        "【可用钩子策略】\n"
        f"{json.dumps(hooks_summary, ensure_ascii=False, indent=2)}\n\n"
        "【可用构图策略】\n"
        f"{json.dumps(comp_summary, ensure_ascii=False, indent=2)}\n\n"
        "【输出 JSON 格式要求】\n"
        "必须输出严格符合以下结构的 JSON 字符串（不要有任何 markdown 标记或前导解释文字）：\n"
        "{\n"
        '  "topic": "主题类别，必须是 科技/教育/情绪\\/心理/商业\\/金融/生活\\/健康/文化\\/艺术/社会\\/政治/旅行\\/美食 之一",\n'
        '  "emotion": "情感基调，必须是 温暖/严肃/冷静/激昂/悲伤/幽默/浪漫/治愈 之一",\n'
        '  "keywords": ["关键词1", "关键词2", ...],\n'
        '  "subject": "核心视觉主体名词短语（2-6字）",\n'
        '  "emotional_core": "最引发共鸣/最刺痛的一句话（20字以内）",\n'
        '  "conflict_point": "揭示的核心矛盾，若无则留空",\n'
        '  "curiosity_gap": "读者想知道的信息缺口，若无则留空",\n'
        '  "empathy_anchor": "引发“这说我呢”共鸣的一句话，若无则留空",\n'
        '  "emotional_arc": "情绪走向，格式如“从X到Y”，若无则留空",\n'
        '  "matched_style": "选中的风格名称 (必须是风格列表中精确的名字)",\n'
        '  "hook_payload": {\n'
        '    "hook_type": "选中的钩子类型 hook_type",\n'
        '    "hook_type_cn": "选中的钩子中文名",\n'
        '    "composition_strategy": "选中的构图策略名称",\n'
        '    "composition_strategy_cn": "构图策略中文名",\n'
        '    "visual_concept": "美学融合保护下重写的完整英文视觉概念描述，直接用于生图，包含媒介、构图、主体和画面细节",\n'
        '    "visual_concept_cn": "中文视觉概念摘要",\n'
        '    "hook_rationale": "策略说明：解释该钩子如何企合张力，以及如何混合与保留所选风格美学的"\n'
        '  }\n'
        "}"
    )
    return prompt


def _analyze_with_openai(text: str, config: dict) -> Optional[ArticleInfo]:
    """调用 OpenAI API 分析文章 (大合并调用)"""
    try:
        import openai

        model = config.get("llm_model", "gpt-4o-mini")
        base_url = config.get("openai_base_url", "") or None
        client = openai.OpenAI(base_url=base_url)

        system_prompt = _build_merged_llm_system_prompt()
        run_logger.info(f"[V2 OpenAI] 使用模型 {model} 执行大合并分析与视觉钩子设计...")

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"请分析并设计以下文章：\n\n{text[:4000]}"},
            ],
            temperature=0.3,
            max_tokens=1200,
            response_format={"type": "json_object"} if model != "gpt-3.5-turbo" else None,
        )

        raw = response.choices[0].message.content
        parsed = _parse_llm_json(raw)
        if parsed:
            result = ArticleInfo.from_dict(parsed)
            run_logger.info(
                f"[V2 OpenAI] 大合并分析与设计成功 — topic={result.topic}, matched_style={result.matched_style}"
            )
            return result
        else:
            run_logger.warning(f"[V2 OpenAI] 无法解析 LLM 输出: {raw[:200]}")
            return None

    except ImportError:
        run_logger.warning("[V2 OpenAI] openai SDK 未安装")
        return None
    except Exception as e:
        run_logger.error(f"[V2 OpenAI] API 调用失败: {e}")
        return None


def _analyze_with_gemini(text: str, config: dict) -> Optional[ArticleInfo]:
    """调用 Gemini API 分析文章 (大合并调用)"""
    try:
        from google import genai
        from google.genai import types

        model_name = config.get("gemini_llm_model", "gemini-2.0-flash")
        client = genai.Client()

        system_prompt = _build_merged_llm_system_prompt()
        run_logger.info(f"[V2 Gemini] 使用模型 {model_name} 执行大合并分析与视觉钩子设计...")

        full_prompt = (
            f"{system_prompt}\n\n"
            f"请分析并设计以下文章：\n\n{text[:4000]}"
        )

        response = client.models.generate_content(
            model=model_name,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
                max_tokens=1200,
            )
        )

        raw = response.text
        parsed = _parse_llm_json(raw)
        if parsed:
            result = ArticleInfo.from_dict(parsed)
            run_logger.info(
                f"[V2 Gemini] 大合并分析与设计成功 — topic={result.topic}, matched_style={result.matched_style}"
            )
            return result
        else:
            run_logger.warning(f"[V2 Gemini] 无法解析 LLM 输出: {raw[:200]}")
            return None

    except ImportError:
        run_logger.warning("[V2 Gemini] google-genai SDK 未安装")
        return None
    except Exception as e:
        run_logger.error(f"[V2 Gemini] API 调用失败: {e}")
        return None


# ===========================================================================
# 公共接口
# ===========================================================================

def analyze_article(
    article_text: str,
    use_llm: bool = False,
    llm_provider: str = "openai",
) -> ArticleInfo:
    """
    分析文章内容，提取主题、情绪、关键词和视觉主体。

    Args:
        article_text: 文章正文
        use_llm: 是否启用 LLM 增强分析（V2）
        llm_provider: LLM 提供商，"openai" 或 "gemini"

    Returns:
        ArticleInfo 数据类实例
    """
    run_logger.info(
        f"开始分析文章 (长度={len(article_text)}, "
        f"use_llm={use_llm}, provider={llm_provider})"
    )

    # --- V2: LLM 分析 ---
    if use_llm:
        config = load_config()
        provider = llm_provider.lower().strip()

        result = None
        if provider == "gemini":
            result = _analyze_with_gemini(article_text, config)
        else:
            result = _analyze_with_openai(article_text, config)

        if result is not None:
            return result

        run_logger.warning("[V2] LLM 分析失败，回退到 V1 规则分析")

    # --- V1: 规则分析 ---
    return _analyze_rule_based(article_text)
