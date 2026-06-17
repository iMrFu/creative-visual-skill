"""
Creative Visual Skill — Module E: 生图执行器
负责将 PromptPayload 交给不同后端（本地 ComfyUI / OpenAI / Gemini）生成图片，
返回统一的 ImageResult。
"""

import os
import json
import time
import uuid
import random
import base64
import threading
import urllib.request
import urllib.parse
import urllib.error
from typing import List

from .utils import (
    PromptPayload,
    ImageResult,
    OUTPUT_DIR,
    WORKFLOWS_DIR,
    run_logger,
    read_json_file,
    generate_timestamped_filename,
)
from .config import load_config

# ---------------------------------------------------------------------------
# 串行队列锁 —— 本地 ComfyUI 同一时间只跑一个任务
# ---------------------------------------------------------------------------
_local_lock = threading.Lock()


# ===========================================================================
# 主入口
# ===========================================================================

def run_image_job(payload: PromptPayload, provider: str = "local") -> ImageResult:
    """
    根据 provider 分发到对应后端执行生图。

    Args:
        payload:  PromptPayload 结构
        provider: 'local' | 'openai' | 'gemini'

    Returns:
        ImageResult
    """
    provider = provider.lower().strip()
    run_logger.info(f"run_image_job 启动 | provider={provider} | subject={payload.subject[:60]}")

    dispatch = {
        "local": _run_local,
        "openai": _run_openai,
        "gemini": _run_gemini,
    }

    handler = dispatch.get(provider)
    if handler is None:
        msg = f"不支持的 provider: {provider}（可选: local / openai / gemini）"
        run_logger.error(msg)
        return ImageResult(success=False, error_message=msg)

    try:
        return handler(payload)
    except Exception as exc:
        run_logger.exception(f"run_image_job 异常 | provider={provider}")
        return ImageResult(success=False, error_message=str(exc))


# ===========================================================================
# 本地 ComfyUI
# ===========================================================================

def _run_local(payload: PromptPayload) -> ImageResult:
    """
    通过 ComfyUI HTTP API 执行本地生图。
    严格串行：同一时间只允许一个任务在跑。
    """
    from .model_adapter import build_prompt

    config = load_config()
    # Apply dynamic memory overrides if present in payload
    if hasattr(payload, "overrides") and payload.overrides:
        config.update(payload.overrides)
        run_logger.info(f"应用记忆库动态覆盖参数: {payload.overrides}")

    positive, negative = build_prompt(payload, "local")


    # ---- 加载工作流模板 ----
    workflow_name = config.get("comfyui_workflow", "sdxl_basic")
    workflow_path = os.path.join(WORKFLOWS_DIR, f"{workflow_name}.json")
    workflow = read_json_file(workflow_path)
    if not workflow:
        return ImageResult(
            success=False,
            error_message=f"工作流文件不存在或为空: {workflow_path}",
        )

    # ---- 替换提示词占位符 ----
    workflow_str = json.dumps(workflow, ensure_ascii=False)
    workflow_str = workflow_str.replace("POSITIVE_PROMPT_PLACEHOLDER", _escape_json_str(positive))
    workflow_str = workflow_str.replace("NEGATIVE_PROMPT_PLACEHOLDER", _escape_json_str(negative))
    workflow = json.loads(workflow_str)

    # ---- 设置尺寸（根据 ratio） ----
    ratio_dims = config.get("ratio_dimensions", {})
    dims = ratio_dims.get(payload.ratio, {"width": 1024, "height": 1024})
    _set_latent_dimensions(workflow, dims["width"], dims["height"])

    # ---- 覆盖采样参数（如果配置中有自定义值）----
    _override_sampler_params(workflow, config)

    # ---- 覆盖 checkpoint（如果配置中指定了）----
    _override_checkpoint(workflow, config)

    # ---- 设置随机种子 ----
    seed = random.randint(0, 2**63 - 1)
    _set_seed(workflow, seed)

    # ---- 串行执行 ----
    server = config.get("comfyui_server", "http://127.0.0.1:8188")
    timeout = config.get("comfyui_timeout", 300)
    poll_interval = config.get("comfyui_poll_interval", 2)

    with _local_lock:
        run_logger.info(f"ComfyUI 任务提交 | server={server} | seed={seed}")

        # 提交 prompt
        client_id = str(uuid.uuid4())
        prompt_id = _comfyui_queue_prompt(server, workflow, client_id)
        if prompt_id is None:
            return ImageResult(
                success=False,
                prompt_used=positive,
                error_message="ComfyUI 提交 prompt 失败",
            )

        # 轮询等待完成
        history = _comfyui_poll_history(server, prompt_id, timeout, poll_interval)
        if history is None:
            return ImageResult(
                success=False,
                prompt_used=positive,
                error_message=f"ComfyUI 任务超时（{timeout}s）或轮询失败",
            )

        # 从 history 中提取输出图片信息
        image_info = _extract_image_info(history)
        if image_info is None:
            return ImageResult(
                success=False,
                prompt_used=positive,
                error_message="ComfyUI 返回结果中未找到输出图片",
            )

        # 下载图片
        filename, subfolder, img_type = image_info
        image_data = _comfyui_download_image(server, filename, subfolder, img_type)
        if image_data is None:
            return ImageResult(
                success=False,
                prompt_used=positive,
                error_message=f"ComfyUI 图片下载失败: {filename}",
            )

        # 保存到 output/
        out_filename = generate_timestamped_filename(prefix="local", ext=".png")
        out_path = os.path.join(OUTPUT_DIR, out_filename)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(image_data)

        run_logger.info(f"ComfyUI 生图成功 | 输出: {out_path}")
        return ImageResult(
            success=True,
            image_path=out_path,
            prompt_used=positive,
            metadata={
                "provider": "local",
                "workflow": workflow_name,
                "seed": seed,
                "negative": negative,
                "prompt_id": prompt_id,
            },
        )


