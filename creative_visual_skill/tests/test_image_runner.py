"""
test_image_runner.py — image_runner 模块的单元测试与 API 尺寸映射校验
"""

import os
import sys
from unittest.mock import patch, MagicMock
import pytest

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import PromptPayload
from image_runner import run_image_job


@patch("openai.OpenAI")
def test_openai_size_mapping_dalle3(mock_openai_class):
    """验证使用 DALL-E 3 时，尺寸会被自动纠偏映射为 DALL-E 3 官方限制的尺寸"""
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_response = MagicMock()
    mock_data = MagicMock()
    mock_data.b64_json = "bW9ja19iYXNlNjRfZGF0YQ=="  # valid base64 for "mock_base64_data"
    mock_response.data = [mock_data]
    mock_client.images.generate.return_value = mock_response

    # 1. 验证 1:1 比例自动映射为 1024x1024
    payload_square = PromptPayload(ratio="1:1", subject="a small kitten")
    with patch("image_runner.load_config") as mock_load_config:
        mock_load_config.return_value = {"openai_model": "dall-e-3"}
        run_image_job(payload_square, provider="openai")
        
        _, kwargs = mock_client.images.generate.call_args
        assert kwargs["size"] == "1024x1024"
        assert kwargs["model"] == "dall-e-3"

    # 2. 验证 16:9 比例自动映射为 1792x1024
    payload_widescreen = PromptPayload(ratio="16:9", subject="a sunset landscape")
    with patch("image_runner.load_config") as mock_load_config:
        mock_load_config.return_value = {"openai_model": "dall-e-3"}
        run_image_job(payload_widescreen, provider="openai")
        
        _, kwargs = mock_client.images.generate.call_args
        assert kwargs["size"] == "1792x1024"

    # 3. 验证 9:16 竖屏自动映射为 1024x1792
    payload_portrait = PromptPayload(ratio="9:16", subject="a portrait of a woman")
    with patch("image_runner.load_config") as mock_load_config:
        mock_load_config.return_value = {"openai_model": "dall-e-3"}
        run_image_job(payload_portrait, provider="openai")
        
        _, kwargs = mock_client.images.generate.call_args
        assert kwargs["size"] == "1024x1792"

    # 4. 验证其它非 DALL-E 3 模型仍旧使用配置文件中的默认尺寸
    payload_other = PromptPayload(ratio="2.35:1", subject="cinematic frame")
    with patch("image_runner.load_config") as mock_load_config:
        mock_load_config.return_value = {
            "openai_model": "dall-e-2",
            "openai_size_cover": "1536x1024"
        }
        run_image_job(payload_other, provider="openai")
        
        _, kwargs = mock_client.images.generate.call_args
        assert kwargs["size"] == "1536x1024"
        assert kwargs["model"] == "dall-e-2"
