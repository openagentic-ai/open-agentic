"""模块说明（中文）：`src/openagentic/workflow/presets.py`。

系统预设工作流定义 + 启动时 upsert 逻辑。

在 FastAPI lifespan 中调用 load_presets()，扫描 ``presets/`` 目录下的 YAML 文件，
按 slug 匹配已有记录 → 按 version 决定是否升级，保证系统工作流定义最新且跨渠道一致。
"""

from __future__ import annotations

import structlog
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from openagentic.workflow.models import Workflow

logger = structlog.get_logger("openagentic.workflow.presets")

PRESETS_DIR = Path(__file__).parent / "presets"


def _load_preset_yaml(path: Path) -> dict | None:
    """加载单个 YAML 预设文件，返回 dict 或 None（解析失败）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        logger.exception("failed to load preset yaml", path=str(path))
        return None

    required = {"slug", "version", "name", "definition"}
    missing = required - set(data.keys())
    if missing:
        logger.warning("preset yaml missing required keys", path=str(path), missing=sorted(missing))
        return None
    return data


def _scan_presets() -> list[dict]:
    """扫描 presets 目录，返回所有合法预设 dict 列表（按 slug 去重，同名后者覆盖）。"""
    if not PRESETS_DIR.is_dir():
        logger.warning("presets directory not found", path=str(PRESETS_DIR))
        return []

    seen: dict[str, dict] = {}
    for yaml_file in sorted(PRESETS_DIR.glob("*.yaml")):
        data = _load_preset_yaml(yaml_file)
        if data is None:
            continue
        slug = data["slug"]
        if slug in seen:
            logger.info("preset slug shadowed by later file", slug=slug, path=str(yaml_file))
        seen[slug] = data

    return list(seen.values())


async def load_presets(db: AsyncSession) -> list[str]:
    """在应用启动时 upsert 系统预设工作流。

    按 slug（唯一索引）匹配已有记录：
    - 不存在 → 新建（user_id=NULL, is_system=True）
    - 存在但 version 更大 → 更新 definition + description + version
    - 存在且 version 相同 → 跳过
    - 存在但 version 更小 → 跳过（不允许降级）

    返回本次新建/更新的 slug 列表（供日志输出）。
    """
    presets = _scan_presets()
    if not presets:
        logger.info("no preset workflows found")
        return []

    changed: list[str] = []

    for preset in presets:
        slug = preset["slug"]
        version = int(preset["version"])
        result = await db.execute(
            select(Workflow).where(Workflow.slug == slug)
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            wf = Workflow(
                user_id=None,
                slug=slug,
                name=preset["name"],
                description=preset.get("description", ""),
                definition=preset["definition"],
                version=version,
                is_system=True,
                is_active=True,
            )
            db.add(wf)
            changed.append(slug)
            logger.info("preset workflow created", slug=slug, version=version)
        elif existing.version < version:
            existing.name = preset["name"]
            existing.description = preset.get("description", "")
            existing.definition = preset["definition"]
            existing.version = version
            changed.append(slug)
            logger.info("preset workflow upgraded", slug=slug,
                        old_version=existing.version - 1, new_version=version)
        elif existing.version > version:
            logger.info("preset workflow version older, skipped",
                        slug=slug, existing_version=existing.version, yaml_version=version)
        else:
            logger.debug("preset workflow up-to-date", slug=slug, version=version)

    if changed:
        await db.flush()
        logger.info("preset workflows upserted", count=len(changed), slugs=changed)
    else:
        logger.info("preset workflows up-to-date", count=len(presets))

    return changed