# ===========================================================================
# OpenAI (gpt-image-1 / dall-e-3)
# ===========================================================================

def _run_openai(payload: PromptPayload) -> ImageResult:
    """
    通过 OpenAI images.generate API 生图。
    支持指数退避重试（主要处理 429 限流）。
    """
    from .model_adapter import build_prompt

    try:
        import openai
    except ImportError:
        return ImageResult(success=False, error_message="openai SDK 未安装，请 pip install openai")

    config = load_config()
    # Apply dynamic memory overrides if present in payload
    if hasattr(payload, "overrides") and payload.overrides:
        config.update(payload.overrides)
        run_logger.info(f"应用记忆库动态覆盖参数: {payload.overrides}")

    prompt_text = build_prompt(payload, "openai")


    model = config.get("openai_model", "gpt-image-1")

    # 根据 ratio 选择 size 并兼容 DALL-E 3 官方标准尺寸
    if "dall-e-3" in model.lower() or "image" in model.lower():
        # DALL-E 3 只接受 1024x1024, 1792x1024, 1024x1792
        if payload.ratio == "1:1":
            size = "1024x1024"
        elif payload.ratio in ("9:16", "2:3"):
            size = "1024x1792"
        else:
            size = "1792x1024"
    else:
        if "cover" in payload.ratio or payload.ratio in ("2.35:1", "21:9"):
            size = config.get("openai_size_cover", "1536x1024")
        else:
            size = config.get("openai_size_content", "1536x1024")

    quality = config.get("openai_quality", "high")

    # 指数退避重试
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = openai.OpenAI(base_url=config.get("openai_base_url", "") or None)
            run_logger.info(f"OpenAI 生图请求 | model={model} | size={size} | attempt={attempt+1}")

            response = client.images.generate(
                model=model,
                prompt=prompt_text,
                size=size,
                quality=quality,
                n=1,
            )

            # 尝试获取 base64 数据
            image_data_b64 = None
            if hasattr(response.data[0], "b64_json") and response.data[0].b64_json:
                image_data_b64 = response.data[0].b64_json
            elif hasattr(response.data[0], "url") and response.data[0].url:
                # 从 URL 下载图片
                req = urllib.request.Request(response.data[0].url)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    image_bytes = resp.read()
                out_filename = generate_timestamped_filename(prefix="openai", ext=".png")
                out_path = os.path.join(OUTPUT_DIR, out_filename)
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                with open(out_path, "wb") as f:
                    f.write(image_bytes)

                run_logger.info(f"OpenAI 生图成功（URL 模式）| 输出: {out_path}")
                return ImageResult(
                    success=True,
                    image_path=out_path,
                    prompt_used=prompt_text,
                    metadata={"provider": "openai", "model": model, "size": size},
                )

            if image_data_b64:
                image_bytes = base64.b64decode(image_data_b64)
                out_filename = generate_timestamped_filename(prefix="openai", ext=".png")
                out_path = os.path.join(OUTPUT_DIR, out_filename)
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                with open(out_path, "wb") as f:
                    f.write(image_bytes)

                run_logger.info(f"OpenAI 生图成功（base64 模式）| 输出: {out_path}")
                return ImageResult(
                    success=True,
                    image_path=out_path,
                    prompt_used=prompt_text,
                    metadata={"provider": "openai", "model": model, "size": size},
                )

            return ImageResult(
                success=False,
                prompt_used=prompt_text,
                error_message="OpenAI 返回数据中无图片（无 b64_json 也无 url）",
            )

        except Exception as exc:
            error_str = str(exc)
            # 429 限流 → 指数退避重试
            is_rate_limit = "429" in error_str or "rate" in error_str.lower()
            if is_rate_limit and attempt < max_retries - 1:
                wait = (2 ** attempt) * 2  # 2s, 4s, 8s
                run_logger.warning(f"OpenAI 429 限流，{wait}s 后重试 (attempt {attempt+1})")
                time.sleep(wait)
                continue
            else:
                run_logger.error(f"OpenAI 生图失败: {error_str}")
                return ImageResult(
                    success=False,
                    prompt_used=prompt_text,
                    error_message=f"OpenAI API 错误: {error_str}",
                )

    # 理论上不会走到这里
    return ImageResult(success=False, prompt_used=prompt_text, error_message="OpenAI 重试次数耗尽")


