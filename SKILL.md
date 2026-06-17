---
name: creative-visual-skill
description: 自媒体视觉策划与跨模型生图中台 Skill 模块，为 Agent 赋予文章视觉解析、风格推荐与多后端串行/云端图像生成及自进化调参能力。
---

# Creative Visual Skill (CVSkill) — 指南与指令规范

CVSkill 是一个为 AI Agent 赋予自媒体视觉策划与多后端跨模型图像生成能力的 Skill 扩展模块。AI 助理（如 Antigravity）可通过读取并理解此 `SKILL.md`，获知如何调度与集成 CVSkill 的核心能力。

---

## 🛠️ 能力概述

当用户请求进行“自媒体视觉策划”、“生图”、“公众号封面设计”或“风格库管理”时，本 Skill 模块可提供以下子能力：

1. **文章视觉分析 (Article Analysis)**: 接收长文，智能解析文章的主题分类、情感基调、关键词集以及提取核心视觉主体 `subject`。
2. **风格匹配推荐 (Style Selection)**: 比对文章语义特征与 `styles/style_library.md` 中的标签交集，打分推荐最切合的风格模板。
3. **JSON 语义中台 (PromptPayload)**: 生成全局唯一的真相源 JSON，解耦语义层与渲染层，供不同后端调阅。
4. **多模型适配 (Model Adaptation)**: 针对 ComfyUI 翻译为逗号分隔标签并自动注入 2.35:1 水平宽幅布局与留白提示词；针对 OpenAI/Gemini 转译为自然语言叙事描述。
5. **串行排队生图 (Image Generation)**: 自动分发生图任务。针对 ComfyUI 执行严格的线程锁单队列串行等待逻辑，保证 GPU 安全落盘。
6. **素材交互式注入 (Style Injection)**: 检测爆款注入意图，进行格式解析展示并进行 `(y/n)` 二次确权后追加保存到风格库。
7. **配置自进化 (Self-Evolution)**: 接受负反馈，调参自动覆写 `config.json`，完成系统的闭环自我迭代。
8. **Agent 主动视觉审计 (Agent Audit)**: 生图成功后由 Agent 执行多模态视觉审计（配合大模型）或文本诊断，生成优化报告并提请用户确权更新。

---

## 📂 项目结构规范

本 Skill 路径下包含以下核心资产：
* **`main.py`**: CLI 运行入口、交互向导与审计确权接口。
* **`config.json`**: 模块核心配置文件（包含 `version: "1.0.0"`）。
* **`styles/style_library.md`**: 风格模板库，通过 `## Style` 标题与 ```json 代码块扩展。
* **`workflows/`**: 预置的 `sdxl_basic.json` 和 `flux_basic.json` 本地生图工作流。
* **`tests/`**: 包含 47 个 pytest 用例的自动化测试套件。

---

## 🚀 调用与执行指令规范

AI 助理可通过终端命令行调度本 Skill：

### 1. 启动交互式向导
```bash
$env:PYTHONIOENCODING="utf-8"
python -m creative_visual_skill.main --interactive
```

### 2. 长文章分析与生图管道
```bash
# 生成 2.35:1 封面与 16:9 内容配图
python -m creative_visual_skill.main --article "长文章内容..."

# 强制指定风格模板与 OpenAI 后端，并启用 V2 大模型增强提取
python -m creative_visual_skill.main --article "长文章内容..." --style "赛博朋克霓虹风" --provider openai --use-llm
```

### 3. 保存新风格 (素材注入)
CVSkill 支持通过“文字描述”或“本地参考图片”两种方式智能录入新风格：

#### 3.1 基于文字描述注册
如果描述中包含可变主体，推荐使用 `[SUBJECT]` 占位符；若没有，AI 将智能推断核心主体并引导您交互式自愈注入。
```bash
# 标准录入方式（必须包含“保存到视觉库”、“存入素材”等触发词）
python -m creative_visual_skill.main --save-style "保存到视觉库：极简插画风，主体使用[SUBJECT]，采用黑金撞色，现代极简风格。"

