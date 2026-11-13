
import sqlite3
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field

import agent_service
import session_store
import task_service as service

from ai_service import chat_with_tools
from long_term_memory import format_memories


router = APIRouter()


# ==========================================
# 1. 请求与响应模型
# ==========================================

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(
        min_length=1,
        max_length=2000,
    )

    session_id: UUID | None = None

    use_long_term_memory: bool = False

    agent_id: UUID | None = None


class ChatResponse(BaseModel):
    session_id: str
    agent_id: str
    reply: str
    history: list[ChatMessage]


class HistoryMessage(BaseModel):
    id: int
    role: str
    content: str


class HistoryPageResponse(BaseModel):
    session_id: str
    agent_id: str | None = None
    messages: list[HistoryMessage]
    has_more: bool
    limit: int
    offset: int


# ==========================================
# 2. POST /chat
# Agent 绑定聊天
# ==========================================

@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(request: ChatRequest):

    question = request.message.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="消息不能为空",
        )

    new_session = request.session_id is None

    session_id = str(
        request.session_id or uuid4()
    )

    try:
        session_store.init_database()

        # ==================================
        # A. 确定会话绑定的 Agent
        # ==================================

        if new_session:
            # 新会话：使用用户指定的 Agent
            # 未指定时绑定默认 Agent
            agent_id = (
                str(request.agent_id)
                if request.agent_id is not None
                else agent_service.DEFAULT_AGENT_ID
            )

            history = []

        else:
            # 旧会话：优先读取数据库中的绑定
            session = session_store.get_session(
                session_id
            )

            agent_id = session["agent_id"]

            # 显式传入其他 Agent：
            # 必须拒绝，不能混用聊天历史
            if (
                request.agent_id is not None
                and str(request.agent_id) != agent_id
            ):
                raise (
                    session_store.SessionAgentMismatchError(
                        "当前会话已绑定其他 Agent。"
                        "如需切换，请创建新会话。"
                    )
                )

            history = session_store.load_history(
                session_id
            )

        # ==================================
        # B. 读取 Agent 配置
        # ==================================

        agent_config = None

        # 对于非默认 Agent：
        # 必须从数据库加载配置。
        #
        # 显式指定默认 Agent 时也加载配置。
        #
        # 默认 Agent 且未显式指定时，
        # 保持旧的 chat_with_tools 调用签名，
        # ai_service 内部会读取默认配置。

        if (
            agent_id != agent_service.DEFAULT_AGENT_ID
            or request.agent_id is not None
        ):
            agent_config = agent_service.get_agent(
                agent_id
            )

        # ==================================
        # C. 长期记忆
        # ==================================

        memory_context = ""

        if request.use_long_term_memory:
            memory_context = format_memories()

        # ==================================
        # D. 调用 AI
        # ==================================

        chat_options = {
            "long_term_memory": memory_context,
        }

        if agent_config is not None:
            chat_options["agent_config"] = (
                agent_config
            )

        answer = chat_with_tools(
            [
                *history,
                {
                    "role": "user",
                    "content": question,
                },
            ],
            service.get_task_summary,
            **chat_options,
        )

        # ==================================
        # E. 保存聊天
        # ==================================

        # AI 成功返回后才保存这一轮消息。
        # 写入前会再次检查 Agent 绑定关系。

        updated_history = session_store.save_turn(
            session_id,
            question,
            answer,
            new_session=new_session,
            agent_id=agent_id,
        )

        return ChatResponse(
            session_id=session_id,
            agent_id=agent_id,
            reply=answer,
            history=updated_history,
        )

    except (
        session_store.SessionAgentMismatchError
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except OpenAIError as exc:
        raise HTTPException(
            status_code=502,
            detail="AI 服务请求失败",
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="AI 服务配置或长期记忆读取失败",
        ) from exc

    except (
        sqlite3.Error,
        OSError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail="聊天数据处理失败",
        ) from exc


# ==========================================
# 3. GET /chat/sessions/{session_id}
# ==========================================

@router.get(
    "/chat/sessions/{session_id}",
    response_model=HistoryPageResponse,
)
def get_session_history(
    session_id: UUID,
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
):

    try:
        session_store.init_database()

        page = session_store.load_history_page(
            str(session_id),
            limit=limit,
            offset=offset,
        )

        return HistoryPageResponse(
            session_id=str(session_id),
            agent_id=page["agent_id"],
            messages=page["messages"],
            has_more=page["has_more"],
            limit=limit,
            offset=offset,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail="聊天会话不存在",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except (
        sqlite3.Error,
        OSError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail="聊天历史读取失败",
        ) from exc


# ==========================================
# 4. GET /chat/sessions
# ==========================================

@router.get("/chat/sessions")
def get_sessions():
    """获取聊天会话列表及绑定的 Agent。"""

    try:
        session_store.init_database()

        return session_store.list_sessions()

    except (
        sqlite3.Error,
        OSError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail="读取会话列表失败",
        ) from exc


# ==========================================
# 5. DELETE /chat/sessions/{session_id}
# ==========================================

@router.delete(
    "/chat/sessions/{session_id}"
)
def remove_session(session_id: UUID):
    """删除指定聊天会话。"""

    try:
        session_store.init_database()

        deleted = session_store.delete_session(
            str(session_id)
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="聊天会话不存在",
            )

        return {"deleted": True}

    except (
        sqlite3.Error,
        OSError,
    ) as exc:
        raise HTTPException(
            status_code=500,
            detail="删除会话失败",
        ) from exc
