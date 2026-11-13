
import logging
import sqlite3

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import agent_service as service


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agents",
    tags=["Agents"],
)


# ==========================================
# 1. 创建 Agent 的请求模型
# ==========================================

class AgentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=40,
        description="Agent 名称",
    )

    description: str = Field(
        default="",
        max_length=300,
    )

    personality: str = "professional"

    response_style: str = "balanced"

    custom_instructions: str = Field(
        default="",
        max_length=2000,
    )

    enabled_tools: list[str] | None = None


# ==========================================
# 2. 更新 Agent 的请求模型
# ==========================================

class AgentUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        max_length=40,
    )

    description: str | None = Field(
        default=None,
        max_length=300,
    )

    personality: str | None = None

    response_style: str | None = None

    custom_instructions: str | None = Field(
        default=None,
        max_length=2000,
    )

    enabled_tools: list[str] | None = None


# ==========================================
# 3. Agent 响应模型
# ==========================================

class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    personality: str
    response_style: str
    custom_instructions: str
    enabled_tools: list[str]
    created_at: str
    updated_at: str


# ==========================================
# 4. POST /agents
# 创建 Agent
# ==========================================

@router.post(
    "",
    response_model=AgentResponse,
    status_code=201,
)
def create_agent(request: AgentCreateRequest):

    try:
        return service.create_agent(
            **request.model_dump(exclude_none=True)
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except (sqlite3.Error, OSError) as exc:
        logger.exception("创建 Agent 失败")

        raise HTTPException(
            status_code=500,
            detail="Agent 创建失败",
        ) from exc


# ==========================================
# 5. GET /agents
# 获取 Agent 列表
# ==========================================

@router.get(
    "",
    response_model=list[AgentResponse],
)
def list_agents():

    try:
        return service.list_agents()

    except (sqlite3.Error, OSError, ValueError) as exc:
        logger.exception("读取 Agent 列表失败")

        raise HTTPException(
            status_code=500,
            detail="Agent 列表读取失败",
        ) from exc


# ==========================================
# 6. GET /agents/{agent_id}
# 获取指定 Agent
# ==========================================

@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
)
def get_agent(agent_id: str):

    try:
        return service.get_agent(agent_id)

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail="Agent 不存在",
        ) from exc

    except (sqlite3.Error, OSError, ValueError) as exc:
        logger.exception("读取 Agent 失败")

        raise HTTPException(
            status_code=500,
            detail="Agent 配置读取失败",
        ) from exc


# ==========================================
# 7. PATCH /agents/{agent_id}
# 更新指定 Agent
# ==========================================

@router.patch(
    "/{agent_id}",
    response_model=AgentResponse,
)
def update_agent(
    agent_id: str,
    request: AgentUpdateRequest,
):

    # 没有传入的字段不修改
    # None 也表示不修改
    # [] 和 "" 则可以清空对应的配置

    updates = request.model_dump(
        exclude_unset=True,
        exclude_none=True,
    )

    try:
        return service.update_agent(
            agent_id,
            **updates,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail="Agent 不存在",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except (sqlite3.Error, OSError) as exc:
        logger.exception("更新 Agent 失败")

        raise HTTPException(
            status_code=500,
            detail="Agent 配置更新失败",
        ) from exc