# ===========================================================================
# Gemini (Imagen / gemini-2.0-flash-preview-image-generation)
# ===========================================================================

def _run_gemini(payload: PromptPayload) -> ImageResult:
    """
    通过 Google GenAI SDK 生图。
    """
    from .model_adapter import build_prompt

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return ImageResult(
            success=False,
            error_message="google-genai SDK 未安装，请 pip install google-genai",
        )

    config = load_config()
    # Apply dynamic memory overrides if present in payload
    if hasattr(payload, "overrides") and payload.overrides:
        config.update(payload.overrides)
        run_logger.info(f"应用记忆库动态覆盖参数: {payload.overrides}")

    prompt_text = build_prompt(payload, "gemini")


    model = config.get("gemini_model", "gemini-2.0-flash-preview-image-generation")

    # 指数退避重试
    max_retries = 3
    for attempt in range(max_retries):
        try:
            client = genai.Client()
            run_logger.info(f"Gemini 生图请求 | model={model} | attempt={attempt+1}")

            response = client.models.generate_content(
                model=model,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )

            # 从 response.candidates 中提取图片
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                        # 根据 MIME 类型决定扩展名
                        mime = part.inline_data.mime_type
                        ext = ".png" if "png" in mime else ".jpg"
                        image_bytes = part.inline_data.data

                        out_filename = generate_timestamped_filename(prefix="gemini", ext=ext)
                        out_path = os.path.join(OUTPUT_DIR, out_filename)
                        os.makedirs(OUTPUT_DIR, exist_ok=True)
                        with open(out_path, "wb") as f:
                            f.write(image_bytes)

                        run_logger.info(f"Gemini 生图成功 | 输出: {out_path}")
                        return ImageResult(
                            success=True,
                            image_path=out_path,
                            prompt_used=prompt_text,
                            metadata={"provider": "gemini", "model": model},
                        )

            # 如果没有返回候选内容，并且是最后一次尝试，则报错返回
            if attempt == max_retries - 1:
                return ImageResult(
                    success=False,
                    prompt_used=prompt_text,
                    error_message="Gemini 返回结果中未找到图片数据",
                )

        except Exception as exc:
            error_str = str(exc)
            is_rate_limit = "429" in error_str or "rate" in error_str.lower()
            if is_rate_limit and attempt < max_retries - 1:
                wait = (2 ** attempt) * 2  # 2s, 4s, 8s
                run_logger.warning(f"Gemini 429 限流，{wait}s 后重试 (attempt {attempt+1})")
                time.sleep(wait)
                continue
            else:
                run_logger.error(f"Gemini 生图失败: {error_str}")
                return ImageResult(
                    success=False,
                    prompt_used=prompt_text,
                    error_message=f"Gemini API 错误: {error_str}",
                )

    # 理论上不会走到这里
    return ImageResult(success=False, prompt_used=prompt_text, error_message="Gemini 重试次数耗尽")


# ===========================================================================
# 批量执行
# ===========================================================================

def run_batch_jobs(
    payloads: List[PromptPayload],
    provider: str = "local",
) -> List[ImageResult]:
    """
    批量执行生图任务。

    - local: 严格串行（ComfyUI 单队列）
    - openai / gemini: 也串行执行（避免触发限流），
      如需并发可在外部自行实现线程池。

    Args:
        payloads: PromptPayload 列表
        provider: 后端类型

    Returns:
        ImageResult 列表，与 payloads 一一对应
    """
    results: List[ImageResult] = []
    total = len(payloads)

    for idx, payload in enumerate(payloads, 1):
        run_logger.info(f"批量任务 [{idx}/{total}] 开始 | provider={provider}")
        result = run_image_job(payload, provider=provider)
        results.append(result)

        if result.success:
            run_logger.info(f"批量任务 [{idx}/{total}] 成功 | {result.image_path}")
        else:
            run_logger.warning(f"批量任务 [{idx}/{total}] 失败 | {result.error_message}")

    return results


# ===========================================================================
# ComfyUI HTTP 工具函数
# ===========================================================================

