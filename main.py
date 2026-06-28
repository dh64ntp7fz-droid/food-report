"""
门店临期食材每日上报系统
FastAPI + Supabase 后端
"""
import os
import json
import asyncio
import logging
from datetime import datetime, date, time
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─── 日志 ───
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("food-report")

# ─── 配置 ───
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ieidvazvzulsrfopjvyf.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbG...qyb0")
API_BASE = f"{SUPABASE_URL}/rest/v1"
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

# 环境判断
IS_RENDER = os.environ.get("RENDER", False)

app = FastAPI(title="湘阁里辣 · 新鲜食材菜品推荐系统")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ══════════════════════════════════════════════════════════
#  辅助函数
# ══════════════════════════════════════════════════════════

def api_get(table: str, params: dict = None) -> list:
    """GET 请求 Supabase"""
    headers = HEADERS.copy()
    headers["Prefer"] = "return=representation"
    url = f"{API_BASE}/{table}"
    r = requests.get(url, headers=headers, params=params or {}, timeout=10)
    if r.status_code >= 400:
        log.error(f"Supabase GET {table} 失败: {r.status_code} {r.text[:200]}")
        raise HTTPException(502, f"数据库查询失败: {r.status_code}")
    return r.json()


def api_post(table: str, data: dict) -> dict:
    """POST 请求 Supabase"""
    headers = HEADERS.copy()
    headers["Prefer"] = "return=representation"
    url = f"{API_BASE}/{table}"
    r = requests.post(url, headers=headers, json=data, timeout=10)
    if r.status_code >= 400:
        log.error(f"Supabase POST {table} 失败: {r.status_code} {r.text[:200]}")
        raise HTTPException(502, f"数据库写入失败: {r.status_code}")
    return r.json()


def api_put(table: str, data: dict, query: str = "") -> dict:
    """PUT/PATCH 请求 Supabase"""
    headers = HEADERS.copy()
    headers["Prefer"] = "return=representation"
    url = f"{API_BASE}/{table}"
    if query:
        url += f"?{query}"
    # Supabase REST uses PATCH for updates
    r = requests.patch(url, headers=headers, json=data, timeout=10)
    if r.status_code >= 400:
        log.error(f"Supabase PATCH {table} 失败: {r.status_code} {r.text[:200]}")
        raise HTTPException(502, f"数据库更新失败: {r.status_code}")
    return r.json()


def api_delete(table: str, query: str):
    """DELETE 请求 Supabase"""
    headers = HEADERS.copy()
    url = f"{API_BASE}/{table}?{query}"
    r = requests.delete(url, headers=headers, timeout=10)
    if r.status_code >= 400:
        log.error(f"Supabase DELETE {table} 失败: {r.status_code} {r.text[:200]}")
        raise HTTPException(502, f"数据库删除失败: {r.status_code}")


def push_webhook(url: str, content: str) -> bool:
    """推送消息到企微群机器人"""
    if not url:
        return False
    try:
        payload = {"msgtype": "text", "text": {"content": content}}
        r = requests.post(url, json=payload, timeout=8)
        if r.status_code == 200:
            return True
        log.warning(f"Webhook 推送失败: {r.status_code} {r.text[:100]}")
        return False
    except Exception as e:
        log.error(f"Webhook 异常: {e}")
        return False


def build_report_text(store_name: str, slot_label: str, items: list) -> str:
    """生成标准上报文案"""
    lines = [f"【湘阁里辣 · 新鲜食材 · 菜品推荐】"]
    for item in items:
        lines.append(f"{item['name']}：{item['value']}份")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"上报时间：{now}")
    return "\n".join(lines)


def get_cn_slot() -> str:
    """获取当前时段中文标签"""
    h = datetime.now().hour
    if h < 13:
        return "早10:00"
    return "晚17:00"


def get_en_slot_from_label(label: str) -> str:
    return "morning" if "早" in label else "noon"


# ══════════════════════════════════════════════════════════
#  API 端点
# ══════════════════════════════════════════════════════════

@app.get("/api/stores")
def list_stores():
    """获取门店列表（附带菜品数量）"""
    stores = api_get("food_stores", {"order": "sort_order.asc"})
    for s in stores:
        items = api_get("food_menu_items", {
            "store_id": f"eq.{s['id']}",
            "order": "sort_order.asc",
        })
        s["menu_items"] = items
    return stores


