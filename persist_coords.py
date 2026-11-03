# -*- coding: utf-8 -*-
"""坐标固化脚本：把 qiongyou.db 中已回填的 price_lib 坐标写回 data.sql。

配合 backfill_coords.py 使用，形成「回填 → 固化」闭环：
    python backfill_coords.py      # 先回填坐标到 qiongyou.db
    python persist_coords.py       # 再把坐标写回 data.sql

这样之后重跑 init_db.py（从 data.sql 重建库）时坐标不会丢失。

说明：仅重写 data.sql 中的 price_lib 块；city_config 块及其余内容原样保留。
      仍未回填到坐标的条目保持 NULL，可再次回填后重复执行本脚本覆盖。
"""
import os
import sqlite3

from config import Config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.sql")

def _lit(value):
    """SQL 字面量：None → NULL；float 坐标保留最短往返精度；其余按原格式。"""
    if value is None:
        return "NULL"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    return "'{}'".format(str(value).replace("'", "''"))


def _fmt_price(value):
    """价格保持 2 位小数（与 data.sql 原格式一致）。"""
    if value is None:
        return "NULL"
    return "{:.2f}".format(value)


def build_price_lib_block(conn):
    """从库中读取全部 price_lib 行，生成新的 INSERT 块（INSERT + 各行数据）。"""
    rows = conn.execute(
        "SELECT city, name, type, price, lat, lng, open_hours, source "
        "FROM price_lib ORDER BY id"
    ).fetchall()
    lines = ["INSERT INTO price_lib (city, name, type, price, lat, lng, open_hours, source) VALUES"]
    for i, r in enumerate(rows):
        cols = (
            _lit(r["city"]),
            _lit(r["name"]),
            _lit(r["type"]),
            _fmt_price(r["price"]),
            _lit(r["lat"]),
            _lit(r["lng"]),
            _lit(r["open_hours"]),
            _lit(r["source"]),
        )
        suffix = "," if i < len(rows) - 1 else ";"
        lines.append("  ({}){}".format(", ".join(cols), suffix))
    return "\n".join(lines) + "\n"


def main():
    if not os.path.exists(Config.DATABASE):
        print(f"未找到数据库 {Config.DATABASE}，请先运行：python init_db.py && python backfill_coords.py")
        return

    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    block = build_price_lib_block(conn)
    total = conn.execute("SELECT COUNT(*) c FROM price_lib").fetchone()["c"]
    done = conn.execute(
        "SELECT COUNT(*) c FROM price_lib WHERE lat IS NOT NULL AND lng IS NOT NULL"
    ).fetchone()["c"]
    conn.close()

    with open(DATA_FILE, encoding="utf-8") as f:
        lines = f.read().split("\n")

    # 找到 price_lib 的 INSERT 行，保留其之前的内容（含 city_config 块、空行、注释行）
    insert_idx = next(i for i, ln in enumerate(lines) if ln.strip().startswith("INSERT INTO price_lib"))
    new_content = "\n".join(lines[:insert_idx]) + "\n" + block

    with open(DATA_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)

    print(f"已固化坐标到 data.sql：共 {total} 条，含坐标 {done} 条，缺失 {total - done} 条")


if __name__ == "__main__":
    main()
