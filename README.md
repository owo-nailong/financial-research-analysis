# 金融研报智能分析与投资决策辅助系统

**智研 AI** 是一套面向投研场景的本地化智能分析系统，覆盖多源金融信息聚合、结构化抽取、观点与情绪分析、知识库 RAG 问答、行情看板、内容生成与多智能体协同，支持管理员与普通用户权限分离。

> 本仓库提供 **Docker 一键部署** 与 **本地开发** 两种方式。推荐首次体验使用 Docker，无需手动安装 MySQL、Redis 与 Node 环境。

---

## 目录

- [功能概览](#功能概览)
- [技术架构](#技术架构)
- [环境要求](#环境要求)
- [快速开始（Docker，推荐）](#快速开始docker推荐)
- [本地开发启动](#本地开发启动)
- [默认账号与访问地址](#默认账号与访问地址)
- [使用说明](#使用说明)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [常见问题](#常见问题)
- [测试](#测试)
- [免责声明](#免责声明)

---

## 功能概览

| 模块 | 说明 |
|------|------|
| 智能对话 | 自然语言提问；可启用知识库检索（RAG）；支持关注标的代码缩小检索范围 |
| 数据看板 | A 股代码/名称搜索，日 K 蜡烛图、周期高低与均线；管理员可同步公开行情源数据 |
| 内容工作台 | 按模板生成研报摘要、投资建议等，支持下载；管理员可写入知识库 |
| 多智能体 | 分析师 / 投资者视角 / 审核 / 经理等角色协同产出综合结论 |
| 知识库管理 | 文档导入、启用/停用、检索状态查看（管理员） |
| RAG 参数 | 切分策略、块大小、重叠、Top-K、阈值等（管理员） |
| 系统管理 | 运行状态、用户与密码管理、数据目录导入知识库（管理员） |
| 账号安全 | 登录密码 RSA-OAEP 加密传输；普通用户可在「安全管理」修改密码 |

---

## 技术架构

| 层级 | 选型 |
|------|------|
| 前端 | Vue 3 · Vite · Nginx（生产镜像） |
| 后端 | Python 3 · FastAPI · SQLAlchemy |
| 数据存储 | MySQL 8（或 SQLite 精简模式）· Redis |
| 大模型 | Ollama（默认 `qwen2.5:latest`） |
| 向量嵌入 | Ollama（默认 `embeddinggemma:latest`）· 本地向量索引 |
| 部署 | Docker Compose |

数据与向量索引默认落在项目 `data/` 目录（或 Docker 数据卷），配置通过环境变量完成。

---

## 环境要求

### 方式 A：Docker（推荐给最终使用者）

| 项目 | 要求 |
|------|------|
| 软件 | [Docker Desktop](https://www.docker.com/products/docker-desktop/) 或兼容的 Docker Engine + Compose |
| 硬件（完整版） | 建议 **16GB+ 内存**；首次需下载镜像与模型（数 GB 级） |
| 网络 | 可访问 Docker Hub 与 Ollama 模型源（或已提前准备好模型） |
| 系统 | Windows 10/11、macOS、Linux |

### 方式 B：本地开发

| 项目 | 要求 |
|------|------|
| 运行时 | Python 3.10+、Node.js 18+ |
| 中间件 | MySQL 8.x、Redis（可选）、[Ollama](https://ollama.com/) |
| 模型 | `qwen2.5:latest`、`embeddinggemma:latest` |

---

## 快速开始（Docker，推荐）

### 1. 获取代码

```bash
git clone https://github.com/owo-nailong/financial-research-analysis.git
cd financial-research-analysis
```

若使用压缩包，解压后进入项目根目录即可。

### 2. 启动服务

**Windows**

1. 确认 Docker Desktop 已启动  
2. 双击项目根目录 **`docker-start.bat`**  
   - 脚本会自动构建、启动容器  
   - 检测模型是否已存在，**已有则跳过下载**

**macOS / Linux / 命令行**

```bash
docker compose up -d --build

# 首次需要拉取模型（体积较大，请保持网络畅通）
docker compose exec ollama ollama pull qwen2.5:latest
docker compose exec ollama ollama pull embeddinggemma:latest
```

首次构建通常需要 **5～20 分钟**（取决于网络与机器性能）。

### 3. 打开系统

浏览器访问：**http://localhost:8080**

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | `admin` | `admin123` |
| 普通用户 | `user` | `user123` |

生产或公网环境请务必修改默认密码与 `JWT_SECRET`（见[配置说明](#配置说明)）。

### 4. 停止服务

```bash
docker compose down          # 停止容器，保留数据卷
docker compose down -v       # 停止并删除数据卷（清空数据库与模型卷，慎用）
```

Windows 也可双击 **`docker-stop.bat`**。

### 精简版（低配机器 / 仅浏览界面）

不启动 MySQL 与容器内 Ollama，使用 SQLite，对话能力受限：

```bash
docker compose -f docker-compose.lite.yml up -d --build
```

访问地址同为 http://localhost:8080 。

### 本机已有 Ollama 模型时（避免重复下载）

Docker 内 Ollama **默认使用独立数据卷**，与本机 `~/.ollama` 不共享。若本机已下载过 `qwen2.5`、`embeddinggemma`，可在项目根目录创建 `.env`（可参考 `.env.docker.example`）：

```env
# 方式一：挂载本机模型目录（路径请改成你的用户名）
# Windows
OLLAMA_MODELS_DIR=C:\Users\你的用户名\.ollama
# Linux:  OLLAMA_MODELS_DIR=/home/你的用户名/.ollama
# macOS:  OLLAMA_MODELS_DIR=/Users/你的用户名/.ollama

# 方式二：直接使用本机已运行的 Ollama 服务（本机需已启动 ollama serve）
# OLLAMA_BASE_URL=http://host.docker.internal:11434
```

然后执行：

```bash
docker compose up -d --build
```

| 场景 | 是否需要再 pull |
|------|-----------------|
| 默认配置、容器内首次使用 | 需要 |
| 同一 Docker 数据卷再次启动 | 不需要 |
| 已挂载本机 `\.ollama` 且本机已有模型 | 一般不需要 |
| 后端直连本机 Ollama 服务 | 不需要 |

---

## 本地开发启动

适用于需要修改源码、热更新的开发场景。

### 1. 准备依赖服务

- 启动 MySQL 8，创建库（可选执行 `init_db.sql`）  
- 启动 Redis（可选；未启动时部分缓存降级）  
- 安装并启动 [Ollama](https://ollama.com/)，执行：

```bash
ollama pull qwen2.5:latest
ollama pull embeddinggemma:latest
```

### 2. 配置环境变量

```bash
# Linux / macOS
cp .env.example .env

# Windows
copy .env.example .env
```

按本机环境编辑 `.env` 中的 `MYSQL_*`、`REDIS_*`、`OLLAMA_BASE_URL` 等。

### 3. 启动后端

```bash
pip install -r backend/requirements.txt
python main.py
```

默认 API：`http://127.0.0.1:8000`（可通过 `SERVER_PORT` 修改）。  
本仓库 Windows 脚本常用 **8010** 端口，见 `start_all.bat`。

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

开发地址一般为 `http://127.0.0.1:5173`。  
若后端端口不是 `8010`，可设置：

```bash
# PowerShell 示例
$env:VITE_API_TARGET="http://127.0.0.1:8000"
npm run dev
```

### Windows 一键（开发模式）

在已安装 Python、Node、MySQL、Redis、Ollama 的前提下，可双击 **`start_all.bat`** 启动后端（8010）与前端（5173）。

---

## 默认账号与访问地址

### Docker 部署

| 项目 | 地址 |
|------|------|
| Web 前端 | http://localhost:8080 |
| API 文档 | http://localhost:8080/docs |

### 本地开发

| 项目 | 地址 |
|------|------|
| Web 前端 | http://127.0.0.1:5173 |
| API | http://127.0.0.1:8000 或 8010 |
| API 文档 | http://127.0.0.1:8000/docs |

### 演示账号

| 角色 | 用户名 | 密码 | 权限摘要 |
|------|--------|------|----------|
| 管理员 | admin | admin123 | 全部功能 + 知识库 / RAG / 用户管理 |
| 普通用户 | user | user123 | 对话、看板、工作台、多智能体、帮助中心、安全管理 |

登录密码在传输过程中使用 **RSA-OAEP（SHA-256）** 加密，不以明文提交。

---

## 使用说明

### 普通用户

1. 使用 `user` 账号登录  
2. **智能对话**：输入问题；可勾选「启用知识库检索」；可选填写关注标的代码（鼠标悬停「?」查看说明）  
3. **数据看板**：输入股票代码或名称（如 `600519` / `茅台`）查看 K 线  
4. **内容工作台 / 多智能体**：按页面提示生成或协同分析  
5. **安全管理**：修改本人登录密码  

### 管理员

在普通用户能力基础上：

1. **知识库管理**：上传/导入文档，启用或停用，删除文档  
2. **RAG 参数**：配置切分策略（句子 / 段落 / Markdown / 固定长度 / 自定义）、块大小与阈值  
3. **知识库状态**：查看向量索引与嵌入服务是否可用  
4. **系统管理**：监控数据库 / Redis / Ollama 状态；管理用户与重置任意账号密码；**导入数据目录至知识库**；重建演示数据  
5. **数据看板**：可同步公开数据源入库  

### 知识库资料导入

1. 将 `.md` / `.txt` / `.csv` / `.pdf` 等文件放入 `data/kb_docs/` 或 `data/uploads/`（Docker 下对应容器内数据卷，也可通过管理端上传）  
2. 使用管理员登录 → **系统管理** → **导入数据目录至知识库**  
3. 系统会扫描 `data/` 下可识别文档，并自动跳过向量库、数据库等运行时文件  

---

## 配置说明

### Docker 可选环境变量

复制 `.env.docker.example` 为 `.env` 后按需修改（不配置则使用默认值）：

| 变量 | 含义 | 默认示例 |
|------|------|----------|
| `WEB_PORT` | 浏览器访问端口 | `8080` |
| `MYSQL_USER` / `MYSQL_PASSWORD` | 应用数据库账号 | `fras` / `fras123` |
| `JWT_SECRET` | JWT 签名密钥 | 请改为随机长字符串 |
| `ADMIN_PASSWORD` / `USER_PASSWORD` | 初始账号密码 | 见演示账号 |
| `LLM_MODEL` | 对话模型 | `qwen2.5:latest` |
| `EMBEDDING_MODEL` | 嵌入模型 | `embeddinggemma:latest` |
| `OLLAMA_MODELS_DIR` | 挂载本机模型目录 | 不设置则用 Docker 卷 |
| `OLLAMA_BASE_URL` | Ollama 服务地址 | 容器内 `http://ollama:11434` |

修改端口示例：

```bash
# Linux / macOS
WEB_PORT=9000 docker compose up -d

# Windows PowerShell
$env:WEB_PORT=9000; docker compose up -d
```

### 本地开发 `.env`

以 `.env.example` 为模板，常用项：

| 变量 | 说明 |
|------|------|
| `USE_SQLITE` | `true` 时使用 SQLite，无需 MySQL |
| `MYSQL_HOST` / `MYSQL_PORT` / `MYSQL_USER` / `MYSQL_PASSWORD` | 数据库连接 |
| `REDIS_HOST` / `REDIS_PORT` | Redis 连接 |
| `OLLAMA_BASE_URL` | 本机 Ollama，默认 `http://127.0.0.1:11434` |
| `SERVER_PORT` | 后端端口，默认 `8000` |
| `JWT_SECRET` | 务必修改后再上线 |

---

## 项目结构

```text
.
├── backend/                  # FastAPI 后端与业务逻辑
│   ├── main.py               # API 入口
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 # Vue 3 前端
│   ├── Dockerfile
│   ├── nginx.conf            # 生产环境反向代理 /api
│   └── src/
├── data/                     # 运行时数据（上传、向量索引、待导入文档）
├── docker-compose.yml        # 完整部署（MySQL + Redis + Ollama + 前后端）
├── docker-compose.lite.yml   # 精简部署
├── docker-start.bat          # Windows Docker 一键启动
├── docker-stop.bat           # Windows Docker 停止
├── start_all.bat             # Windows 本地开发一键启动
├── stop_all.bat
├── init_db.sql               # MySQL 表结构初始化
├── main.py                   # 本地后端启动入口
├── .env.example              # 本地开发环境变量模板
├── .env.docker.example       # Docker 环境变量模板
└── README.md
```

---

## 常见问题

### 1. 打开 http://localhost:8080 无法访问

- 确认 Docker Desktop 正在运行  
- 执行 `docker compose ps`，确认 `frontend` / `backend` 为 healthy 或 running  
- 查看日志：`docker compose logs -f frontend backend`  
- 检查 8080 端口是否被占用，或修改 `WEB_PORT`  

### 2. 能打开页面，但对话很慢或失败

- 确认模型已拉取：`docker compose exec ollama ollama list`  
- 无 GPU 时 CPU 推理可能较慢（数十秒属正常）  
- 内存不足时请关闭其他应用，或改用精简版 compose  

### 3. 知识库检索无结果

- 管理员是否已导入文档或同步数据  
- **RAG 参数** 中是否已启用 RAG  
- Ollama 嵌入模型是否可用（`embeddinggemma:latest`）  

### 4. 登录提示加密相关错误

- 使用现代浏览器（支持 Web Crypto）  
- 确保后端 `/api/auth/public-key` 可访问  
- 不要使用旧版仅提交明文密码的第三方客户端  

### 5. 本机已有模型，Docker 仍在下载

- 未配置 `OLLAMA_MODELS_DIR` 时，容器与本机模型隔离，属预期行为  
- 按上文「本机已有 Ollama 模型时」配置 `.env` 后重启  

### 6. Windows 路径含中文导致 Docker 异常

- 建议将项目放在纯英文路径下再执行 `docker compose`  
- 或仅使用已安装的 Docker Desktop 最新版并开启足够磁盘权限  

---

## 测试

```bash
cd backend
pip install -r requirements.txt
pytest -q tests/test_core.py
```

---

## 免责声明

- 本项目仅供 **学习、研究与演示**，不构成任何投资建议或承诺。  
- 行情与公开信息来自第三方接口，时效与准确性以源站为准。  
- 大模型输出可能存在幻觉或偏差，重要决策请结合专业研究与人工复核。  
- 使用前请遵守所在地区关于数据使用、金融信息与开源软件的相关规定。  

---

## 许可证

未单独声明许可证时，默认仅供学习交流；二次分发或商用请自行确认依赖组件协议并获得相应授权。
