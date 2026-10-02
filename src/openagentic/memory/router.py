"""模块说明（中文）：`src/openagentic/memory/router.py`。

四层记忆 REST API —— 将 MemoryManager 暴露为 HTTP 接口，
供飞书/企微/小程序/App 等非 Python 客户端读写记忆。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from openagentic.core.auth.models import User
from openagentic.deps import get_current_user

from openagentic.memory.manager import MemoryManager, CORE_CATEGORIES
from openagentic.memory.schemas import (
    CoreMemoryCreate,
    CoreMemoryResponse,
    EpisodeCreate,
    EpisodeResponse,
    ProcedureCreate,
    ProcedureResponse,
    CoreCategory,
)

router = APIRouter(prefix="/api/memory", tags=["memory"])

def get_memory_manager(current: User = Depends(get_current_user)) -> MemoryManager:
    if not current.is_active:
        raise HTTPException(403, "Account is inactive")
    return MemoryManager.for_user(str(current.id))


# -- Core Memory -----------------------------------------------------------


@router.get("/core", response_model=list[CoreMemoryResponse])
def list_core(
    category: CoreCategory | None = Query(None, description="过滤分类"),
    limit: int = Query(20, ge=1, le=100),
    _mgr: MemoryManager = Depends(get_memory_manager),
):
    """列出 Core Memory（按 importance 降序）。"""
    entries = _mgr.list_core(category=category, limit=limit)
    return [CoreMemoryResponse(**e.__dict__) for e in entries]


@router.get("/core/search", response_model=list[CoreMemoryResponse])
def search_core(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    category: CoreCategory | None = Query(None),
    top_k: int = Query(10, ge=1, le=50),
    _mgr: MemoryManager = Depends(get_memory_manager),
):
    """关键词搜索 Core Memory。"""
    entries = _mgr.search_core(q, category=category, top_k=top_k)
    return [CoreMemoryResponse(**e.__dict__) for e in entries]


@router.post("/core", status_code=201)
def save_core(body: CoreMemoryCreate, _mgr: MemoryManager = Depends(get_memory_manager)):
    """保存一条 Core Memory（key 已存在则更新）。"""
    if body.category not in CORE_CATEGORIES:
        raise HTTPException(400, f"Invalid category: {body.category}. Must be one of {CORE_CATEGORIES}")
    path = _mgr.save_core_memory(
        key=body.key, value=body.value,
        category=body.category, importance=body.importance,
    )
    return {"saved": body.key, "file": path}


@router.delete("/core/{key}")
def delete_core(key: str, _mgr: MemoryManager = Depends(get_memory_manager)):
    """按 key 删除一条 Core Memory。"""
    if not _mgr.delete_core_memory(key):
        raise HTTPException(404, f"Core memory not found: {key}")
    return {"deleted": key}


# -- Episodic Memory --------------------------------------------------------


@router.get("/episodes/search", response_model=list[EpisodeResponse])
def search_episodes(
    q: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=50),
    _mgr: MemoryManager = Depends(get_memory_manager),
):
    """关键词搜索 Episodic Memory。"""
    return [EpisodeResponse(**e) for e in _mgr.search_episodes(q, top_k=top_k)]


@router.post("/episodes", status_code=201)
def save_episode(body: EpisodeCreate, _mgr: MemoryManager = Depends(get_memory_manager)):
    """保存一条情节记忆（对话/任务摘要）。"""
    path = _mgr.save_episode(body.title, body.summary, body.tags)
    return {"saved": body.title, "file": path}


# -- Procedural Memory ------------------------------------------------------


@router.get("/procedures/search", response_model=list[ProcedureResponse])
def search_procedures(
    q: str = Query(..., min_length=1),
    top_k: int = Query(3, ge=1, le=50),
    _mgr: MemoryManager = Depends(get_memory_manager),
):
    """关键词搜索 Procedural Memory。"""
    return [ProcedureResponse(**p) for p in _mgr.search_procedures(q, top_k=top_k)]


@router.post("/procedures", status_code=201)
def save_procedure(body: ProcedureCreate, _mgr: MemoryManager = Depends(get_memory_manager)):
    """保存一条可复用步骤。"""
    path = _mgr.save_procedure(
        body.name, body.description,
        body.trigger_pattern, body.steps,
    )
    return {"saved": body.name, "file": path}


@router.get("/vault")
def vault_status(_mgr: MemoryManager = Depends(get_memory_manager)):
    return {"mode": "obsidian-compatible", "path": str(_mgr.vault.root),
            "capabilities": ["markdown", "properties", "wikilinks", "backlinks", "search"]}


@router.get("/vault/search")
def search_vault(
    q: str = Query(default="", max_length=200),
    top_k: int = Query(default=20, ge=1, le=50),
    _mgr: MemoryManager = Depends(get_memory_manager),
):
    return _mgr.vault.search(q, top_k, folder="procedures")


@router.get("/vault/note")
def read_vault_note(
    path: str = Query(min_length=1, max_length=500),
    _mgr: MemoryManager = Depends(get_memory_manager),
):
    try:
        note = _mgr.vault.read(path)
        return {**note, "backlinks": _mgr.vault.backlinks(path), "uri": _mgr.vault.uri(path)}
    except FileNotFoundError as exc:
        raise HTTPException(404, "Note not found") from exc
    except (ValueError, OSError, UnicodeError) as exc:
        raise HTTPException(400, "Invalid vault note") from exc
