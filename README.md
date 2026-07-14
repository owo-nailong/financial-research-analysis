# 金融研报智能分析与投资决策辅助系统

Python / FastAPI + Flask + Vue.js + MySQL 8 + Redis + Ollama (RAG / Agent)

## 环境

- MySQL 8.x（`USE_SQLITE=false`）
- Redis（Docker 示例容器名 `finagent-redis` 或本机 6379）
- Ollama：`qwen2.5:latest`、`embeddinggemma:latest`
- 下载代理（可选）：`HTTP_PROXY=http://127.0.0.1:7897`

## 启动

```bash
# 1) 依赖
pip install -r backend/requirements.txt
# 若较慢：
# set HTTP_PROXY=http://127.0.0.1:7897
# set HTTPS_PROXY=http://127.0.0.1:7897

# 2) 配置 .env（已提供模板 .env.example）

# 3) 种子数据 + 向量索引
python main.py --seed

# 4) 后端 FastAPI
python main.py

# 5) Flask 辅服务（另一终端）
python main.py --flask

# 6) 前端
cd frontend
npm install
npm run dev
```

## 账号

| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 使用者 | user | user123 |

管理员：知识库导入、RAG 参数、用户管理。  
使用者：对话、检索、内容生成。

## 测试

```bash
cd backend
pytest -q tests/test_core.py
```

## 模块

1. 多源聚合：研报 / 新闻 / 公告 / 舆情  
2. 结构化提取：财务、预测、评级、风险  
3. 观点对比与情感  
4. 摘要 / Agent 问答 / RAG  
5. 前端：对话、知识库、工作台、管理后台  
