
"""
FlowMind AI - Long-Term Memory Routes

功能：
1. Agent 独立长期记忆
2. 创建长期记忆
3. 查看长期记忆列表
4. 查看单条记忆
5. 编辑长期记忆
6. 删除长期记忆
7. AI 自动提取候选记忆
8. 用户审核确认后保存

所有记忆均按 Agent ID 隔离。
"""

import sqlite3
from typing import Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from openai import OpenAIError

import agent_service
import memory_store
import session_store

from memory_extraction import (
    extract_memory_candidates,
    MemoryExtractionError,
)


router = APIRouter(tags=["Memory"])


# ==========================================
# 1. 记忆类型和来源
# ==========================================

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
# 2. 创建记忆的数据模型
# ==========================================

class MemoryCreate(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

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

    @field_validator(
        "memory_key",
        "content",
    )
    @classmethod
    def validate_text(cls, value):

        value = value.strip()

        if not value:
            raise ValueError(
                "记忆名称和内容不能为空"
            )

        return value


# ==========================================
# 3. 更新记忆的数据模型
# ==========================================

class MemoryUpdate(BaseModel):

    model_config = ConfigDict(
        extra="forbid"
    )

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

    @field_validator(
        "memory_key",
        "content",
    )
    @classmethod
    def validate_text(cls, value):

        if value is None:
            return value

        value = value.strip()

        if not value:
            raise ValueError(
                "记忆名称和内容不能为空"
            )

        return value


# ==========================================
# 4. 通用辅助函数
# ==========================================

def ensure_agent_exists(agent_id):
    """
    确保指定 Agent 存在。

    如果不存在，agent_service
    会抛出 LookupError。
    """

    agent_service.get_agent(
        str(agent_id)
    )


def handle_value_error(error):
    """
    区分重复记忆与其他参数错误。

    同名记忆：409
    普通参数错误：422
    """

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
# 5. POST /memories
# 创建长期记忆
# ==========================================

@router.post(
    "/memories",
    status_code=201,
)
def create_memory(
    request: MemoryCreate,
):

    try:

        # A. 确认 Agent 存在
        ensure_agent_exists(
            request.agent_id
        )

        # B. 保存到 SQLite
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

    except ValueError as exc:

        handle_value_error(exc)

    except (
        sqlite3.Error,
        OSError,
        KeyError,
        TypeError,
    ):

        raise HTTPException(
            status_code=500,
            detail="创建记忆失败",
        )


# ==========================================
# 6. GET /memories
# 查看当前 Agent 的长期记忆列表
# ==========================================

@router.get("/memories")
def get_memories(
    agent_id: UUID,

    memory_type: MemoryType | None = None,

    limit: int = Query(
        default=100,
        ge=1,
        le=500,
    ),

    offset: int = Query(
        default=0,
        ge=0,
    ),
):

    try:

        # A. 确认 Agent 存在
        ensure_agent_exists(agent_id)

        # B. 只读取该 Agent 的记忆
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

    except ValueError as exc:

        handle_value_error(exc)

    except (
        sqlite3.Error,
        OSError,
        KeyError,
        TypeError,
    ):

        raise HTTPException(
            status_code=500,
            detail="读取记忆列表失败",
        )


# ==========================================
# 7. GET /memories/{memory_id}
# 查看单条记忆
# ==========================================

@router.get(
    "/memories/{memory_id:uuid}"
)
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

    except (
        sqlite3.Error,
        OSError,
        KeyError,
        TypeError,
    ):

        raise HTTPException(
            status_code=500,
            detail="读取记忆失败",
        )


# ==========================================
# 8. PATCH /memories/{memory_id}
# 更新长期记忆
# ==========================================

@router.patch(
    "/memories/{memory_id:uuid}"
)
def update_memory(
    memory_id: UUID,
    request: MemoryUpdate,
    agent_id: UUID,
):

    # 只更新本次请求明确提供的字段
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

        # A. 确认 Agent 存在
        ensure_agent_exists(agent_id)

        # B. 更新该 Agent 的指定记忆
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

    except ValueError as exc:

        handle_value_error(exc)

    except (
        sqlite3.Error,
        OSError,
        KeyError,
        TypeError,
    ):

        raise HTTPException(
            status_code=500,
            detail="更新记忆失败",
        )


# ==========================================
# 9. DELETE /memories/{memory_id}
# 删除长期记忆
# ==========================================

@router.delete(
    "/memories/{memory_id:uuid}"
)
def delete_memory(
    memory_id: UUID,
    agent_id: UUID,
):

    try:

        # A. 确认 Agent 存在
        ensure_agent_exists(agent_id)

        # B. 删除指定记忆
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

    except (
        sqlite3.Error,
        OSError,
        KeyError,
        TypeError,
    ):

        raise HTTPException(
            status_code=500,
            detail="删除记忆失败",
        )


# ==========================================
# 10. AI 记忆提取请求模型
# ==========================================

class MemoryExtractRequest(BaseModel):
    """
    从以下来源中选择一种提取：

    1. text
       从指定文本中提取候选记忆。

    2. session_id
       从已有聊天会话中提取候选记忆。

    text 和 session_id 必须二选一。

    提取结果不会自动保存。
    """

    model_config = ConfigDict(
        extra="forbid"
    )

    agent_id: UUID

    text: str | None = Field(
        default=None,
        max_length=4000,
    )

    session_id: UUID | None = None

    @model_validator(mode="after")
    def validate_source(self):

        # 必须且只能选择一种来源
        if (
            (self.text is None)
            == (self.session_id is None)
        ):

            raise ValueError(
                "text 和 session_id 必须且只能提供一个"
            )

        # 清理用户输入文本
        if self.text is not None:

            self.text = self.text.strip()

            if not self.text:

                raise ValueError(
                    "待提取文本不能为空"
                )

        return self


# ==========================================
# 11. POST /memories/extract
# AI 自动提取候选长期记忆
# ==========================================

@router.post(
    "/memories/extract",
    status_code=200,
)
def extract_memories(
    request: MemoryExtractRequest,
):
    """
    使用 DeepSeek 提取候选记忆。

    支持：
    - 从指定文本提取
    - 从当前 Agent 的聊天会话提取

    安全原则：
    - 只从用户消息中提取
    - 不把 AI 回复当作用户事实
    - 只返回候选记忆
    - 不自动写入 SQLite
    - 必须由用户确认后再保存
    """

    agent_id = str(request.agent_id)

    try:

        # ==================================
        # A. 验证当前 Agent
        # ==================================

        agent_service.get_agent(
            agent_id
        )

        # ==================================
        # B. 获取待提取文本
        # ==================================

        if request.session_id is not None:

            session_id = str(
                request.session_id
            )

            session_store.init_database()

            session = session_store.get_session(
                session_id
            )

            # 防止提取其他 Agent 的聊天
            if session["agent_id"] != agent_id:

                raise HTTPException(
                    status_code=409,
                    detail=(
                        "该聊天会话不属于指定 Agent，"
                        "无法提取记忆"
                    ),
                )

            # 读取最近的聊天记录
            history = session_store.load_history(
                session_id,
                limit=20,
            )

            # 只提取用户消息
            user_messages = [
                item["content"]
                for item in history
                if item["role"] == "user"
            ]

            source_text = "\n".join(
                f"用户：{message}"
                for message in user_messages
            )

            # 控制上下文大小
            source_text = source_text[-4000:]

        else:

            # 用户自行输入的文本
            source_text = request.text

        # ==================================
        # C. 调用 AI 提取候选记忆
        # ==================================

        if not source_text:

            # 空会话无需请求模型
            candidates = []

        else:

            candidates = extract_memory_candidates(
                source_text
            )

        # ==================================
        # D. 返回候选记忆
        # ==================================

        # 不执行数据库写入。
        # 用户确认后，前端调用：
        # POST /memories

        return {
            "agent_id": agent_id,
            "candidates": candidates,
            "count": len(candidates),
            "requires_confirmation": True,
            "saved": False,
        }

    # ======================================
    # 错误处理
    # ======================================

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
