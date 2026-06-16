#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Creative Visual Skill — 入口与主控脚本
提供 CLI 命令行交互，编排文章分析、风格选择、JSON 提示词中台和生图/自进化流程。
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# 加载环境变量（如 API Keys）
load_dotenv()

# 确保当前目录在 sys.path 中，以便直接运行
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from utils import (
    ArticleInfo,
    StyleInfo,
    PromptPayload,
    ImageResult,
    run_logger,
)
from config import load_config, get_config_value
from article_analyzer import analyze_article
from style_library import list_styles, select_style
from json_builder import build_payload
from image_runner import run_image_job, run_batch_jobs
from save_style import process_save_request, check_save_trigger
from evolver import trigger_evolution, apply_evolution, get_evolution_history


def print_banner():
    print("=" * 60)
    print("      🎨 Welcome to Creative Visual Skill (CVSkill) 🎨")
    print("=" * 60)


def handle_list_styles():
    """列出当前风格库中所有的风格模板"""
    print("\n--- 现有风格库模板列表 ---")
    styles = list_styles()
    if not styles:
        print("风格库为空！请检查 styles/style_library.md 文件。")
        return

    for idx, s in enumerate(styles, 1):
        tags_str = ", ".join(s.tags)
        colors_str = ", ".join(s.colors)
        print(f"{idx}. 【{s.style_name}】")
        print(f"   - 构图: {s.composition}")
        print(f"   - 配色: [{colors_str}]")
        print(f"   - 标签: [{tags_str}]")
        print("-" * 50)


def handle_save_style(style_text: str, use_llm: bool):
    """保存/注入风格"""
    print("\n--- 触发风格/素材注入流程 ---")
    success = process_save_request(style_text, use_llm=use_llm, interactive=True)
    if success:
        print("🎉 风格素材注入成功！已保存至风格库。")
    else:
        print("💡 风格素材注入已取消或失败。")


def handle_optimize(feedback_text: str, use_llm: bool):
    """触发自进化模块"""
    print("\n--- 触发系统自进化调优 ---")
    # 尝试读取最近一次的 payload（如果有的话，本地可以保存在临时位置，没有就传 None）
    updates = trigger_evolution(feedback_text, recent_payload=None, use_llm=use_llm)
    if updates:
        print("🔧 检测到待更新配置项:")
        for k, v in updates.items():
            if not k.startswith("_"):
                print(f"   - {k}: {v}")
        apply_evolution(updates)
        print("✅ 自进化配置已成功应用并记录。")
    else:
        print("ℹ️ 基于当前反馈，无需或无法自动生成调优项。已记录反馈内容。")


def run_pipeline(
    article_text: str,
    style_name: str = None,
    ratio_type: str = "both",
    provider: str = None,
    use_llm: bool = False,
) -> bool:
    """
    运行完整的自媒体视觉策划 + 生图流程。
    """
    config = load_config()
    target_provider = provider or config.get("default_provider", "local")

    print("\n[Step 1] 分析文章内容...")
    article_info = analyze_article(article_text, use_llm=use_llm, llm_provider=config.get("llm_provider", "openai"))
    print(f"  - 识别主题: {article_info.topic}")
    print(f"  - 情绪基调: {article_info.emotion}")
    print(f"  - 核心关键词: {', '.join(article_info.keywords)}")
    print(f"  - 视觉主体: {article_info.subject}")

    style_info = None
    if style_name:
        print(f"\n[Step 2] 匹配指定风格: 【{style_name}】...")
        styles = list_styles()
        for s in styles:
            if s.style_name.strip() == style_name.strip():
                style_info = s
                break
        if not style_info:
            print(f"⚠️ 未在库中找到指定风格 【{style_name}】，将切换为自动匹配...")

    if not style_info:
        print("\n[Step 2] 自动匹配最佳风格...")
        style_info = select_style(article_info)
        print(f"  - 最佳匹配风格: 【{style_info.style_name}】")

    # 确定生成的比例
    ratios = []
    if ratio_type in ["cover", "both"]:
        ratios.append(config.get("default_cover_ratio", "2.35:1"))
    if ratio_type in ["content", "both"]:
        ratios.append(config.get("default_content_ratio", "16:9"))

    payloads = []
    print("\n[Step 3] 构建 JSON 提示词中台 Payload...")
    for r in ratios:
        payload = build_payload(article_info, style_info, ratio=r)
        payloads.append(payload)
        print(f"  - 已构建 {r} 比例的 Payload")

    print(f"\n[Step 4] 开始执行生图任务 (通道: {target_provider})...")
    # 运行生图任务
    results = run_batch_jobs(payloads, provider=target_provider)

    print("\n[Step 5] 执行结果汇总:")
    all_success = True
    for idx, res in enumerate(results, 1):
        ratio_str = ratios[idx - 1]
        if res.success:
            print(f"  ✨ 任务 {idx} ({ratio_str}): 成功! 图片保存至 -> {res.image_path}")
            run_logger.info(f"Pipeline 生图成功 ({ratio_str}) -> {res.image_path}")
        else:
            all_success = False
            print(f"  ❌ 任务 {idx} ({ratio_str}): 失败! 原因: {res.error_message}")
            run_logger.error(f"Pipeline 生图失败 ({ratio_str}) -> {res.error_message}")

    return all_success


