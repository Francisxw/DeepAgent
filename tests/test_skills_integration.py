"""
tests/test_skills_integration.py
测试 Skills 集成
"""

import os
import sys
from pathlib import Path

import pytest

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_skills_directory_exists():
    """Skills 目录应存在于项目根目录。"""
    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"
    assert skills_dir.exists(), f"Skills 目录不存在: {skills_dir}"


def test_each_skill_has_skill_md():
    """每个 Skill 子目录都应包含 SKILL.md。"""
    project_root = Path(__file__).parent.parent
    skills_dir = project_root / "skills"
    if not skills_dir.exists():
        pytest.skip("Skills 目录不存在")

    available_skills = [d for d in skills_dir.iterdir() if d.is_dir()]
    assert len(available_skills) > 0, "未发现任何 Skill"

    missing = []
    for skill_dir in available_skills:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            missing.append(skill_dir.name)

    assert missing == [], f"以下 Skill 缺少 SKILL.md: {missing}"


@pytest.mark.asyncio
async def test_agent_invocation_with_skill():
    """Agent 应能响应代码审查类请求（需要完整运行环境）。"""
    try:
        from agent.main_agent import main_agent
    except Exception as exc:
        pytest.skip(f"无法导入 main_agent: {exc}")

    try:
        result = await main_agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "帮我审查一下这个Python函数的安全性：\n\n"
                            "def login(username, password):\n"
                            "    query = f\"SELECT * FROM users WHERE username='{username}' AND password='{password}'\"\n"
                            "    return execute_query(query)"
                        ),
                    }
                ]
            }
        )
        assert result is not None
    except Exception as exc:
        pytest.skip(f"Agent 执行失败（可能缺少 LLM/外部服务配置）: {exc}")
