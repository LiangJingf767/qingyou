-- 大学生穷游行程规划助手 —— 建表脚本（SQLite）
-- 说明：SQLite 的外键约束需每条连接单独开启，见 db.py / init_db.py 中的 PRAGMA foreign_keys = ON

-- 1. 攻略项目（含约束）
CREATE TABLE IF NOT EXISTS project (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    city         TEXT    NOT NULL,                       -- 目的地城市
    days         INTEGER NOT NULL DEFAULT 1,             -- 游玩天数
    budget       REAL,                                   -- 用户总预算
    people       INTEGER NOT NULL DEFAULT 1,             -- 同行人数（人均/覆盖天数用）
    start_date   TEXT,                                   -- 出发日期（YYYY-MM-DD，闭馆日检测用）
    preferences  TEXT,                                   -- 兴趣偏好，JSON 文本
    cover        TEXT,                                   -- 封面图片相对路径（用户上传）
    plan_tips    TEXT,                                   -- 生成建议（JSON 文本，字符串列表）
    status       TEXT    NOT NULL DEFAULT 'editing',     -- editing / generated / exported
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 2. 攻略条目（景点 / 美食 / 机位 / 住宿）
CREATE TABLE IF NOT EXISTS item (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id   INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    type         TEXT,                                   -- 景点/美食/机位/住宿
    price        REAL,                                   -- 最终采用价
    price_source TEXT,                                   -- 价格来源：用户/价格库/待补充
    lat          REAL,
    lng          REAL,
    open_hours   TEXT,                                   -- 开放时间（含闭馆信息）
    est_duration INTEGER,                                -- 预估游玩分钟
    note         TEXT,                                   -- 条目备注（大模型生成的时间段/游玩提示）
    day          INTEGER,                                -- 所属天
    order_no     INTEGER,                                -- 当天顺序（order 为 SQL 关键字，故用 order_no）
    dropped      INTEGER NOT NULL DEFAULT 0,             -- 用户手动砍单标记（1=已砍，撤销改回 0）
    popularity   INTEGER NOT NULL DEFAULT 1,             -- 热门度（提及次数）
    source_ids   TEXT,                                   -- 关联 note 的 id，逗号分隔
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE
);

-- 3. 原始笔记（条目溯源）
CREATE TABLE IF NOT EXISTS note (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL,
    text        TEXT,
    source      TEXT,                                    -- 小红书/抖音/手动
    created_at  TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE
);

-- 4. 图片（关联条目）
CREATE TABLE IF NOT EXISTS image (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id   INTEGER NOT NULL,
    path      TEXT    NOT NULL,
    caption   TEXT,
    FOREIGN KEY (item_id) REFERENCES item(id) ON DELETE CASCADE
);

-- 5. 预置价格库
CREATE TABLE IF NOT EXISTS price_lib (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    city        TEXT,
    name        TEXT NOT NULL,
    type        TEXT,
    price       REAL,
    lat         REAL,
    lng         REAL,
    open_hours  TEXT,
    source      TEXT                                    -- 数据来源（预置/官方/抓取）
);

-- 6. 城市配置
CREATE TABLE IF NOT EXISTS city_config (
    city         TEXT PRIMARY KEY,                       -- 城市名作为主键
    transit_avg  REAL,                                   -- 日均交通
    hostel_avg   REAL,                                   -- 青旅均价/晚
    meal_avg     REAL                                    -- 日均餐饮
);

-- 7. 预算结果（与项目 1—1，由预算核算服务计算写入）
CREATE TABLE IF NOT EXISTS budget (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id     INTEGER NOT NULL,
    ticket_total   REAL,                                 -- 门票合计
    food_total     REAL,                                 -- 餐饮合计
    traffic_total  REAL,                                 -- 交通合计
    hotel_total    REAL,                                 -- 住宿合计
    total          REAL,                                 -- 总计
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE
);

-- 8. 记账（行程中实际花费）
CREATE TABLE IF NOT EXISTS expense (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  INTEGER NOT NULL,
    category    TEXT,                                    -- 分类：门票/餐饮/交通/住宿/购物/其他
    amount      REAL    NOT NULL,                        -- 金额（>0）
    item_id     INTEGER,                                 -- 可选关联行程条目
    note        TEXT,                                    -- 备注
    spent_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),  -- 记账日期（自动）
    FOREIGN KEY (project_id) REFERENCES project(id) ON DELETE CASCADE,
    FOREIGN KEY (item_id)     REFERENCES item(id)     ON DELETE SET NULL
);

-- 9. 景点评价（用户评分，用于「必去景点」客观推荐）
CREATE TABLE IF NOT EXISTS review (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    attraction_id INTEGER NOT NULL,                      -- price_lib.id
    rating        INTEGER NOT NULL,                      -- 1-5 星
    comment       TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (attraction_id) REFERENCES price_lib(id) ON DELETE CASCADE
);

-- 10. 景点图片（用户上传，关联 price_lib，避免逐条预置图片）
CREATE TABLE IF NOT EXISTS attraction_image (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    attraction_id INTEGER NOT NULL,
    path          TEXT    NOT NULL,                       -- static/uploads/ 下相对路径
    caption       TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (attraction_id) REFERENCES price_lib(id) ON DELETE CASCADE
);
