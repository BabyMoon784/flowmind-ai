
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

import task_service


logger = logging.getLogger(__name__)


# ==========================================
# 1. 工具参数模型
# ==========================================

class EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        min_length=1,
        max_length=100,
        description="需要创建的任务名称",
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("任务名称不能为空")

        return value


class UpdateTaskArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: int = Field(
        ge=1,
        description="任务 ID，必须是正整数",
    )

    status: Literal["待完成", "已完成"] = Field(
        description="要设置的任务状态",
    )


# ==========================================
# 2. 单个工具的定义
# ==========================================

@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[..., Any]


# ==========================================
# 3. 工具注册与执行
# ==========================================

class ToolRegistry:

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(
        self,
        name: str,
        description: str,
        args_model: type[BaseModel],
        handler: Callable[..., Any],
    ):
        """注册一个可供 Agent 使用的工具。"""

        if name in self._tools:
            raise ValueError(f"工具重复注册：{name}")

        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            args_model=args_model,
            handler=handler,
        )

    def schemas(
        self,
        allowed_names: set[str] | None = None,
    ) -> list[dict]:
        """生成发送给大模型的 Function Calling 描述。"""

        result = []

        for tool in self._tools.values():
            if (
                allowed_names is not None
                and tool.name not in allowed_names
            ):
                continue

            result.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": (
                        tool.args_model.model_json_schema()
                    ),
                },
            })

        return result

    def execute(
        self,
        name: str,
        raw_arguments: str = "{}",
        allowed_names: set[str] | None = None,
    ) -> dict:
        """验证参数、检查权限并执行工具。"""

        # 权限必须在执行时再次检查，
        # 不能只依赖发送给大模型的工具列表。
        if (
            allowed_names is not None
            and name not in allowed_names
        ):
            return {
                "ok": False,
                "error": "当前 Agent 无权使用该工具",
            }

        tool = self._tools.get(name)

        if tool is None:
            return {
                "ok": False,
                "error": f"未注册的工具：{name}",
            }

        # 解析模型返回的 JSON 参数
        try:
            arguments = json.loads(raw_arguments or "{}")
        except (json.JSONDecodeError, TypeError):
            return {
                "ok": False,
                "error": "工具参数不是合法的 JSON",
            }

        if not isinstance(arguments, dict):
            return {
                "ok": False,
                "error": "工具参数必须是 JSON 对象",
            }

        # 使用 Pydantic 校验参数
        try:
            validated = tool.args_model.model_validate(
                arguments
            )
        except ValidationError:
            return {
                "ok": False,
                "error": "工具参数校验失败",
            }

        # 执行真实 Python 函数
        try:
            data = tool.handler(
                **validated.model_dump()
            )

            return {
                "ok": True,
                "data": data,
            }

        except (LookupError, ValueError) as error:
            return {
                "ok": False,
                "error": str(error),
            }

        except Exception:
            logger.exception("工具执行失败：%s", name)

            return {
                "ok": False,
                "error": "工具执行失败，请检查后端日志",
            }


# ==========================================
# 4. 注册 FlowMind 任务工具
# ==========================================

def build_task_registry(
    task_summary_func: Callable | None = None,
) -> ToolRegistry:

    registry = ToolRegistry()

    registry.register(
        name="get_task_summary",
        description=(
            "统计当前任务总数、已完成数量、"
            "未完成数量。用户询问任务数量时调用。"
        ),
        args_model=EmptyArgs,
        handler=(
            task_summary_func
            if task_summary_func is not None
            else task_service.get_task_summary
        ),
    )

    registry.register(
        name="list_tasks",
        description=(
            "查询所有任务的 ID、标题和状态。"
            "用户想查看任务清单或寻找任务 ID 时调用。"
        ),
        args_model=EmptyArgs,
        handler=task_service.list_tasks,
    )

    registry.register(
        name="create_task",
        description=(
            "向任务数据库创建新任务。"
            "仅在用户明确要求添加或创建任务时调用。"
        ),
        args_model=CreateTaskArgs,
        handler=task_service.create_task,
    )

    registry.register(
        name="update_task_status",
        description=(
            "根据任务 ID 更新任务状态。"
            "仅在用户明确要求修改或完成任务时调用。"
            "如果不知道任务 ID，应先查询任务列表。"
        ),
        args_model=UpdateTaskArgs,
        handler=task_service.update_task_status,
    )

    return registry
