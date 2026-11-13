
import sqlite3
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field

from ai_service import chat_with_tools
from long_term_memory import format_memories
import task_service as service
import session_store
import agent_service

router = APIRouter()


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

    # 不传时使用默认 Agent
    agent_id: UUID | None = None


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    history: list[ChatMessage]



class HistoryMessage(BaseModel):
    id: int
    role: str
    content: str


class HistoryPageResponse(BaseModel):
    session_id: str
    messages: list[HistoryMessage]
    has_more: bool
    limit: int
    offset: int


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    question = request.message.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="消息不能为空"
        )

    new_session = request.session_id is None
    session_id = str(request.session_id or uuid4())

    try:
        session_store.init_database()

        # 新会话没有历史，旧会话读取最近 10 条消息
        if new_session:
            history = []
        else:
            history = session_store.load_history(session_id)

        memory_context = ""

        if request.use_long_term_memory:
            memory_context = format_memories()

        
        # 显式指定 Agent 时读取其配置
        agent_config = None

        if request.agent_id is not None:
            agent_config = agent_service.get_agent(
                str(request.agent_id)
            )

        # 保持旧版调用方式兼容
        chat_options = {
            "long_term_memory": memory_context,
        }

        if agent_config is not None:
            chat_options["agent_config"] = agent_config

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


        # 模型成功回复后，才保存这一轮对话
        updated_history = session_store.save_turn(
            session_id,
            question,
            answer,
            new_session=new_session
        )

        return ChatResponse(
            session_id=session_id,
            reply=answer,
            history=updated_history
        )

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="聊天会话不存在"
        )

    except OpenAIError:
        raise HTTPException(
            status_code=502,
            detail="AI 服务请求失败"
        )

    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="AI 服务配置或长期记忆读取失败"
        )

    except (sqlite3.Error, OSError, ValueError):
        raise HTTPException(
            status_code=500,
            detail="聊天数据处理失败"
        )



@router.get(
    "/chat/sessions/{session_id}",
    response_model=HistoryPageResponse
)
def get_session_history(
    session_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """分页获取指定会话的聊天历史。"""
    try:
        session_store.init_database()

        page = session_store.load_history_page(
            str(session_id),
            limit=limit,
            offset=offset
        )

        return HistoryPageResponse(
            session_id=str(session_id),
            messages=page["messages"],
            has_more=page["has_more"],
            limit=limit,
            offset=offset
        )

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="聊天会话不存在"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e)
        )

    except (sqlite3.Error, OSError):
        raise HTTPException(
            status_code=500,
            detail="聊天历史读取失败"
        )



@router.get("/chat/sessions")
def get_sessions():
    """获取聊天会话列表。"""
    try:
        session_store.init_database()
        return session_store.list_sessions()

    except (sqlite3.Error, OSError):
        raise HTTPException(
            status_code=500,
            detail="读取会话列表失败"
        )


@router.delete("/chat/sessions/{session_id}")
def remove_session(session_id: UUID):
    """删除一段聊天会话。"""
    try:
        session_store.init_database()

        deleted = session_store.delete_session(
            str(session_id)
        )

        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="聊天会话不存在"
            )

        return {"deleted": True}

    except (sqlite3.Error, OSError):
        raise HTTPException(
            status_code=500,
            detail="删除会话失败"
        )

