from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
_env = Environment(loader=FileSystemLoader(str(_prompts_dir)))


def load_prompt(name: str, **vars) -> str:
    """从 prompts/ 目录加载 Jinja2 模板并渲染

    Args:
        name: 模板文件名（如 'script_dialogue.j2'）
        **vars: 模板变量

    Returns:
        渲染后的 prompt 字符串
    """
    template = _env.get_template(name)
    return template.render(**vars)
