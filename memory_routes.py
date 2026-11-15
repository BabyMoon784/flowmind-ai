
import sqlite3
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic import model_validator
from openai import OpenAIError

import session_store

from memory_extraction import (
    extract_memory_candidates,
    MemoryExtractionError,
)

import agent_service
import memory_store


router = APIRouter(tags=["Memory"])


MemoryType = Literal[
    "profile",
    "preference",
    "project",
    "fact",
    "goal",
]

MemorySource = Literal[
    "manual",
    "conversation",
    "import",
    "system",
]

DUPLICATE_MEMORY_MESSAGE = (
    "该 Agent 已存在同名记忆，请修改名称或更新原记忆"
)


# ==========================================
# 1. 请求数据模型
# ==========================================

class MemoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: UUID

    memory_key: str = Field(
        min_length=1,
        max_length=100,
    )

    content: str = Field(
        min_length=1,
        max_length=3000,
    )

    memory_type: MemoryType = "fact"

    source: MemorySource = "manual"

    importance: int = Field(
        default=3,
        ge=1,
        le=5,
        strict=True,
    )

    @field_validator("memory_key", "content")
    @classmethod
    def validate_text(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("记忆名称和内容不能为空")

        return value


class MemoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    content: str | None = Field(
        default=None,
        min_length=1,
        max_length=3000,
    )

    memory_type: MemoryType | None = None

    source: MemorySource | None = None

    importance: int | None = Field(
        default=None,
        ge=1,
        le=5,
        strict=True,
    )

    @field_validator("memory_key", "content")
    @classmethod
    def validate_text(cls, value):
        if value is None:
            return value

        value = value.strip()

        if not value:
            raise ValueError("记忆名称和内容不能为空")

        return value


# ==========================================
# 2. 通用辅助函数
# ==========================================

def ensure_agent_exists(agent_id):
    """确保 Agent 存在。"""

    agent_service.get_agent(str(agent_id))


def handle_value_error(error):
    """区分重复记忆和普通参数错误。"""

    detail = str(error)

    if detail == DUPLICATE_MEMORY_MESSAGE:
        raise HTTPException(
            status_code=409,
            detail=detail,
        )

    raise HTTPException(
        status_code=422,
        detail=detail,
    )


# ==========================================
# 3. 创建记忆
# ==========================================

@router.post("/memories", status_code=201)
def create_memory(request: MemoryCreate):

    try:
        ensure_agent_exists(request.agent_id)

        memory = memory_store.create_memory(
            str(request.agent_id),
            request.memory_key,
            request.content,
            memory_type=request.memory_type,
            source=request.source,
            importance=request.importance,
        )

        return memory

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Agent 不存在",
        )

    except ValueError as e:
        handle_value_error(e)

    except (sqlite3.Error, OSError, KeyError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="创建记忆失败",
        )


# ==========================================
# 4. 获取记忆列表
# ==========================================

@router.get("/memories")
def get_memories(
    agent_id: UUID,
    memory_type: MemoryType | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):

    try:
        ensure_agent_exists(agent_id)

        memories = memory_store.list_memories(
            str(agent_id),
            memory_type=memory_type,
            limit=limit,
            offset=offset,
        )

        return {
            "count": len(memories),
            "memories": memories,
            "limit": limit,
            "offset": offset,
        }

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Agent 不存在",
        )

    except ValueError as e:
        handle_value_error(e)

    except (sqlite3.Error, OSError, KeyError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="读取记忆列表失败",
        )


# ==========================================
# 5. 获取单条记忆
# ==========================================

@router.get("/memories/{memory_id}")
def get_memory(
    memory_id: UUID,
    agent_id: UUID,
):

    try:
        ensure_agent_exists(agent_id)

        memory = memory_store.get_memory(
            str(memory_id),
            str(agent_id),
        )

        if memory is None:
            raise HTTPException(
                status_code=404,
                detail="记忆不存在",
            )

        return memory

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Agent 不存在",
        )

    except (sqlite3.Error, OSError, KeyError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="读取记忆失败",
        )


