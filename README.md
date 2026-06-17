# Creative Visual Skill (CVSkill) — 自媒体视觉策划与跨模型生图中台

一个独立于具体运行平台、模块化设计的**“自媒体视觉策划 + 跨模型生图”**能力模块。系统通过定义统一的中台语义数据结构和交互协议，可以在本地 Python 脚本、Claude Skills、OpenAI Assistants、n8n 工作流、或自建 Agent 框架中无缝部署。

---

## 📌 项目定位

* **输入端**：自媒体长文章 / 公众号文章 (+ 可选的用户个性化风格素材，如特定的提示词与参考图)。
* **中台层**：统一的 JSON 提示词结构（`PromptPayload`），作为跨模型适配的“唯一真相源”。
* **输出端**：自适应生成公众号封面图 (宽幅 2.35:1) 与正文配图 (16:9 或其他比例)。
* **生图通道**：支持本地 ComfyUI API（Flux / SDXL 模型等）及云端生图接口（OpenAI / Gemini API 等）。
* **素材积累与演进**：支持“风格内容库”沉淀（Markdown 文件 + 物理素材图）以及基于用户真实反馈的配置“自进化”调优。

---

## 🛠️ 版本信息与版本控制

本仓库遵循语义化版本控制规范：
* **当前版本**：`1.0.0`
* **版本特征**：
  * **V1（规则驱动级）**：已完整实现并打通。支持基于 `jieba` 中文分词的文章分析、标签交集匹配的风格推荐、ComfyUI 宽幅布局翻译、基于特定触发词的风格注入确权、以及规则映射自进化。
  * **V2（大模型增强级）**：已在代码中完整保留入口。通过在 `creative_visual_skill/.env` 中配置 `OPENAI_API_KEY` 或 `GEMINI_API_KEY`，并带上 `--use-llm` 命令行参数，即可启用基于高级 Agent 的文章主体语义提取、大模型风格库结构化生成、以及 LLM Agent 诊断自进化调参。

---

## 📂 项目结构图

```bash
.
├── .gitignore                  # Git 忽略配置文件
├── README.md                   # 仓库主说明文档 (v1.0.0)
│
└── creative_visual_skill/      # CVSkill 能力模块根目录
    ├── main.py                 # CLI 主入口、交互式向导及 Agent 创作评分系统
    ├── config.py               # 全局配置加载与写入模块
    ├── config.json             # 动态重写的运行时配置文件 (声明 "version": "1.0.0")
    ├── utils.py                # 核心数据类 (ArticleInfo, StyleInfo等) 与辅助工具 (版本声明 "1.0.0")
    ├── article_analyzer.py     # 模块A：文章分析器 (V1分词 / V2大模型分析)
    ├── style_library.py        # 模块B：风格库管理器 (Markdown JSON 解析与匹配评分)
    ├── json_builder.py         # 模块C：中台 Payload 构建器
    ├── model_adapter.py        # 模块D：跨提供商提示词适配转译器
    ├── image_runner.py         # 模块E：生图执行器 (ComfyUI串行 / OpenAI / Gemini)
    ├── save_style.py           # 模块F：素材注入与二次确权流程
    ├── evolver.py              # 模块G：规则/LLM自进化优化模块
    ├── requirements.txt        # 项目依赖
    │
    ├── styles/                 # 风格素材库
    │   ├── style_library.md    # 风格库模板定义 (预置 6 大主流视觉风格)
    │   └── image/              # 预置 6 大风格的完整样例图片与用户素材目录
    │
    ├── workflows/              # ComfyUI API 工作流模板
    │   ├── sdxl_basic.json     # SDXL 基础工作流 API
    │   └── flux_basic.json     # Flux 基础工作流 API
    │
    ├── logs/                   # 日志目录
    │   ├── run.log             # 运行日志
    │   └── evolution.log       # 自进化日志
    │
    ├── output/                 # 最终生成的图片输出目录 (附 .gitkeep)
    │
    └── tests/                  # 完备单元测试套件 (包含 32 个 pytest 用例)
```

---

## ⚙️ 核心模块级设计说明

### 1. 模块 A：文章分析器 `ArticleAnalyzer`
* **职责**：从长文本中提取主题类别 (`topic`)、情感基调 (`emotion`)、核心关键词 (`keywords`) 及视觉主体语义 (`subject`)。
* **双模态支持**：
  * **V1（本地模式）**：通过 `jieba` 分词和自定义的高频词库、主题词库、情绪映射库实现提取。
  * **V2（大模型模式）**：向 LLM 发送结构化 Prompt，返回标准的 `ArticleInfo` JSON。

### 2. 模块 B：风格库管理 `StyleLibrary`
* **职责**：解析存储在 `styles/style_library.md` 中以 Markdown+JSON 形式定义的风格模板，根据文章的 `ArticleInfo` 的关键词集与风格 tags 进行交集得分比对，匹配最适合的 `StyleInfo` 并执行输出。

