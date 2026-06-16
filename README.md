# Creative Visual Skill (CVSkill) — 自媒体视觉策划与跨模型生图中台

一个平台无关的、模块化设计的**“自媒体视觉策划 + 跨模型生图”**能力模块。它定义了清晰的模块边界与数据结构协议，可以轻松嵌入到本地脚本、Claude Skills、OpenAI Assistants、n8n 或自建 Agent 框架中。

---

## 🚀 核心设计理念

1. **统一中台语义 (PromptPayload)**：所有底层生图模型均以同一个 JSON Payload 作为“唯一真相源”。
2. **多端自适应适配器**：针对本地 ComfyUI（输出逗号分隔的英文 tag 串，并进行横版/留白等布局转换）及云端模型（OpenAI/Gemini，输出自然语言故事感长文本）进行精准转译。
3. **安全素材注入**：配备了防冲突触发词矩阵及交互式二次确认流程，防范对风格库文件的误写。
4. **系统自进化 (Evolver)**：根据模型报错及用户反馈（如“画面太挤”、“图片模糊”）自动调整全局配置（如采样步数、留白权重），并记录进化日志。
5. **本地串行队列**：对本地 ComfyUI 实现基于多线程锁的严格串行生图控制，避免 GPU 显存溢出 (OOM)。

---

## 📂 项目结构

```bash
.
├── .gitignore                  # Git 忽略配置文件
├── README.md                   # 仓库主说明文档
│
└── creative_visual_skill/      # CVSkill 能力模块根目录
    ├── main.py                 # CLI 主入口与交互向导
    ├── config.py               # 全局配置加载与写入模块
    ├── config.json             # 可动态重写的运行时配置文件
    ├── utils.py                # 核心数据类与辅助工具
    ├── article_analyzer.py     # 模块A：文章分析器 (V1规则分词 + V2大模型分析)
    ├── style_library.py        # 模块B：风格库管理器 (Markdown 解析与标签得分匹配)
    ├── json_builder.py         # 模块C：中台 Payload 构建器
    ├── model_adapter.py        # 模块D：跨提供商提示词适配转译器
    ├── image_runner.py         # 模块E：生图执行器 (ComfyUI 串行 / OpenAI / Gemini)
    ├── save_style.py           # 模块F：素材注入与二次确权流程
    ├── evolver.py              # 模块G：规则/LLM自进化优化模块
    ├── requirements.txt        # 项目依赖
    │
    ├── styles/                 # 风格素材库
    │   ├── style_library.md    # 风格库模板定义 (预置 6 大主流风格)
    │   └── image/              # 用户图片素材目录
    │
    ├── workflows/              # ComfyUI API 工作流模板
    │   ├── sdxl_basic.json     # SDXL 基础工作流 API
    │   └── flux_basic.json     # Flux 基础工作流 API
    │
    ├── logs/                   # 日志目录
    │   ├── run.log             # 运行日志
    │   └── evolution.log       # 自进化日志
    │
    ├── output/                 # 最终生成的图片输出目录
    │
    └── tests/                  # 完备单元测试套件
```

---

## 🛠️ 安装与环境配置

### 1. 安装依赖项

推荐使用 Python 3.10+。在项目根目录下安装基础依赖：

```bash
cd creative_visual_skill
pip install -r requirements.txt
```

如果需要使用 **V2 LLM 增强模式**，需要确保配置了相应的 API 客户端（安装 `openai` 及 `google-genai`）。

### 2. 配置环境变量

在 `creative_visual_skill` 目录下创建 `.env` 文件，用于存放云端 API 密钥（如果不需要云端功能，可忽略）：

```env
OPENAI_API_KEY=your-openai-api-key
GEMINI_API_KEY=your-gemini-api-key
```

### 3. 配置本地 ComfyUI

如果使用本地生图（默认模式）：
1. 确保本地运行了 ComfyUI，且 API 端口为 `http://127.0.0.1:8188`（可在 `config.json` 中修改 `comfyui_server`）。
2. 在 ComfyUI 的环境内放有 SDXL Checkpoint（默认 `sd_xl_base_1.0.safetensors`）或 Flux Dev Checkpoint。

---

## 🎮 使用方法

*注意：以下命令均在 `creative_visual_skill` 目录下执行。*

```bash
cd creative_visual_skill
```

### 1. 交互式向导模式 (推荐)

启动极简的控制台交互面板，支持一键运行所有功能：

```bash
python main.py --interactive
```

你可以按照终端向导，输入文章或直接粘贴风格素材进行体验。

---

### 2. 命令行单项操作

#### 📖 文章视觉策划并生成图片 (封面图 + 正文配图)

```bash
# 默认使用本地 ComfyUI，生成 2.35:1 (封面) 和 16:9 (正文) 两个比例的图片
python main.py --article "在家庭教育中，陪伴是最长情的告白。亲子陪伴能够温暖孩子的内心..."

# 指定云端 OpenAI 生图，且只生成公众号封面 (2.35:1)
python main.py --article "人工智能技术正在深刻改变我们的生活..." --provider openai --type cover

# 从本地 TXT 文件读取文章并生图，同时指定强制使用特定风格
python main.py --article-file my_article.txt --style "赛博朋克霓虹风"

# 启用 V2 LLM 增强模式（使用大模型做文章分析与主体提取）
python main.py --article "文章内容" --use-llm --provider gemini
```

#### 💾 风格素材注入 (保存到视觉库)

用户可通过输入包含触发词的文字，将网络爆款提示词或新风格存入系统：

```bash
python main.py --save-style "保存到视觉库：极简黑金插画风，主体使用[SUBJECT]，采用黑金撞色，现代极简风格。"
```
*系统会解析出该风格定义并在终端进行二次确认（y/n），通过后追加写入风格库中。*

#### 🔧 系统自进化优化 (Feedback Loop)

当生成的图片不符合预期时，可以通过优化命令直接对配置进行调整：

```bash
# 规则调优：会自动增加 whitespace_weight 留白权重，降低 max_elements_per_image 数量
python main.py --optimize "刚才生成的拼贴风画面太挤了，字都叠在一起了"

# 大模型调优：启动高级 Agent 诊断并精细更新 config.json 与 evolution.log 记录
python main.py --optimize "图片噪点太多，而且画得太单调了" --use-llm
```

#### 📋 查看风格库列表

```bash
python main.py --list-styles
```

---

## 🧪 自动化测试验证

在 `creative_visual_skill` 目录下，执行以下命令进行完整性验证：

```bash
python -m pytest tests/ -v
```

---

## 📦 核心接口数据标准

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

### PromptPayload (JSON 提示词中台)
```json
{
  "subject": "亲子陪伴",
  "style": "复古剪贴簿拼贴风",
  "composition": "multi-layer collage, stickers, edges with whitespace",
  "colors": ["warm yellow", "dark brown"],
  "background": "vintage paper texture",
  "ratio": "2.35:1",
  "negative": ["distorted", "deformed", "too realistic"],
  "tags": ["collage", "vintage", "scrapbook"],
  "examples": []
}
```
