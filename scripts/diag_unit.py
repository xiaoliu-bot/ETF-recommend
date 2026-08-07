# -*- coding: utf-8 -*-
# 单元测试: 用合成K线验证"上行周期回调翻加仓 / 下行反弹不误触发"逻辑, 不依赖外网
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import update


def make_bars(up_trend=True, pullback=True, overheated=False):
    """构造日K: [date, open, close, high, low, volume, amount]
    up_trend=True 前段上涨; pullback=True 末5日上行中回调(下行中则对应反弹)
    overheated=True 上行末段已暴涨(测试过热不追高)"""
    bars, price = [], 1.0
    base_vol = 1000.0
    n = 120
    for d in range(n):
        if up_trend and not overheated:
            drift = 0.004
        elif up_trend and overheated:
            drift = 0.012          # 暴涨已超买
        else:
            drift = -0.004
        if d >= n - 5:
            if pullback and up_trend:
                drift = -0.012     # 上行中回调
            elif (not pullback) and (not up_trend):
                drift = 0.012      # 下行中反弹
        close = price * (1 + drift)
        vol = base_vol * (0.55 if (d >= n - 5 and pullback and up_trend) else 1.0)
        high = max(price, close) * 1.006
        low = min(price, close) * 0.994
        bars.append([f"2026-03-{d+1:02d}", round(price, 3), round(close, 3),
                     round(high, 3), round(low, 3), vol, round(vol * close, 1)])
        price = close
    return bars


print("=" * 60)
print("案例1: 上行周期 + 末段缩量回调企稳(应当是加仓/建仓)")
e1 = update.analyze("512690", "测试上行回调", "白酒", make_bars(True, True), [])
print(f"  trend_env={e1['trend_env']} in_pullback={e1['in_pullback']} "
      f"depth={e1['pullback_depth']} pq={e1['pullback_quality']} -> {e1['signal']}({e1['score']})")

print("=" * 60)
print("案例2: 下行周期 + 末段反弹(应当不触发上行回调加仓)")
e2 = update.analyze("512690", "测试下行反弹", "白酒", make_bars(False, False), [])
print(f"  trend_env={e2['trend_env']} in_pullback={e2['in_pullback']} -> {e2['signal']}({e2['score']})")

print("=" * 60)
print("案例3: 上行周期但已严重超买过热(回调应先等确认, 不急于加仓)")
e3 = update.analyze("512690", "测试过热回调", "白酒", make_bars(True, True, True), [])
print(f"  trend_env={e3['trend_env']} in_pullback={e3['in_pullback']} pq={e3['pullback_quality']} -> {e3['signal']}({e3['score']})")
