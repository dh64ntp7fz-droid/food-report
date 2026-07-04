# 湘阁里辣 · 新鲜食材菜品推荐系统（门店临期食材每日上报）

> **生产地址**：https://food-report.onrender.com
> **前端上报页**：`/` | **后台管理**：`/admin`
> **项目仓库**：https://github.com/dh64ntp7fz-droid/food-report
> **技术栈**：FastAPI (Python) + Supabase (PostgreSQL) + Render + 企业微信机器人

---

## 目录

1. [系统概述](#1-系统概述)
2. [全链路架构](#2-全链路架构)
3. [部署指南](#3-部署指南)
4. [数据库设计](#4-数据库设计)
5. [API 参考](#5-api-参考)
6. [定时检查与推送机制](#6-定时检查与推送机制)
7. [前端说明](#7-前端说明)
8. [已知问题与修复历史](#8-已知问题与修复历史)
9. [运维手册](#9-运维手册)

---

## 1. 系统概述

### 1.1 业务场景

湘阁里辣 5 家门店的厨师长每天两次（早 10:00 / 晚 17:00）上报当日新鲜食材及推荐菜品数量，系统自动生成推送文案并发送到对应门店的微信群，提醒顾客关注当日新鲜食材。

### 1.2 核心流程

```
厨师长 → 浏览器/手机打开上报页
       → 选择自己门店
       → 填写各菜品推荐份数
       → 提交
       → 系统生成文案 → 推送到该门店企微群
                         同时存入 Supabase 历史记录
       （如到点未提交 → 定时检查发现 → 推漏报告警到门店群）
```

### 1.3 5 家门店

| ID | 门店名 | 菜品数 | 企微 Webhook |
|:--:|:------|:-----:|:------------|
| 1 | 凤岗黄河店 | 8 | `key=7abf8ef0-...` |
| 2 | 大朗环球店 | 9 | `key=cbac48c7-...` |
| 3 | 凤岗天安数码城店 | 11 | `key=2c774eee-...` |
| 4 | 长安锦厦店 | 10 | `key=397b64a5-...` |
| 5 | 长安花园店 | 11 | `key=1e08dacd-...` |

---

## 2. 全链路架构

### 2.1 系统架构图

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  浏览器前端   │────▶│  FastAPI 后端     │────▶│  Supabase    │
│  index.html  │     │  main.py         │     │  PostgreSQL  │
│  admin.html  │     │  uvicorn 运行    │     │  5 张表      │
└──────────────┘     └────────┬─────────┘     └──────────────┘
                              │
                              ▼
                     ┌──────────────────────┐
                     │  企业微信机器人       │
                     │  Webhook API         │
                     └──────────┬───────────┘
                                ▼
                     ┌──────────────────────┐
                     │  门店微信群           │
                     │  （每店一个群）       │
                     └──────────────────────┘
```

### 2.2 外部依赖

| 组件 | 用途 | 访问方式 |
|:----|:----|:--------|
| **Supabase** | 数据存储 | REST API（service_role key） |
| **Render** | 服务托管 | GitHub 自动部署 |
| **企业微信机器人** | 消息推送 | Webhook（每个门店一个独立 Key） |
| **UptimeRobot** | 服务保活（防 Free Tier 休眠） | 每 5 分钟 ping `/health` |

### 2.3 部署拓扑

```
Render (oregon)
  └─ food-report (Python / uvicorn)
       ├─ SUPABASE_URL → https://ieidvazvzulsrfopjvyf.supabase.co
       ├─ SUPABASE_KEY → <service_role key>
       └─ RENDER = "true"
```

**注意**：`food-report` 和 `room-reservation`、`queue-system` 是**不同的 Render 账号**，部署信息不共享。

---

## 3. 部署指南

### 3.1 Supabase 初始化

1. 打开 https://supabase.com → GitHub 登录 → 进入项目 `ieidvazvzulsrfopjvyf`
2. **SQL Editor** → 运行 `supabase_setup.sql`
3. **Project Settings → API** 找到两个 key：
   - `URL` → 给 `SUPABASE_URL`
   - `service_role key` → 给 `SUPABASE_KEY`（⚠️ 不是 anon public key，是 service_role）

### 3.2 Render 部署

#### 方式一：一键部署（推荐）

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

#### 方式二：手动

1. Fork 仓库到自己的 GitHub
2. Render Dashboard → New Web Service → 连接仓库
3. 配置：

| 配置项 | 值 |
|:------|:---|
| Name | `food-report` |
| Runtime | `Python` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port 10000` |
| Plan | **Starter**（Free 够用） |

4. 环境变量：

| 变量 | 值 |
|:----|:---|
| `SUPABASE_URL` | Supabase Project URL |
| `SUPABASE_KEY` | Supabase **service_role** key |
| `RENDER` | `true` |
| `SECRET_CODE` | （可选，修改暗号，默认"无敌小帅"） |

### 3.3 UptimeRobot 保活（必配）

> **⚠️ Render Free 计划 15 分钟无请求就会休眠。没有保活 → scheduler 不跑 → 定时检查失效。**

1. 打开 https://uptimerobot.com → 添加 monitor
2. 配置：

| 配置项 | 值 |
|:------|:---|
| Monitor Type | HTTP(s) |
| URL | `https://food-report.onrender.com/health` |
| Interval | **5 minutes** |

> 当前已有一个 5 分钟监测在运行。如果换人接手，确认该 monitor 还活着。

---

## 4. 数据库设计

### 4.1 表结构（5 张表）

#### `food_stores` — 门店

| 字段 | 类型 | 说明 |
|:----|:----|:----|
| id | BIGINT PK | 自动生成 |
| name | TEXT | 门店名 |
| sort_order | INT | 排序 |
| created_at | TIMESTAMPTZ | 创建时间 |

#### `food_menu_items` — 菜品

| 字段 | 类型 | 说明 |
|:----|:----|:----|
| id | BIGINT PK | 自动生成 |
| store_id | BIGINT FK | 所属门店 |
| name | TEXT | 菜品名 |
| unit | TEXT | 单位（份/斤/条） |
| sort_order | INT | 排序 |
| created_at | TIMESTAMPTZ | |

#### `food_reports` — 上报记录

| 字段 | 类型 | 说明 |
|:----|:----|:----|
| id | BIGINT PK | 自动生成 |
| store_id | BIGINT | 门店 ID |
| store_name | TEXT | 门店名 |
| time_slot | TEXT | `morning` 或 `noon` |
| slot_label | TEXT | `早10:00` 或 `晚17:00` |
| data | JSONB | `{"菜品名": 数量}` |
| items_detail | JSONB | `[{"name","unit","value"}]` |
| raw_text | TEXT | 推送到群的完整文案 |
| report_date | DATE | 上报日期 |
| pushed | BOOLEAN | 是否推送成功 |
| push_status | TEXT | `pending` / `success` / `failed` |
| created_at | TIMESTAMPTZ | 创建时间 |

#### `food_webhook_config` — Webhook 配置

| 字段 | 类型 | 说明 |
|:----|:----|:----|
| id | BIGINT PK | |
| store_id | BIGINT FK UNIQUE | 每家门店一条 |
| webhook_url | TEXT | 企微机器人 URL |
| created_at / updated_at | TIMESTAMPTZ | |

#### `food_system_config` — 系统配置

| 字段 | 类型 | 说明 |
|:----|:----|:----|
| id | BIGINT PK | |
| key | TEXT UNIQUE | 配置键名 |
| value | TEXT | 配置值 |
| updated_at | TIMESTAMPTZ | |

当前只有一条配置：`alert_webhook_url` — 漏报告警汇总推送地址。

### 4.2 安全策略

所有表开启 RLS（Row Level Security），并创建了 `anon_all_access` 策略，让后端通过 anon key 也能读写。

---

## 5. API 参考

### 5.1 公共端点

| 方法 | 路径 | 说明 |
|:----|:----|:-----|
| GET | `/health` | 健康检查 → `{"status":"ok","service":"food-report"}` |
| GET | `/` | 前端上报页 |
| GET | `/admin` | 后台管理页 |
| GET | `/api/stores` | 门店列表（含菜品） |
| GET | `/api/stores/{id}/menu` | 某店菜品列表 |
| POST | `/api/report` | 提交上报 |
| GET | `/api/reports` | 查询历史记录 |
| GET | `/api/webhook-config` | Webhook 配置查询 |
| PUT | `/api/stores/{id}` | 更新门店排序 |

### 5.2 受保护端点（需暗号）

| 方法 | 路径 | 说明 |
|:----|:----|:-----|
| POST | `/api/webhook-config` | 更新 Webhook URL |
| GET/PUT | `/api/system-config` | 系统配置（告警 Webhook） |
| POST | `/api/menu` | 新增菜品 |
| PUT/DELETE | `/api/menu/{id}` | 编辑/删除菜品 |

暗号验证方式：请求体传 `{"secret": "无敌小帅"}` 或 Header `X-Secret: 无敌小帅`。

### 5.3 提交上报示例

```bash
curl -X POST https://food-report.onrender.com/api/report \
  -H "Content-Type: application/json" \
  -d '{
    "store_id": 2,
    "slot_label": "早10:00",
    "items": [
      {"name": "手撕土鸡", "unit": "份", "value": 5},
      {"name": "老鸭汤", "unit": "份", "value": 1}
    ]
  }'
```

返回：
```json
{
  "success": true,
  "report_id": 75,
  "pushed": true,
  "raw_text": "【湘阁里辣 · 新鲜食材 · 今日推荐】\n手撕土鸡：5份\n老鸭汤：1份\n上报时间：2026-07-04 10:52\n @所有人"
}
```

### 5.4 查询历史示例

```bash
# 查某店某天的记录
curl "https://food-report.onrender.com/api/reports?store_id=2&date=2026-07-04&limit=10"
```

---

## 6. 定时检查与推送机制

### 6.1 定时检查逻辑

```
scheduler_loop()
  └─ 每 60 秒调用一次 check_missed_reports()
       └─ 检查当前时间是否在检查窗口内：
            早: 10:05 ~ 10:20（含）
            晚: 17:05 ~ 17:20（含）
          └─ 窗口内首次命中 →
               查当天已提交记录 →
               找到未提交的门店 →
               推送到该门店 Webhook
```

### 6.2 开机补查（2026-07-04 新增）

```
startup()
  ├─ scheduler_loop()  ← 常驻循环
  └─ _startup_catchup()  ← 5 秒后执行一次
       └─ check_missed_reports(catchup=True)
            └─ 检查所有"已到时间但还没超过窗口"的时段
                例如 10:08 重启 → 补查 10:05 窗口
```

### 6.3 防重复推送

每个 `(日期, 时段)` 组合全局只推送一次，记录在内存字典 `_done_checks` 中。服务重启后重置（允许再次推送）。

### 6.4 推送文案格式

```
【湘阁里辣 · 新鲜食材 · 今日推荐】
<菜品名>：<数量>份
<菜品名>：<数量>份
...
上报时间：2026-07-04 10:52
 @所有人
```

### 6.5 漏报告警文案

```
⚠️ <门店名> <时段> 新鲜食材尚未上报，
请尽快填写！
```

---

## 7. 前端说明

### 7.1 上报页（`/`）

`static/index.html` — 厨师长每天使用的页面：
- 下拉选门店 → 加载该店菜品 → 加减数量 → 提交
- 自动判断时段（13:00 前 = 早10:00，之后 = 晚17:00）
- 提交后显示完整的推送文案

### 7.2 管理页（`/admin`）

`static/admin.html` — 管理员使用，四个选项卡：
- **📋 菜品管理** — 每家店独立维护菜品名称/单位/排序
- **🔗 Webhook** — 配置各门店企微机器人 URL
- **📊 历史记录** — 按门店/日期查询上报历史
- **🔔 告警设置** — 配置漏报告警的推送地址

修改 Webhook 和告警设置需要暗号验证（默认：`无敌小帅`）。

---

## 8. 已知问题与修复历史

### 8.1 🔴 已修复：严格分钟匹配导致漏报检查跳过（2026-07-04）

**根因**：原代码 `current_minutes != check_minutes`，scheduler 循环抖动几秒到 xx:06 就永久错过当天检查窗口。

**修复**：放宽到 15 分钟窗口（10:05~10:20 / 17:05~17:20），加上开机补查机制。

**涉及文件**：`main.py` 的 `check_missed_reports()` 和 `_startup_catchup()`。

### 8.2 🔴 已修复：开机不补查（2026-07-04）

**根因**：`catchup=True` 功能写了但从未被调用。

**修复**：`startup()` 启动后 5 秒自动执行补查。

### 8.3 🟡 已清理：开机补查重复调用（2026-07-04）

**根因**：`_startup_catchup()` 中 `check_missed_reports(catchup=True)` 被写了两遍，第二次还多包了一层 `try/except`。

**修复**：合并为单次调用。

### 8.4 🟢 潜在风险：Supabase service_role key 泄露

**说明**：代码第 29 行 `SUPABASE_KEY` 默认值是截断的占位符，实际值在 Render 环境变量中。如果有人 fork 仓库，需要自行配置环境变量。

### 8.5 🟢 潜在风险：Free Tier 休眠

**说明**：Render Free Plan 15 分钟无请求即休眠。定时检查在休眠期间不执行。必须配合 UptimeRobot 5 分钟保活。如果更换 UptimeRobot 账号或删除 monitor，需重新配置。

---

## 9. 运维手册

### 9.1 每日检查

```bash
# 1. 检查服务是否活着
curl https://food-report.onrender.com/health

# 2. 查看今天上报情况
curl "https://food-report.onrender.com/api/reports?date=$(date +%F)&limit=20"

# 3. 手动触发提交（模拟某店上报）
curl -X POST https://food-report.onrender.com/api/report \
  -H "Content-Type: application/json" \
  -d '{"store_id": 2, "slot_label": "早10:00", "items": [{"name":"手撕土鸡","unit":"份","value":3}]}'

# 4. 向某店群手动推送提醒（慎用！会被群成员看到）
# curl -X POST https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=XXXXX \
#   -H "Content-Type: application/json" \
#   -d '{"msgtype":"text","text":{"content":"⚠️ 提醒消息"}}'
```

### 9.2 更新菜品

浏览器打开 `https://food-report.onrender.com/admin` → 菜品管理 → 找到对应门店 → 增删改。

### 9.3 更新 Webhook

浏览器打开 `https://food-report.onrender.com/admin` → Webhook 标签 → 修改 → 保存（需暗号）。

如果 Webhook 失效（企微机器人被踢出群）：
1. 在企微群 → 群设置 → 群机器人 → 重新生成 Webhook URL
2. 到管理页更新

### 9.4 查看日志

Render Dashboard → food-report → Logs → 搜索关键词：
- `检查漏报` — 查看定时检查是否运行
- `推漏报告警` — 查看哪些门店被推送
- `启动补查` — 查看开机补查是否执行
- `Supabase.*失败` — 查看数据库问题

### 9.5 部署更新

```bash
git add -A
git commit -m "fix: 说明改动内容"
git push origin main
```

Render 自动检测到 push 后部署（约 1-2 分钟）。部署后 5 秒会自动补查今天的漏报。

### 9.6 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
export SUPABASE_URL=https://ieidvazvzulsrfopjvyf.supabase.co
export SUPABASE_KEY=<service_role key>

# 启动
uvicorn main:app --host 0.0.0.0 --port 3458 --reload
```

### 9.7 关键环境变量

| 变量 | 当前值 | 来源 |
|:----|:------|:----|
| `SUPABASE_URL` | `https://ieidvazvzulsrfopjvyf.supabase.co` | Supabase Project Settings → API |
| `SUPABASE_KEY` | （Render 环境变量中） | Supabase → service_role key |
| `RENDER` | `true` | 手动设置 |
| `SECRET_CODE` | `无敌小帅`（代码默认值） | 可选覆盖 |

### 9.8 关键 URL 汇总

| 名称 | URL |
|:----|:----|
| 上报系统 | https://food-report.onrender.com |
| Supabase 控制台 | https://supabase.com → 项目 `ieidvazvzulsrfopjvyf` |
| GitHub 仓库 | https://github.com/dh64ntp7fz-droid/food-report |
| UptimeRobot | https://uptimerobot.com → food-report monitor |
| 企微告警 Webhook | `d35ec9fd-b3e2-4132-848c-0fbc7ab38107`（系统配置中） |

---

> **最后更新**：2026-07-04
> **维护人**：Johnny
> **备份**：本文件与 `supabase_setup.sql` 一起提交到 Git，即使服务挂掉也能从 SQL 重建
