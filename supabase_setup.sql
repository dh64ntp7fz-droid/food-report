-- ============================================================
-- 门店临期食材每日上报系统 · Supabase 建表脚本
-- 在 Supabase Dashboard → SQL Editor 运行
-- ============================================================

-- 1. 门店表
CREATE TABLE IF NOT EXISTS food_stores (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  name TEXT NOT NULL,
  sort_order INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. 菜品表
CREATE TABLE IF NOT EXISTS food_menu_items (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  store_id BIGINT NOT NULL REFERENCES food_stores(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  unit TEXT NOT NULL,
  sort_order INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 上报记录表
CREATE TABLE IF NOT EXISTS food_reports (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  store_id BIGINT NOT NULL,
  store_name TEXT NOT NULL,
  time_slot TEXT NOT NULL,       -- 'morning' | 'noon'
  slot_label TEXT NOT NULL,      -- '早10:00' | '午12:00'
  data JSONB NOT NULL,           -- {"菜品名": 数量, ...}
  items_detail JSONB NOT NULL,   -- [{"name":"...","unit":"...","value":N}, ...]
  raw_text TEXT NOT NULL,        -- 自动生成的群消息文案
  report_date DATE NOT NULL,
  pushed BOOLEAN DEFAULT FALSE,
  push_status TEXT DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Webhook 配置表
CREATE TABLE IF NOT EXISTS food_webhook_config (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  store_id BIGINT NOT NULL REFERENCES food_stores(id) ON DELETE CASCADE UNIQUE,
  webhook_url TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. 系统配置（告警 Webhook 等）
CREATE TABLE IF NOT EXISTS food_system_config (
  id BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
  key TEXT NOT NULL UNIQUE,
  value TEXT NOT NULL,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_food_reports_store_date ON food_reports(store_id, report_date);
CREATE INDEX IF NOT EXISTS idx_food_reports_date ON food_reports(report_date);
CREATE INDEX IF NOT EXISTS idx_food_menu_items_store ON food_menu_items(store_id);

-- 插入门店数据
INSERT INTO food_stores (name, sort_order) VALUES
  ('凤岗黄河店', 1),
  ('大朗环球店', 2),
  ('凤岗天安数码城店', 3),
  ('长安锦厦店', 4),
  ('长安花园店', 5)
ON CONFLICT DO NOTHING;

-- 插入菜品数据
INSERT INTO food_menu_items (store_id, name, unit, sort_order)
SELECT s.id, m.name, m.unit, m.sort_order
FROM (VALUES
  ('凤岗黄河店', '新鲜青菜', '斤', 1),
  ('凤岗黄河店', '现切鲜牛肉', '份', 2),
  ('凤岗黄河店', '鲜鸭血', '盒', 3),
  ('凤岗黄河店', '现炸酥肉', '份', 4),
  ('凤岗黄河店', '活虾', '斤', 5),
  ('大朗环球店', '本地时蔬', '斤', 1),
  ('大朗环球店', '鲜鱼片', '份', 2),
  ('大朗环球店', '嫩豆腐', '盒', 3),
  ('大朗环球店', '新鲜五花肉', '斤', 4),
  ('凤岗天安数码城店', '生菜', '斤', 1),
  ('凤岗天安数码城店', '鲜鸡杂', '份', 2),
  ('凤岗天安数码城店', '手工丸子', '盒', 3),
  ('长安锦厦店', '油麦菜', '斤', 1),
  ('长安锦厦店', '鲜排骨', '斤', 2),
  ('长安锦厦店', '鲜毛肚', '份', 3),
  ('长安锦厦店', '嫩千张', '盒', 4),
  ('长安花园店', '娃娃菜', '斤', 1),
  ('长安花园店', '新鲜鱼片', '份', 2),
  ('长安花园店', '鲜鸭血', '盒', 3)
) AS m(store_name, name, unit, sort_order)
JOIN food_stores s ON s.name = m.store_name
ON CONFLICT DO NOTHING;

-- 插入 Webhook 配置（空占位，后续在后台填写）
INSERT INTO food_webhook_config (store_id, webhook_url)
SELECT id, '' FROM food_stores
ON CONFLICT DO NOTHING;

-- 插入默认告警 Webhook
INSERT INTO food_system_config (key, value)
VALUES ('alert_webhook_url', 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=d35ec9fd-b3e2-4132-848c-0fbc7ab38107')
ON CONFLICT DO NOTHING;

-- 启用 RLS（安全加固）
ALTER TABLE food_stores ENABLE ROW LEVEL SECURITY;
ALTER TABLE food_menu_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE food_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE food_webhook_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE food_system_config ENABLE ROW LEVEL SECURITY;

-- 允许 service_role 全部访问（我们只用 service_role key）
CREATE POLICY "service_role_all_access" ON food_stores FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_access" ON food_menu_items FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_access" ON food_reports FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_access" ON food_webhook_config FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role_all_access" ON food_system_config FOR ALL TO service_role USING (true) WITH CHECK (true);

-- 允许 anon 只读门店和菜品（前端需要查询）
CREATE POLICY "anon_read_stores" ON food_stores FOR SELECT TO anon USING (true);
CREATE POLICY "anon_read_menu" ON food_menu_items FOR SELECT TO anon USING (true);
CREATE POLICY "anon_insert_report" ON food_reports FOR INSERT TO anon WITH CHECK (true);