@app.get("/api/stores/{store_id}/menu")
def get_menu(store_id: int):
    """获取某店菜品列表"""
    items = api_get("food_menu_items", {
        "store_id": f"eq.{store_id}",
        "order": "sort_order.asc",
    })
    return items


@app.post("/api/report")
def submit_report(data: dict):
    """
    提交上报数据
    请求体: { store_id, store_name, slot_label, items: [{name,unit,value}, ...] }
    """
    store_id = data.get("store_id")
    slot_label = data.get("slot_label")
    items = data.get("items", [])

    if not store_id or not slot_label or not items:
        raise HTTPException(400, "缺少必填字段")

    # 查询门店名称
    stores = api_get("food_stores", {"id": f"eq.{store_id}", "select": "name"})
    store_name = stores[0]["name"] if stores else data.get("store_name", "")

    # 生成文案
    raw_text = build_report_text(store_name, slot_label, items)

    # 构建 data JSON 格式
    data_map = {item["name"]: item["value"] for item in items}

    # 存入数据库
    report_data = {
        "store_id": store_id,
        "store_name": store_name,
        "time_slot": en_slot,
        "slot_label": slot_label,
        "data": json.dumps(data_map),
        "items_detail": json.dumps(items, ensure_ascii=False),
        "raw_text": raw_text,
        "report_date": today,
    }
    result = api_post("food_reports", report_data)
    report_id = result[0]["id"]

    # 推送 Webhook
    webhooks = api_get("food_webhook_config", {"store_id": f"eq.{store_id}"})
    webhook_url = webhooks[0].get("webhook_url", "") if webhooks else ""
    push_ok = push_webhook(webhook_url, raw_text)

    # 更新推送状态
    api_put("food_reports", {
        "pushed": push_ok,
        "push_status": "success" if push_ok else "failed",
    }, f"id=eq.{report_id}")

    return {
        "success": True,
        "report_id": report_id,
        "pushed": push_ok,
        "raw_text": raw_text,
    }


@app.get("/api/reports")
def query_reports(
    store_id: Optional[int] = Query(None),
    date: Optional[str] = Query(None),
    slot: Optional[str] = Query(None),
    limit: int = Query(50),
    offset: int = Query(0),
):
    """查询历史记录"""
    filters = []
    if store_id:
        filters.append(f"store_id=eq.{store_id}")
    if date:
        filters.append(f"report_date=eq.{date}")
    if slot:
        en = "morning" if "早" in slot else "noon"
        filters.append(f"time_slot=eq.{en}")

    params = {
        "order": "created_at.desc",
        "limit": limit,
        "offset": offset,
    }
    if filters:
        params["and"] = ",".join(filters)

    return api_get("food_reports", params)


@app.get("/api/webhook-config")
def get_webhook_config():
    """获取各店 Webhook 配置"""
    configs = api_get("food_webhook_config", {
        "select": "id,store_id,webhook_url",
    })
    # 附加门店名
    stores = {s["id"]: s["name"] for s in api_get("food_stores")}
    for cfg in configs:
        cfg["store_name"] = stores.get(cfg["store_id"], "")
    return configs


@app.post("/api/webhook-config")
def update_webhook_config(data: dict):
    """更新 Webhook 配置"""
    store_id = data.get("store_id")
    webhook_url = data.get("webhook_url", "")
    if not store_id:
        raise HTTPException(400, "缺少 store_id")
    api_put("food_webhook_config", {"webhook_url": webhook_url}, f"store_id=eq.{store_id}")
    return {"success": True}


@app.get("/api/system-config")
def get_system_config():
    """获取系统配置（告警 Webhook）"""
    rows = api_get("food_system_config")
    config = {r["key"]: r["value"] for r in rows}
    return config


@app.put("/api/system-config")
def update_system_config(data: dict):
    """更新系统配置"""
    key = data.get("key")
    value = data.get("value")
    if not key:
        raise HTTPException(400, "缺少 key")
    # upsert
    existing = api_get("food_system_config", {"key": f"eq.{key}"})
    if existing:
        api_put("food_system_config", {"value": value}, f"key=eq.{key}")
    else:
        api_post("food_system_config", {"key": key, "value": value})
    return {"success": True}


