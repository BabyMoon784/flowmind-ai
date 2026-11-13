
import copy

import pytest

from prompt_builder import build_system_prompt


def test_default_agent_prompt():
    prompt = build_system_prompt()

    assert "My Agent" in prompt
    assert "专业、严谨、理性" in prompt
    assert "回复结构清晰" in prompt


def test_custom_name_and_description():
    prompt = build_system_prompt({
        "name": "CodeMate",
        "description": "专业编程助手",
        "personality": "professional",
        "response_style": "detailed",
    })

    assert "CodeMate" in prompt
    assert "专业编程助手" in prompt
    assert "详细的解释" in prompt


def test_different_personalities():
    professional = build_system_prompt({
        "name": "Agent",
        "personality": "professional",
    })

    creative = build_system_prompt({
        "name": "Agent",
        "personality": "creative",
    })

    assert professional != creative
    assert "专业、严谨" in professional
    assert "创造力" in creative


def test_different_response_styles():
    concise = build_system_prompt({
        "name": "Agent",
        "response_style": "concise",
    })

    detailed = build_system_prompt({
        "name": "Agent",
        "response_style": "detailed",
    })

    assert "回复简洁" in concise
    assert "详细的解释" in detailed


def test_custom_instructions():
    prompt = build_system_prompt({
        "name": "CodeMate",
        "custom_instructions": (
            "优先使用中文解释 Python 和 C++。"
        ),
    })

    assert "用户自定义指令" in prompt
    assert "Python 和 C++" in prompt


def test_long_term_memory():
    prompt = build_system_prompt(
        {"name": "Friday"},
        long_term_memory="用户正在学习 FastAPI。",
    )

    assert "# 长期记忆" in prompt
    assert "用户正在学习 FastAPI" in prompt
    assert "背景资料" in prompt


def test_empty_memory():
    prompt = build_system_prompt(
        {"name": "Friday"},
        long_term_memory="",
    )

    assert "# 长期记忆" not in prompt


def test_invalid_personality():
    with pytest.raises(ValueError):
        build_system_prompt({
            "name": "Agent",
            "personality": "unknown",
        })


def test_invalid_response_style():
    with pytest.raises(ValueError):
        build_system_prompt({
            "name": "Agent",
            "response_style": "unknown",
        })


def test_does_not_modify_config():
    config = {
        "name": "Nova",
        "personality": "efficient",
        "response_style": "concise",
        "enabled_tools": ["list_tasks"],
    }

    original = copy.deepcopy(config)

    build_system_prompt(config)

    assert config == original
