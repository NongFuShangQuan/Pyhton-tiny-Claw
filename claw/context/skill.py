"""context.skill: 技能外挂加载 (与 .claw/skills/ 目录约定对接)。

"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Skill:
    name: str = "Unknown Skill"
    description: str = "No description provided."
    body: str = ""


class SkillLoader:
    def __init__(self, work_dir: str | os.PathLike):
        self.work_dir = Path(work_dir)

    def load_all(self) -> str:
        """扫描 .claw/skills 目录下所有 SKILL.md，组装头部说明字符串。"""
        skill_dir = self.work_dir / ".claw" / "skills"
        if not skill_dir.exists():
            return ""

        builder: list[str] = []
        builder.append("\n### 可用专业技能 (Agent Skills)")
        builder.append(
            "以下是你拥有的标准化外挂技能，请在符合 description 描述的场景下严格遵循其正文指令：\n"
        )

        count = 0
        for skill_file in skill_dir.rglob("SKILL.md"):
            try:
                content = skill_file.read_text(encoding="utf-8")
            except OSError:
                continue
            skill = parse_skill_md(content)
            count += 1
            builder.append(f"#### 技能名称: {skill.name}")
            builder.append(f"**触发条件**: {skill.description}\n")
            builder.append("**执行指南**:")
            builder.append(skill.body)
            builder.append("\n\n---\n")

        if count == 0:
            return ""
        # 简单防滑标志：和 Go 版保持 < 50 字符返回空逻辑一致
        text = "\n".join(builder)
        if len(text) < 50:
            return ""
        return text


def parse_skill_md(content: str) -> Skill:
    """解析带 frontmatter 的 SKILL.md。"""
    skill = Skill(name="Unknown Skill", description="No description provided.", body=content)

    if content.startswith("---\n") or content.startswith("---\r\n"):
        parts = content.split("---", 2)
        if len(parts) == 3:
            frontmatter = parts[1]
            skill.body = parts[2].strip()
            for raw in frontmatter.splitlines():
                line = raw.strip()
                if line.startswith("name:"):
                    skill.name = line[len("name:") :].strip()
                elif line.startswith("description:"):
                    skill.description = line[len("description:") :].strip()
    return skill


def NewSkillLoader(work_dir: str | os.PathLike) -> SkillLoader:
    return SkillLoader(work_dir)


__all__ = ["Skill", "SkillLoader", "NewSkillLoader", "parse_skill_md"]