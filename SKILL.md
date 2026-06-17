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
* **`tests/`**: 包含 32 个 pytest 用例的自动化测试套件。

---

## 🚀 调用与执行指令规范

AI 助理可通过终端命令行调度本 Skill：

### 1. 启动交互式向导
```bash
$env:PYTHONIOENCODING="utf-8"
python creative_visual_skill/main.py --interactive
```

### 2. 长文章分析与生图管道
```bash
# 生成 2.35:1 封面与 16:9 内容配图
python creative_visual_skill/main.py --article "长文章内容..."

# 强制指定风格模板与 OpenAI 后端，并启用 V2 大模型增强提取
python creative_visual_skill/main.py --article "长文章内容..." --style "赛博朋克霓虹风" --provider openai --use-llm
```

### 3. 保存新风格 (素材注入)
```bash
python creative_visual_skill/main.py --save-style "保存到视觉库：极简插画风，主体使用[SUBJECT]，采用黑金撞色，现代极简风格。"
```

### 4. 触发自进化
```bash
python creative_visual_skill/main.py --optimize "刚才生成的插画风背景太亮了，对比度需要调低"
```

### 5. 校验单元测试
```bash
python -m pytest creative_visual_skill/tests/ -v
```

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