def handle_interactive_mode(use_llm: bool):
    """命令行交互模式"""
    print_banner()
    config = load_config()
    print("已进入交互式向导模式。输入 'exit' 或 'quit' 可退出。")

    while True:
        try:
            print("\n" + "=" * 40)
            print("可用功能列表:")
            print("  1. 文章分析并生成图片 (封面图 + 正文配图)")
            print("  2. 保存新风格到视觉库 (素材注入)")
            print("  3. 输入系统反馈进行自进化优化")
            print("  4. 查看现有风格库列表")
            print("  5. 查看系统自进化历史")
            print("  输入 exit 退出")
            choice = input("请输入功能序号 (1-5/exit): ").strip()

            if choice.lower() in ["exit", "quit"]:
                print("感谢使用，再见！")
                break

            if choice == "1":
                # 文章生成
                article_input = ""
                print("\n请输入文章内容 (输入空行后输入 'EOF' 结束):")
                lines = []
                while True:
                    line = input()
                    if line.strip() == "EOF":
                        break
                    lines.append(line)
                article_input = "\n".join(lines)

                if not article_input.strip():
                    print("❌ 文章内容不能为空。")
                    continue

                provider_choice = input("请选择生图后端 (默认为 local，可选: local/openai/gemini): ").strip()
                if not provider_choice:
                    provider_choice = None

                ratio_choice = input("请选择生成类型 (默认为 both，可选: cover/content/both): ").strip()
                if ratio_choice not in ["cover", "content", "both"]:
                    ratio_choice = "both"

                style_choice = input("指定风格名称 (留空表示自动匹配): ").strip()
                if not style_choice:
                    style_choice = None

                run_pipeline(
                    article_input,
                    style_name=style_choice,
                    ratio_type=ratio_choice,
                    provider=provider_choice,
                    use_llm=use_llm,
                )

            elif choice == "2":
                # 素材注入
                print("\n请输入你想保存的风格素材描述（需包含 '保存到视觉库'、'存入素材' 等触发词，例如：'保存到视觉库：极简黑金风，主体使用[SUBJECT]，搭配黑色磨砂背景。'）：")
                style_input = input().strip()
                if style_input:
                    # 确保输入包含触发词，如果不包含，帮用户补上
                    if not check_save_trigger(style_input):
                        style_input = "保存到视觉库：" + style_input
                    handle_save_style(style_input, use_llm=use_llm)
                else:
                    print("❌ 输入不能为空。")

            elif choice == "3":
                # 自进化
                feedback_input = input("\n请输入你对生图结果的意见/反馈（例如：'刚才生成的拼贴风画面太挤了'）: ").strip()
                if feedback_input:
                    handle_optimize(feedback_input, use_llm=use_llm)
                else:
                    print("❌ 反馈不能为空。")

            elif choice == "4":
                handle_list_styles()

            elif choice == "5":
                history = get_evolution_history()
                print("\n--- 系统自进化调优记录 ---")
                if not history:
                    print("暂无自进化调优记录。")
                else:
                    for item in history:
                        print(f" - [{item.get('timestamp', '未知时间')}] {item.get('detail', '')}")

            else:
                print("❌ 无效的序号，请重新选择。")

        except KeyboardInterrupt:
            print("\n已退出交互模式。")
            break
        except Exception as e:
            print(f"❌ 发生错误: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Creative Visual Skill (CVSkill) - 自媒体视觉策划 + 跨模型生图 Skill 模块"
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--article", type=str, help="直接输入文章内容进行分析生图")
    group.add_argument("--article-file", type=str, help="从文本文件中读取文章内容进行生图")
    group.add_argument("--save-style", type=str, help="素材注入指令，包含触发词以保存新风格")
    group.add_argument("--optimize", type=str, help="传入优化反馈指令以触发自进化模块调优")
    group.add_argument("--list-styles", action="store_true", help="列出风格库中所有的风格模板")
    group.add_argument("--interactive", action="store_true", help="启动交互式向导模式")

    parser.add_argument("--style", type=str, help="指定生图的风格模板名称，不指定则自动匹配")
    parser.add_argument(
        "--type",
        type=str,
        choices=["cover", "content", "both"],
        default="both",
        help="生成类型: cover(封面图 2.35:1) | content(正文图 16:9) | both(两者都生成)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["local", "openai", "gemini"],
        help="生图后端提供商，不指定则使用 config.json 中默认配置",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="开启 LLM 增强模式 (用于文章分析和素材注入结构化解析，需配置环境变量中的 API Keys)",
    )

    args = parser.parse_args()

    # 如果没有任何参数，默认进入 banner 介绍并提示 --help
    if not len(sys.argv) > 1:
        print_banner()
        parser.print_help()
        print("\n💡 建议运行: python main.py --interactive 启动交互模式")
        return

    # 1. 列出风格库
    if args.list_styles:
        handle_list_styles()
        return

    # 2. 素材注入
    if args.save_style:
        handle_save_style(args.save_style, args.use_llm)
        return

    # 3. 自进化
    if args.optimize:
        handle_optimize(args.optimize, args.use_llm)
        return

    # 4. 交互模式
    if args.interactive:
        handle_interactive_mode(args.use_llm)
        return

    # 5. 文章处理 (直接传参或文件读取)
    article_text = ""
    if args.article:
        article_text = args.article
    elif args.article_file:
        if not os.path.exists(args.article_file):
            print(f"❌ 找不到文章文件: {args.article_file}")
            sys.exit(1)
        with open(args.article_file, "r", encoding="utf-8") as f:
            article_text = f.read()

    if article_text:
        success = run_pipeline(
            article_text,
            style_name=args.style,
            ratio_type=args.type,
            provider=args.provider,
            use_llm=args.use_llm,
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