# ==========================================
# 6. 更新记忆
# ==========================================

@router.patch("/memories/{memory_id}")
def update_memory(
    memory_id: UUID,
    request: MemoryUpdate,
    agent_id: UUID,
):

    updates = request.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    if not updates:
        raise HTTPException(
            status_code=422,
            detail="至少需要提供一个更新字段",
        )

    try:
        ensure_agent_exists(agent_id)

        memory = memory_store.update_memory(
            str(memory_id),
            str(agent_id),
            **updates,
        )

        return memory

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Agent 或记忆不存在",
        )

    except ValueError as e:
        handle_value_error(e)

    except (sqlite3.Error, OSError, KeyError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="更新记忆失败",
        )


# ==========================================
# 7. 删除记忆
# ==========================================

@router.delete("/memories/{memory_id}")
def delete_memory(
    memory_id: UUID,
    agent_id: UUID,
):

    try:
        ensure_agent_exists(agent_id)

        deleted = memory_store.delete_memory(
            str(memory_id),
            str(agent_id),
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="记忆不存在",
            )

        return {
            "deleted": True,
            "memory_id": str(memory_id),
        }

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Agent 不存在",
        )

    except (sqlite3.Error, OSError, KeyError, TypeError):
        raise HTTPException(
            status_code=500,
            detail="删除记忆失败",
        )

# ==========================================
# Phase 3 Day 5
# AI 长期记忆提取接口
# ==========================================

class MemoryExtractRequest(BaseModel):
    """
    两种提取方式，二选一：

    1. text：从指定文本提取
    2. session_id：从已有聊天会话提取
    """

    model_config = ConfigDict(extra="forbid")

    agent_id: UUID

    text: str | None = Field(
        default=None,
        max_length=4000,
    )

    session_id: UUID | None = None

    @model_validator(mode="after")
    def validate_source(self):

        if (
            (self.text is None)
            == (self.session_id is None)
        ):
            raise ValueError(
                "text 和 session_id 必须且只能提供一个"
            )

        if self.text is not None:

            self.text = self.text.strip()

            if not self.text:
                raise ValueError(
                    "待提取文本不能为空"
                )

        return self


@router.post(
    "/memories/extract",
    status_code=200,
)
def extract_memories(request: MemoryExtractRequest):
    """
    从用户输入或已有聊天会话中提取候选记忆。

    本接口不会保存任何长期记忆。
    用户确认后，使用 POST /memories 保存。
    """

    agent_id = str(request.agent_id)

    try:

        # A. 校验 Agent 是否存在
        agent_service.get_agent(agent_id)

        # B. 获取待提取文本
        if request.session_id is not None:

            session_id = str(
                request.session_id
            )

            session_store.init_database()

            session = session_store.get_session(
                session_id
            )

            # 必须是该 Agent 绑定的聊天会话
            if session["agent_id"] != agent_id:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "该聊天会话不属于指定 Agent，"
                        "无法提取记忆"
                    ),
                )

            # 只读取最近的聊天消息
            history = session_store.load_history(
                session_id,
                limit=20,
            )

            # 仅从用户消息中提取长期记忆。
            # AI 的回复不作为用户事实来源。
            user_messages = [
                item["content"]
                for item in history
                if item["role"] == "user"
            ]

            source_text = "\n".join(
                f"用户：{message}"
                for message in user_messages
            )

            # 控制发给模型的文本长度
            source_text = source_text[-4000:]

        else:
            source_text = request.text

        # C. 空会话不需要调用模型
        if not source_text:
            candidates = []
        else:
            candidates = extract_memory_candidates(
                source_text
            )

        # D. 仅返回预览，不执行数据库写入
        return {
            "agent_id": agent_id,
            "candidates": candidates,
            "count": len(candidates),
            "requires_confirmation": True,
            "saved": False,
        }

    except HTTPException:
        raise

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail="Agent 或聊天会话不存在",
        ) from exc

    except MemoryExtractionError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI 记忆提取请求失败",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except (
        sqlite3.Error,
        OSError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail="记忆提取数据读取失败",
        ) from exc