### 3. 模块 C：JSON 中台构建 `JsonBuilder`
* **职责**：将匹配到的 `StyleInfo` 中的 `subject_placeholder`（固定为 `[SUBJECT]`）全局替换为文章分析出的 `ArticleInfo.subject` 视觉主体，融合其他参数构建生成唯一的 JSON 中台数据协议 `PromptPayload`。

### 4. 模块 D：模型适配器 `ModelAdapters`
* **职责**：将统一的 `PromptPayload` 转译为不同生图模型所偏好的提示词格式。
  * **ComfyUI 适配**：构建逗号分隔的英文 tag 流，并针对横版比例进行布局转译（如当比率为 `2.35:1` 时，强制在正向词末尾追加 `horizontal layout, asymmetric composition with subject on left third, right side large whitespace area` 等控制指令）。
  * **OpenAI / Gemini 适配**：转化为纯正的自然语言故事性描述段落。

### 5. 模块 E：生图执行器 `ImageRunner`
* **职责**：将最终提示词投递给指定提供商执行图像渲染。
  * **本地 ComfyUI**：通过 REST API 交互。引入线程锁机制进行**严格的单任务串行队列**调度，在确认上一张图片已落盘之后才允许派发下一个生图任务，防范显存卡死或溢出。
  * **云端模型**：通过 SDK 传输给 DALL-E / Imagen 3，获取 Base64 或二进制数据保存。

### 6. 模块 F：素材注入与二次确权 `SaveStyle`
* **职责**：防止网络爆款提示词或新风格误写入风格文件。通过 `config.json` 中的 `TARGET_KEYWORDS` 矩阵进行意图识别。匹配到动作后执行规则或大模型结构化解析风格字段并以 JSON 展示。在终端通过 **`y/n` 交互式二次确权**通过后方可追加写入 `style_library.md` 底部。

### 7. 模块 G：自进化系统 `Evolver`
* **职责**：运行报错或用户反馈图片不理想时（例如通过 `--optimize "刚才生成的拼贴风画面太挤了"`），触发自进化。系统可结合最近运行日志与 Payload 执行规则重写或 LLM 分析，自动更新全局配置文件并留档于进化日志。

---

## 🗃️ 统一接口数据协议定义

### ArticleInfo (文章分析结构)
```json
{
  "topic": "教育",
  "emotion": "温暖",
  "keywords": ["亲子关系", "陪伴"],
  "subject": "亲子陪伴"
}
```

### StyleInfo (风格模板结构)
```json
{
  "style_name": "复古剪贴簿拼贴风",
  "subject_placeholder": "[SUBJECT]",
  "composition": "multi-layer collage, stickers, edges with whitespace",
  "colors": ["warm yellow", "dark brown"],
  "background": "vintage paper texture",
  "negative": ["distorted", "deformed", "too realistic"],
  "tags": ["collage", "vintage", "scrapbook"],
  "examples": []
}
```

### PromptPayload (JSON 提示词中台 - 唯一真相源)
```json
{
  "subject": "亲子陪伴",
  "style": "复古剪贴簿拼贴风",
  "composition": "multi-layer collage, stickers, edges with whitespace, [SUBJECT] on left",
  "colors": ["warm yellow", "dark brown"],
  "background": "vintage paper texture",
  "ratio": "2.35:1",
  "negative": ["distorted", "deformed", "too realistic"],
  "tags": ["collage", "vintage", "scrapbook"],
  "examples": []
}
```

---

## 🚀 安装与使用指引

### 1. 快速开始

```bash
# 进入核心模块目录
cd creative_visual_skill

# 安装所需基础依赖
pip install -r requirements.txt
```

### 2. 交互式向导模式 (极速体验)

```bash
# 建议先在控制台中设置 UTF-8 编码避免 Windows 平台下的 Emoji 字符报错
$env:PYTHONIOENCODING="utf-8"

# 启动交互模式
python main.py --interactive
```

向导支持：
1. 分析输入文章，匹配风格，提交本地/云端生图，**并在生成后启动 10s 超时非阻塞的 "Agent 创作评分系统"（若超时无操作默认用户满意评分 5 分）**。
2. 注入新风格并进行 `(y/n)` 交互确权。
3. 提交图片生成的优化意见并执行配置进化。

---

### 3. 命令行高级参数

```bash
# 分析文章并生成 2.35:1 封面和 16:9 配图 (默认使用 local 模式)
python main.py --article "你的文章长文本内容"

# 强制使用指定的风格模板，指定云端 OpenAI 渠道生成
python main.py --article "你的文章内容" --style "赛博朋克霓虹风" --provider openai

# 启用 V2 LLM 增强提取模式 (需在 .env 文件中预置 API Keys)
python main.py --article "你的文章内容" --use-llm --provider gemini

# 触发自进化调优
python main.py --optimize "画面留白不够，文字和人叠在了一起"
```
