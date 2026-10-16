# shemei-boombase · 内容矩阵管理发布系统

Instagram 帖子文案抓取与企业微信文档写回（MVP）。

- 粘贴 Instagram 帖子链接 → 几秒内抓取原始文案（保留换行、不乱码）
- 同时抓取帖子的图片 / 视频（含多图轮播、Reels），可在线预览、单个下载或一键打包 ZIP 下载
- 文案情绪判断（积极 / 中性 / 消极）、话题标签提取、一键复制
- 一键写回企业微信智能表格，运营同事可在同一行做二次创作
- 简单 JWT 登录校验

技术栈：前端 Vue 3 + Vite + vue-router + axios；后端 FastAPI + PyJWT + httpx + SQLAlchemy + MySQL。

## 目录结构

```
backend/   FastAPI 服务（app/main.py 入口）
frontend/  Vue 3 前端（Vite）
```

## 后端启动

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # 按需修改 SECRET_KEY、APP_USERS、DATABASE_URL、企业微信参数
python run.py                # 或 uvicorn app.main:app --reload --port 8000
```

接口（除登录外均需 `Authorization: Bearer <token>`）：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/login` | 登录，返回 JWT |
| GET | `/api/auth/me` | 当前用户 |
| POST | `/api/posts/extract` | `{ "url": "..." }` 抓取文案、情绪、标签、图片/视频（`media`） |
| GET | `/api/media/proxy` | 图片/视频代理（预览与下载，地址由 extract 返回，带签名，无需 token） |
| POST | `/api/media/zip` | `{ "shortcode": "...", "items": [...] }` 打包下载全部图片/视频 |
| POST | `/api/posts/write-back` | 写回企业微信智能表格并记录历史 |
| GET | `/api/posts/history` | 最近写回记录 |
| GET | `/api/health` | 健康检查（含是否已配置企业微信） |

默认账号来自 `.env` 的 `APP_USERS`（示例：`admin:admin123`）。

## 前端启动

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 ，/api 代理到 http://localhost:8000
npm run build      # 产物在 frontend/dist
```

## 数据库（MySQL）

```sql
CREATE DATABASE boombase DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

在 `backend/.env` 中配置 `DATABASE_URL=mysql+pymysql://用户名:密码@127.0.0.1:3306/boombase?charset=utf8mb4`，服务启动时会自动建表（`history`）。本地没有 MySQL 时可临时改为 `sqlite:///./data.db`。

## 企业微信写回配置

在 `backend/.env` 中填写：

- `WECOM_CORP_ID` / `WECOM_CORP_SECRET`：企业 ID 与自建应用 Secret（应用需有「文档」权限，且智能表格已对应用授权）
- `WECOM_DOCID` / `WECOM_SHEET_ID`：智能表格文档 ID 与子表 ID
- `WECOM_FIELD_*`：智能表格列标题，默认为「帖子链接 / 原始文案 / 作者 / 情绪 / 提交人」，需与表格中的列名一致

未配置时抓取、复制功能正常，写回按钮会提示未配置。

## 说明

- Instagram 抓取顺序：`IG_SESSIONID` 登录态接口（可选）→ `/embed/captioned/` 页面（爬虫 UA）→ 浏览器 UA → 帖子页 `og:description`。
- 遇到「抓取文案失败」多为 Instagram 风控，建议在 `backend/.env` 填 `IG_SESSIONID`：浏览器登录 instagram.com，F12 → Application → Cookies → 复制 `sessionid` 的值。cookie 过期后重新复制即可。
- 服务器无法直连 Instagram 时可配置 `HTTP_PROXY_URL`（图片/视频代理与 ZIP 下载同样走该代理）。
- 图片/视频由后端转发（`/api/media/proxy`），浏览器无需能访问 Instagram CDN；CDN 链接有时效，过期后重新抓取即可。
