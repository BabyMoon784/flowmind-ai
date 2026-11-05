
import sqlite3
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from openai import OpenAIError
from pydantic import BaseModel, ConfigDict, Field

from ai_service import chat_with_tools
from long_term_memory import format_memories
import task_service as service
import session_store


router = APIRouter()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    session_id: UUID | None = None
    use_long_term_memory: bool = False


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    history: list[ChatMessage]


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

        answer = chat_with_tools(
            [
                *history,
                {"role": "user", "content": question}
            ],
            service.get_task_summary,
            long_term_memory=memory_context
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
    response_model=list[ChatMessage]
)
def get_session_history(session_id: UUID):
    try:
        session_store.init_database()

        return session_store.load_history(
            str(session_id)
        )

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="聊天会话不存在"
        )

    except (sqlite3.Error, OSError):
        raise HTTPException(
            status_code=500,
            detail="聊天历史读取失败"
        )

