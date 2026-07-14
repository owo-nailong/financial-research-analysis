# 金融研报智能分析与投资决策辅助系统

FastAPI + Vue 3 + MySQL 8 + Redis + Ollama（RAG / Agent）

## 环境要求

- Python 3.10+
- Node.js 18+
- MySQL 8.x（也可用 `USE_SQLITE=true` 快速试用）
- Redis（可选，未启动时部分缓存降级）
- [Ollama](https://ollama.com/)：`qwen2.5:latest`、`embeddinggemma:latest`

## 快速启动

### 1. 配置

```bash
# 复制环境模板（不要提交真实 .env）
cp .env.example .env
# Windows: copy .env.example .env
```

按本机修改 `.env` 中的 MySQL / Redis / Ollama 地址与密码。  
**所有路径默认为项目相对路径**（`data/`、`data/vector_store/`），无需填写本机绝对路径。

### 2. 后端

```bash
pip install -r backend/requirements.txt

# 初始化数据库表（可选：执行 init_db.sql）
# MySQL: mysql -u root -p < init_db.sql

# 启动 API（默认监听 0.0.0.0:8000；本仓库常用 8010）
python main.py
# 或：
# cd backend && uvicorn main:app --host 127.0.0.1 --port 8010
```

Windows 也可双击根目录 **`start_all.bat`**（同时起后端 8010 + 前端 5173）。

### 3. 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开控制台提示的地址（一般为 `http://127.0.0.1:5173`）。  
前端通过 Vite 代理访问后端；若后端端口不是 8010，可设置环境变量：

```bash
# Windows PowerShell
$env:VITE_API_TARGET="http://127.0.0.1:8000"
npm run dev
```

### 4. Ollama

```bash
ollama pull qwen2.5:latest
ollama pull embeddinggemma:latest
```

## 默认账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 普通用户 | user | user123 |

登录密码经 **RSA-OAEP** 加密传输，不会明文提交。  
上线请务必修改 `.env` 中的 `JWT_SECRET` 与默认密码。

## 目录说明

```
.
├── backend/          # FastAPI 后端
├── frontend/         # Vue 前端
├── data/             # 运行时数据（上传、向量库，gitignore）
├── docs/             # 可选：放入参考文档后可一键导入知识库
├── init_db.sql       # MySQL 表结构
├── main.py           # 启动入口
├── start_all.bat     # Windows 一键启动
└── .env.example      # 环境变量模板
```

## 知识库文档导入

- **管理端上传**：知识库管理 → 批量导入（推荐）
- **项目内文档**：把 `.md`/`.txt` 放到 `docs/`，管理员在「系统管理」点击「导入项目文档到知识库」  
  默认还会导入根目录 `README.md`。**不依赖任何本机绝对路径。**

## 测试

```bash
cd backend
pytest -q tests/test_core.py
```

## 功能概览

1. 多源聚合：研报 / 新闻 / 公告 / 舆情  
2. 结构化提取与观点对比  
3. 智能对话 + RAG  
4. 数据看板（K 线）  
5. 内容工作台 / 多智能体  
6. 角色权限：管理员（知识库、RAG、用户）/ 普通用户（对话与业务页 + 安全管理改密）
