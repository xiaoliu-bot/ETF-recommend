# -*- coding: utf-8 -*-
# 今日真实数据: 打印每个ETF的趋势环境/回调状态/信号, 不落盘(避免改动index.json)
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
import update

news = update.load_news()
print("今日真实数据 - 趋势环境与上行回调识别:")
for code, name, sector in update.ETF_LIST:
    time.sleep(0.4)
    try:
        _, bars = update.fetch_kline(update.secid(code))
        if len(bars) < 70:
            print(f"  {name:8} bars不足跳过"); continue
        e = update.analyze(code, name, sector, bars, news)
        tag = " <<上行回调加仓/建仓" if (e["trend_env"] == "up" and e["in_pullback"]) else ""
        print(f"  {name:8} env={e['trend_env']:5} pullback={str(e['in_pullback']):5} "
              f"depth={e['pullback_depth']:5} pq={e['pullback_quality']:5} -> {e['signal']}({e['score']}){tag}")
    except Exception as ex:
        print(f"  {name} fail: {ex}")
print("[done]")
