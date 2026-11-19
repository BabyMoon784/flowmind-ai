# FlowMind AI

**基于 FastAPI、Vue 3、DeepSeek 和 SQLite 的个人 AI Agent 管理平台**

FlowMind AI 是一个面向个人效率和 AI 应用探索的全栈智能体项目。项目从 Python 命令行工具逐步演进为 Web 应用，支持自定义 Agent、工具调用、持久化聊天记录、Agent 独立长期记忆，以及文档和图片理解。

项目重点是探索如何将大语言模型能力与实际软件系统结合，而不仅仅实现一个基础聊天界面。

## 1. 核心功能

### 多 Agent 管理

- 创建和管理不同用途的 AI Agent
- 为 Agent 配置独立的人格和行为规则
- 每段聊天会话绑定指定 Agent
- 在不同 Agent 之间切换工作场景

### AI 对话与工具调用

- 基于 DeepSeek API 实现多轮 AI 对话
- 支持工具调用，将大语言模型与任务管理功能结合
- 支持 Markdown、代码高亮与数学公式渲染
- 支持聊天记录持久化、恢复与删除

### 独立长期记忆

- 基于 SQLite 存储长期记忆
- 不同 Agent 使用独立的记忆空间
- 根据用户问题检索相关记忆并注入对话上下文
- 支持记忆的新增、查看、修改、删除
- 支持从聊天记录或指定文字中提取候选记忆
- AI 提取结果需要用户审核确认后才能保存

### 文档与图片理解

- 支持 TXT、Markdown、PDF、DOCX 文档文本提取
- 支持 PNG、JPG、JPEG 图片分析
- 使用视觉模型提取图片中的关键信息
- 将文档文本或图片分析结果提供给当前 Agent 进行问答
- 限制上传文件大小并验证文件格式

当前附件功能采用单轮上下文方案，附件原始内容不会自动持久化到聊天历史。

## 2. 技术栈

| 层次 | 技术 |
|---|---|
| 前端 | Vue 3、Vite、JavaScript |
| 后端 | Python、FastAPI、Pydantic |
| AI 模型 | DeepSeek API |
| 数据存储 | SQLite |
| 文本渲染 | Markdown、KaTeX |
| 文件处理 | PDF、DOCX 文本解析、Pillow |
| 测试 | Pytest |
| 版本管理 | Git、GitHub |

## 3. 系统架构

```text
                 FlowMind AI
                      |
               Vue 3 Web UI
                      |
              Axios HTTP API
                      |
                 FastAPI
                      |
       +--------------+--------------+
       |              |              |
  Agent 管理       聊天服务       附件服务
       |              |              |
       |         DeepSeek API    文档文本提取
       |              |          图片视觉分析
       |          工具调用           |
       |              |              |
       +--------------+--------------+
                      |
              SQLite 数据存储
                      |
          +-----------+-----------+
          |                       |
       会话历史               Agent 长期记忆
```

## 4. 项目运行

### 环境准备

需要安装 Python、Node.js、npm 和 Git。

### 启动后端

在项目根目录创建 Python 虚拟环境并安装依赖：

```powershell
python -m venv .venv

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

在项目根目录配置 `.env`，设置 DeepSeek API Key：

```env
DEEPSEEK_API_KEY=填写你的API Key```

启动 FastAPI：

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --reload
```

API 文档默认地址：

`http://127.0.0.1:8000/docs`

### 启动前端

另开一个终端：

```powershell
cd frontend

npm install

npm run dev
```

前端默认地址：

`http://localhost:5173`

## 5. 测试

运行全部后端自动化测试：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

当前开发阶段的测试结果：

```text
167 passed in 4.14s
```

前端生产构建：

```powershell
cd frontend

npm run build
```

当前版本已通过 Vite 生产构建，仍有 JavaScript Bundle 体积优化空间。

## 6. 项目特色

**Agent 级别的数据隔离：** 会话和长期记忆按 Agent 进行关联，避免不同角色之间的数据混用。

**记忆提取审核机制：** AI 不会直接将提取出的候选信息写入长期记忆，而是经过用户确认。

**工具调用集成：** 通过函数调用机制，让语言模型不仅能够生成文本，还能够使用应用中的任务管理能力。

**多模态扩展：** 在原有文字聊天基础上，逐步加入文档读取和图片理解，使 Agent 能够处理更多实际使用场景。

**自动化测试：** 通过 Pytest 对后端接口及核心逻辑进行回归验证。

## 7. 后续计划

- 完善前端交互与响应式布局
- 优化大体积 JavaScript 资源的加载性能
- 增强 Agent 人格一致性和记忆检索质量
- 实现附件持久化和连续多轮文件问答
- 增加 RAG 知识库检索
- 完善部署配置与生产环境安全措施
- 部署在线演示版本

## 8. 开发状态

目前项目主要在 Windows 本地开发环境中运行。

核心功能已经实现，正在进行工程化整理、文档完善和部署准备。

---

**FlowMind AI — Building practical AI Agents with memory, tools and multimodal capabilities.**