@app.post("/api/menu")
def add_menu_item(data: dict):
    """新增菜品"""
    store_id = data.get("store_id")
    name = data.get("name")
    unit = data.get("unit")
    if not all([store_id, name, unit]):
        raise HTTPException(400, "缺少必填字段（store_id, name, unit）")

    # 获取当前最大排序
    items = api_get("food_menu_items", {
        "store_id": f"eq.{store_id}",
        "select": "sort_order",
        "order": "sort_order.desc",
        "limit": 1,
    })
    next_order = (items[0]["sort_order"] + 1) if items else 1

    result = api_post("food_menu_items", {
        "store_id": store_id,
        "name": name,
        "unit": unit,
        "sort_order": next_order,
    })
    return result[0]


@app.put("/api/menu/{item_id}")
def update_menu_item(item_id: int, data: dict):
    """更新菜品"""
    update = {}
    if "name" in data:
        update["name"] = data["name"]
    if "unit" in data:
        update["unit"] = data["unit"]
    if "sort_order" in data:
        update["sort_order"] = data["sort_order"]
    if update:
        api_put("food_menu_items", update, f"id=eq.{item_id}")
    return {"success": True}


@app.delete("/api/menu/{item_id}")
def delete_menu_item(item_id: int):
    """删除菜品"""
    api_delete("food_menu_items", f"id=eq.{item_id}")
    return {"success": True}


@app.get("/health")
def health():
    return {"status": "ok", "service": "food-report"}


# ══════════════════════════════════════════════════════════
#  定时检查：漏报告警
# ══════════════════════════════════════════════════════════

CHECK_TIMES = [
    (10, 5, "早10:00", "morning"),   # 10:05 检查早10点
    (17, 5, "晚17:00", "noon"),      # 17:05 检查晚17点
    (17, 30, "晚17:00", "noon"),     # 17:30 二次提醒
]


async def check_missed_reports():
    """检查是否有门店漏报"""
    try:
        today = date.today().isoformat()
        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute

        for check_h, check_m, slot_label, en_slot in CHECK_TIMES:
            check_minutes = check_h * 60 + check_m
            if current_minutes != check_minutes:
                continue

            log.info(f"🔍 检查漏报: {slot_label}")

            # 获取所有门店
            stores = api_get("food_stores", {"order": "sort_order.asc"})

            # 获取已提交的门店
            submitted = api_get("food_reports", {
                "report_date": f"eq.{today}",
                "time_slot": f"eq.{en_slot}",
                "select": "store_id",
            })
            submitted_ids = {s["store_id"] for s in submitted}

            # 获取告警 Webhook
            alert_url = ""
            configs = api_get("food_system_config", {"key": "eq.alert_webhook_url"})
            if configs:
                alert_url = configs[0].get("value", "")

            if not alert_url:
                log.warning("未配置告警 Webhook，跳过漏报检查")
                return

            # 检查每个门店
            for store in stores:
                sid = store["id"]
                if sid not in submitted_ids:
                    # 获取该门店的webhook
                    webhooks = api_get("food_webhook_config", {"store_id": f"eq.{sid}"})
                    wh_url = webhooks[0].get("webhook_url", "") if webhooks else ""
                    if not wh_url:
                        wh_url = alert_url  # 没有独立webhook时用系统默认
                    if wh_url:
                        msg = (
                            f"⚠️ {store['name']} {slot_label} 新鲜食材尚未上报，\n"
                            f"请尽快填写！"
                        )
                        push_webhook(wh_url, msg)
                        log.info(f"  推漏报告警: {store['name']} {slot_label}")

    except Exception as e:
        log.error(f"漏报检查异常: {e}")


async def scheduler_loop():
    """定时任务循环（每分钟检查一次）"""
    log.info("⏰ 定时检查任务已启动")
    while True:
        try:
            await check_missed_reports()
        except Exception as e:
            log.error(f"scheduler error: {e}")
        await asyncio.sleep(60)


@app.on_event("startup")
async def startup():
    log.info(f"🚀 食材上报系统启动")
    log.info(f"📦 Supabase: {SUPABASE_URL}")
    log.info(f"📋 环境: {'Render' if IS_RENDER else '本地'}")
    asyncio.create_task(scheduler_loop())


# ══════════════════════════════════════════════════════════
#  前端路由
# ══════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
def index():
    path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>上报页面未找到</h1>")


@app.get("/admin", response_class=HTMLResponse)
def admin():
    path = os.path.join(STATIC_DIR, "admin.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>管理页面未找到</h1>")
