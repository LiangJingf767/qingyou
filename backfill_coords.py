# -*- coding: utf-8 -*-
"""价格库坐标回填脚本：为 price_lib 中缺失坐标的条目批量地理编码。

用法：
    cd qiongyou && python backfill_coords.py                # 全部城市
    cd qiongyou && python backfill_coords.py 成都            # 仅某城市
    cd qiongyou && python backfill_coords.py --limit 50      # 限量试跑

说明：个人 Key 约 3 QPS，脚本默认每条 sleep 0.12s；日配额有限，分批跑更稳妥。
"""
import os
import sqlite3
import sys

from config import Config
from services.amap_service import backfill_price_lib_coords


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    city = args[0] if args else None
    limit = None
    if "--limit" in sys.argv:
        i = sys.argv.index("--limit")
        limit = int(sys.argv[i + 1])

    # 库必须已存在（通常由 init_db.py 生成）；这里仅兜底提示，不做重建以免误删数据
    if not os.path.exists(Config.DATABASE):
        print(f"未找到数据库 {Config.DATABASE}，请先运行：python init_db.py")
        return

    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    print(f"开始回填坐标 city={city or '全部'} limit={limit or '不限'} ...")
    ok, skip = backfill_price_lib_coords(city=city, limit=limit, db=conn)
    conn.close()
    print(f"完成：成功 {ok} 条，跳过 {skip} 条")


if __name__ == "__main__":
    main()