def _comfyui_queue_prompt(server: str, workflow: dict, client_id: str) -> str | None:
    """
    向 ComfyUI 提交 prompt，返回 prompt_id。
    失败返回 None。
    """
    url = f"{server}/prompt"
    payload_data = json.dumps(
        {"client_id": client_id, "prompt": workflow},
        ensure_ascii=False,
    ).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            prompt_id = result.get("prompt_id")
            run_logger.info(f"ComfyUI prompt 已提交 | prompt_id={prompt_id}")
            return prompt_id
    except Exception as exc:
        run_logger.error(f"ComfyUI 提交 prompt 失败: {exc}")
        return None


def _comfyui_poll_history(
    server: str,
    prompt_id: str,
    timeout: int,
    poll_interval: int,
) -> dict | None:
    """
    轮询 ComfyUI /history/{prompt_id}，直到任务完成或超时。
    成功返回 history dict，超时返回 None。
    """
    url = f"{server}/history/{prompt_id}"
    start = time.time()

    while time.time() - start < timeout:
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                history = json.loads(resp.read().decode("utf-8"))
                if prompt_id in history:
                    run_logger.info(f"ComfyUI 任务完成 | 耗时 {time.time()-start:.1f}s")
                    return history[prompt_id]
        except Exception:
            pass  # 连接可能暂时不可用，继续轮询

        time.sleep(poll_interval)

    run_logger.error(f"ComfyUI 任务超时 | prompt_id={prompt_id} | timeout={timeout}s")
    return None


def _comfyui_download_image(
    server: str,
    filename: str,
    subfolder: str,
    img_type: str,
) -> bytes | None:
    """
    从 ComfyUI /view 接口下载图片，返回二进制数据。
    """
    params = urllib.parse.urlencode({
        "filename": filename,
        "subfolder": subfolder,
        "type": img_type,
    })
    url = f"{server}/view?{params}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except Exception as exc:
        run_logger.error(f"ComfyUI 图片下载失败: {exc}")
        return None


def _extract_image_info(history: dict) -> tuple | None:
    """
    从 ComfyUI history 结果中提取第一张输出图片的 (filename, subfolder, type)。
    """
    outputs = history.get("outputs", {})
    for node_id, node_output in outputs.items():
        images = node_output.get("images", [])
        if images:
            img = images[0]
            return (
                img.get("filename", ""),
                img.get("subfolder", ""),
                img.get("type", "output"),
            )
    return None


# ===========================================================================
# 工作流修改工具函数
# ===========================================================================

def _escape_json_str(text: str) -> str:
    """
    转义字符串中可能破坏 JSON 的特殊字符。
    json.dumps 会自动转义，这里取其内部字符串（去掉首尾引号）。
    """
    return json.dumps(text, ensure_ascii=False)[1:-1]


def _set_latent_dimensions(workflow: dict, width: int, height: int) -> None:
    """在工作流中找到 EmptyLatentImage 节点并设置尺寸。"""
    for node_id, node in workflow.items():
        if node.get("class_type") == "EmptyLatentImage":
            node["inputs"]["width"] = width
            node["inputs"]["height"] = height
            run_logger.debug(f"EmptyLatentImage 尺寸设置 → {width}x{height}")
            break


def _set_seed(workflow: dict, seed: int) -> None:
    """在工作流中找到 KSampler 节点并设置随机种子。"""
    for node_id, node in workflow.items():
        if node.get("class_type") == "KSampler":
            node["inputs"]["seed"] = seed
            break


def _override_sampler_params(workflow: dict, config: dict) -> None:
    """根据配置覆盖 KSampler 的步数、CFG、采样器、调度器。"""
    for node_id, node in workflow.items():
        if node.get("class_type") == "KSampler":
            inputs = node["inputs"]
            if config.get("comfyui_steps"):
                inputs["steps"] = config["comfyui_steps"]
            if config.get("comfyui_cfg"):
                inputs["cfg"] = config["comfyui_cfg"]
            if config.get("comfyui_sampler"):
                inputs["sampler_name"] = config["comfyui_sampler"]
            if config.get("comfyui_scheduler"):
                inputs["scheduler"] = config["comfyui_scheduler"]
            break


def _override_checkpoint(workflow: dict, config: dict) -> None:
    """如果配置中指定了 checkpoint，则覆盖 CheckpointLoaderSimple 节点。"""
    ckpt = config.get("comfyui_checkpoint", "")
    if not ckpt:
        return  # 留空表示使用工作流默认值

    for node_id, node in workflow.items():
        if node.get("class_type") == "CheckpointLoaderSimple":
            node["inputs"]["ckpt_name"] = ckpt
            run_logger.debug(f"Checkpoint 覆盖 → {ckpt}")
            break
