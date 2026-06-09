# 无计划作业智能检查平台

无计划作业智能检查平台团队开发代码，包含 React 前端、FastAPI 后端、作业票解析、检查流程、系统交互和违规检测原型。

## 目录

| 目录 | 说明 |
|---|---|
| `backend` | 后端 API、作业票解析、数据库访问、智能体流程 |
| `frontend` | React 前端页面和 API 封装 |

## 敏感信息与数据

仓库不包含真实作业票、现场图片、日志、数据库账号密码、API Key 或本机绝对路径。运行时请在本地创建 `.env` 并填写数据库和模型服务配置。

## 本地运行

后端：

```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5757
```