# 智能自愈录入（若描述中缺少 [SUBJECT]，启动二次确权进行 AI 识别与自动注入）
python -m creative_visual_skill.main --save-style "保存到视觉库：极简插画风，一个精致的蜡烛放在黑色大理石桌面上" --use-llm
```

#### 3.2 基于本地参考图片直注（视觉多模态反向工程）
直接传入本地 PNG/JPG 图像路径，系统将自动调用 Vision LLM 逆向推导生图参数，并把该图片保存到内容库作为样例。
```bash
# 传入图片文件路径，必须启用 --use-llm 以唤醒多模态解析能力
python -m creative_visual_skill.main --save-style "styles/image/vintage_sample.png" --use-llm
```


### 4. 触发自进化
```bash
python -m creative_visual_skill.main --optimize "刚才生成的插画风背景太亮了，对比度需要调低"
```

### 5. 校验单元测试
```bash
python -m pytest creative_visual_skill/tests/ -v
```

## 🤖 Agent 视觉诊断与自进化 SOP 规范

为了规范多智能体协作或未来接入的 AI 助理使用 CVSkill 时的调优行为，建立以下生图诊断与自进化标准作业程序（SOP）：

### 1. 自动审计阶段 (仅在启用 `--use-llm` 且有可用图片时触发)
*   生图成功后，助理 Agent **必须**提取图片绝对路径，并调用 `evaluate_generation()`：
    *   **多模态视觉诊断**：向具备 Vision 能力的模型传入原始 Prompt、Payload 以及图片，审计生成质量。
    *   **Skill 诊断**：画面太拥挤、少留白等可调参配置问题，模型将在 `proposed_changes` 中建议调整值。
    *   **Model 诊断**：如人脸肢体严重畸形、文字拼写错误等模型硬伤，归类为 `model` 问题，在 `explanation` 中给出换底层模型（如 OpenAI DALL-E 3 或 Flux）的诊断建议，不建议调参。

### 2. 交互式反馈与自进化确权
*   如果自动审计认为无异常，或者在离线运行模式下，助理 Agent 应提示用户评价。如果收集到反馈（如用户表示“太空旷了”）：
    *   Agent 调用 `evaluate_generation(feedback=user_feedback)`，通过文本规则或 LLM 提取 `proposed_changes` 意见。
    *   Agent **绝不允许**在没有用户许可的情况下擅自覆写配置文件。必须在终端中呈现参数变化对比，并阻塞式提请用户输入进行确权：
        ```text
        是否同意 Agent 自动修改配置文件并应用？(y/n):
        ```
    *   如果用户确权输入 `y`/`yes`，执行配置覆写更新，同时向“智能记忆库”追加记录该次生图教训。

### 3. 智能防错记忆库机制 (Memory Storage)
*   **记录生成**：用户确权同意修改参数后，系统自动在 `creative_visual_skill/memory/history/` 目录下写入该次生图教训的 JSON 归档文件（包含时间戳、风格、主体、使用的提示词、调整前后参数值），并将被投诉的坏图拷贝入 `creative_visual_skill/memory/bad_cases/` 作为反面教材留存。
*   **前置预防（治未病）**：当后续再次启动生图管道匹配到相同风格时，JSON 中台构建器会在生图前自动匹配该风格的记忆库历史，一旦发现曾发生过投诉，**直接将历史调优参数作为覆盖项临时应用到本次 Payload 的 `overrides` 中**，并在控制台提醒用户已自动应用防错记忆，从而实现自动规避重复错误。

---

## 📐 尺寸映射与微信封面排版规范

为了生成高质量的自媒体配图，系统预置了以下宽高比（Ratio）与微信排版布局映射规则。Agent 调度生图时，应将对应比率参数传给生图管道，以使 Model Adapter 自动注入针对性排版提示词：

| 画面宽高比 (Ratio) | 目标像素尺寸 (px) | 触发布局适配逻辑 (Model Adapter) | 微信自媒体典型应用场景 |
|---|---|---|---|
| **`2.35:1`** (默认封面) | 1024 × 440 | 自动追加水平宽幅构图词，并强制在画面**右侧保留大片干净留白**以放置文章标题，核心视觉主体约束在左侧 1/3。 | 微信公众号首条大图封面 / Widescreen Banner |
| **`16:9`** (默认正文) | 1344 × 768 | 适配宽视角电影画幅，采用平衡对称构图，保留画面故事完整度。 | 公众号次条封面 / 正文插图 / 网页首图 |
| **`1:1`** | 1024 × 1024 | 居中构图，对称平衡布局。 | 朋友圈分享配图 / 社交头像 |
| **`3:2`** | 1216 × 832 | 经典单反相机摄影画幅比例。 | 测评配图 / 实拍图仿写 |
| **`21:9`** | 1536 × 640 | 宽视场广角电影画幅，大片级质感。 | 电影感宽画幅正文插图 |

---

## 📊 数据协议标准

### 1. 中台 Payload 规范 (`PromptPayload`)
```json
{
  "subject": "视觉主体",
  "style": "风格模板名称",
  "composition": "构图叙事描述 (已替换 [SUBJECT])",
  "colors": ["配色1", "配色2"],
  "background": "背景材质/氛围",
  "ratio": "2.35:1",
  "negative": ["反向词"],
  "tags": ["标签1", "标签2"],
  "examples": []
}
```
