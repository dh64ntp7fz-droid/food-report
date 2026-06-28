# 门店临期食材每日上报系统

湘阁里辣 5 家门店临期食材每日自动上报系统。

## 功能

- 厨师长选门店 + 时段 → 填数字 → 自动生成文案 → 推微信群机器人
- 每店独立菜品库，后台可编辑
- 10:00 / 12:00 漏报自动提醒
- 历史记录查询

## 技术栈

- **后端**: FastAPI (Python)
- **数据库**: Supabase (PostgreSQL)
- **部署**: Render

## 部署

### 1. Supabase 建表

在 Supabase Dashboard → SQL Editor 运行 `supabase_setup.sql`

### 2. 环境变量

在 Render Dashboard 设置：

| 变量 | 值 |
|------|-----|
| `SUPABASE_URL` | `https://ieidvazvzulsrfopjvyf.supabase.co` |
| `SUPABASE_KEY` | Supabase → Settings → API → service_role key |
| `RENDER` | `true` |

### 3. 一键部署

点击： [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

或手动：New Web Service → 连接 GitHub 仓库 → 选 `food-report` 分支 main

## 本地开发

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 3458
```
