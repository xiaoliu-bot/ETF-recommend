# -*- coding: utf-8 -*-
"""
板块ETF技术分析 - 数据更新与信号引擎
数据源: 东方财富公开行情接口(免费)
每次运行: 拉取K线 -> 计算指标 -> 多因子打分 -> 结合新闻情绪 -> 产出信号 -> 落盘快照(支持回溯)
用法: python update.py
"""
import json
import os
import ssl
import urllib.request
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
SNAP_DIR = os.path.join(DATA_DIR, "snapshots")
os.makedirs(SNAP_DIR, exist_ok=True)

# ---------------- ETF 池 ----------------
ETF_LIST = [
    ("512000", "券商ETF", "券商"),
    ("512480", "半导体ETF", "半导体"),
    ("159995", "芯片ETF", "芯片"),
    ("512010", "医药ETF", "医药"),
    ("512690", "酒ETF", "白酒"),
    ("515030", "新能源车ETF", "新能源车"),
    ("515790", "光伏ETF", "光伏"),
    ("512660", "军工ETF", "军工"),
    ("512800", "银行ETF", "银行"),
    ("512400", "有色金属ETF", "有色"),
    ("515220", "煤炭ETF", "煤炭"),
    ("512200", "房地产ETF", "地产"),
    ("515000", "科技ETF", "科技"),
    ("159928", "消费ETF", "消费"),
    ("159819", "人工智能ETF", "人工智能"),
]

# ---------------- 板块风格与差异化权重 ----------------
# 趋势型(trend): 慢变量、靠均线排列，趋势位置权重高，新闻修正温和(±8)
# 动量型(momentum): 快变量、靠催化与反转，趋势位置惩罚减半、反转/催化加权，新闻修正放大(±15)
STYLE = {
    "券商": "trend", "银行": "trend", "煤炭": "trend", "有色": "trend",
    "地产": "trend", "消费": "trend", "白酒": "trend", "医药": "trend",
    "半导体": "momentum", "芯片": "momentum", "科技": "momentum",
    "人工智能": "momentum", "新能源车": "momentum", "光伏": "momentum", "军工": "momentum",
}
WEIGHTS = {
    "trend":    {"trend_pos": 1.0, "macd_cross": 1.0, "rsi": 1.0, "kdj": 1.0,
                 "reversal": 1.0, "news_per": 3, "news_cap": 8},
    "momentum": {"trend_pos": 0.5, "macd_cross": 1.4, "rsi": 1.2, "kdj": 1.2,
                 "reversal": 1.6, "news_per": 4, "news_cap": 15},
}

INDICES = [
    ("1.000001", "上证指数"),
    ("0.399001", "深证成指"),
    ("0.399006", "创业板指"),
]

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def secid(code):
    return ("1." if code.startswith(("5", "6")) else "0.") + code


def http_json(url, retries=3):
    import time
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={**UA, "Referer": "https://quote.eastmoney.com/",
                                                       "Connection": "close"})
            with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def fetch_kline_em(sid, lmt=160):
    """主数据源: 东方财富(轮换CDN节点)"""
    import random
    node = random.randint(11, 99)
    url = (f"https://{node}.push2his.eastmoney.com/api/qt/stock/kline/get?"
           f"secid={sid}&fields1=f1,f2,f3&fields2=f51,f52,f53,f54,f55,f56,f57"
           f"&klt=101&fqt=1&end=20500101&lmt={lmt}")
    js = http_json(url)
    data = js.get("data") or {}
    bars = []
    for line in data.get("klines") or []:
        p = line.split(",")
        # date, open, close, high, low, volume, amount
        bars.append([p[0], float(p[1]), float(p[2]), float(p[3]), float(p[4]),
                     float(p[5]), float(p[6])])
    return data.get("name", ""), bars


def fetch_kline_tx(sid, lmt=160):
    """备用数据源: 腾讯行情"""
    mkt, code = sid.split(".")
    symbol = ("sh" if mkt == "1" else "sz") + code
    url = (f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?"
           f"param={symbol},day,,,{lmt},qfq")
    js = http_json(url)
    node = (js.get("data") or {}).get(symbol) or {}
    klines = node.get("qfqday") or node.get("day") or []
    bars = []
    for p in klines:
        # [date, open, close, high, low, volume, ...]
        bars.append([p[0], float(p[1]), float(p[2]), float(p[3]), float(p[4]),
                     float(p[5]), float(p[5])])
    return symbol, bars


def fetch_kline(sid, lmt=160):
    import time
    try:
        name, bars = fetch_kline_em(sid, lmt)
        if bars:
            return name, bars
    except Exception:
        pass
    time.sleep(0.8)
    return fetch_kline_tx(sid, lmt)


# ---------------- 指标计算(纯Python) ----------------
def ma(vals, n):
    out = [None] * len(vals)
    s = 0.0
    for i, v in enumerate(vals):
        s += v
        if i >= n:
            s -= vals[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(vals, n):
    out = []
    k = 2.0 / (n + 1)
    prev = vals[0]
    for v in vals:
        prev = v * k + prev * (1 - k)
        out.append(prev)
    return out


def macd(closes):
    e12, e26 = ema(closes, 12), ema(closes, 26)
    dif = [a - b for a, b in zip(e12, e26)]
    dea = ema(dif, 9)
    hist = [(a - b) * 2 for a, b in zip(dif, dea)]
    return dif, dea, hist


def rsi(closes, n=14):
    out = [None] * len(closes)
    gain = loss = 0.0
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g, l = max(ch, 0), max(-ch, 0)
        if i <= n:
            gain += g
            loss += l
            if i == n:
                ag, al = gain / n, loss / n
                out[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
        else:
            ag = (ag * (n - 1) + g) / n
            al = (al * (n - 1) + l) / n
            out[i] = 100 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def kdj(bars, n=9):
    ks, ds, js_ = [], [], []
    k = d = 50.0
    for i in range(len(bars)):
        lo = min(b[4] for b in bars[max(0, i - n + 1):i + 1])
        hi = max(b[3] for b in bars[max(0, i - n + 1):i + 1])
        rsv = 50.0 if hi == lo else (bars[i][2] - lo) / (hi - lo) * 100
        k = k * 2 / 3 + rsv / 3
        d = d * 2 / 3 + k / 3
        ks.append(k); ds.append(d); js_.append(3 * k - 2 * d)
    return ks, ds, js_


def boll(closes, n=20, w=2):
    mid = ma(closes, n)
    up, low = [None] * len(closes), [None] * len(closes)
    for i in range(n - 1, len(closes)):
        seg = closes[i - n + 1:i + 1]
        m = mid[i]
        sd = (sum((x - m) ** 2 for x in seg) / n) ** 0.5
        up[i] = m + w * sd
        low[i] = m - w * sd
    return up, mid, low


# ---------------- 新闻情绪 ----------------
def load_news():
    path = os.path.join(DATA_DIR, "news.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        return []
    cutoff = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    return [x for x in items if str(x.get("time", ""))[:10] >= cutoff]


def news_score(sector, news, style="trend"):
    w = WEIGHTS[style]
    related, delta = [], 0
    for x in news:
        if x.get("sector") == sector or sector in str(x.get("title", "")) + str(x.get("summary", "")):
            related.append(x)
            if x.get("sentiment") == "利好":
                delta += w["news_per"]
            elif x.get("sentiment") == "利空":
                delta -= w["news_per"]
    return max(-w["news_cap"], min(w["news_cap"], delta)), related


# ---------------- 信号引擎 ----------------
def analyze(code, name, sector, bars, news):
    style = STYLE.get(sector, "trend")
    w = WEIGHTS[style]
    closes = [b[2] for b in bars]
    vols = [b[5] for b in bars]
    i = len(bars) - 1
    price = closes[i]
    prev = closes[i - 1]
    chg = (price / prev - 1) * 100

    ma5, ma10, ma20, ma60 = ma(closes, 5), ma(closes, 10), ma(closes, 20), ma(closes, 60)
    dif, dea, hist = macd(closes)
    r = rsi(closes)
    ks, ds, js_ = kdj(bars)
    bu, bm, bl = boll(closes)
    vol_ratio = vols[i] / (sum(vols[i - 5:i]) / 5) if i >= 5 else 1.0

    score = 50.0
    reasons = []
    reversal_parts = []   # 超跌反转信号的明细

    def add(cond_delta, text):
        nonlocal score
        score += cond_delta
        reasons.append({"text": text, "delta": round(cond_delta, 1)})

    # ===== 趋势(位置型) —— 动量型权重减半，避免"价格低就一直扣" =====
    tp = w["trend_pos"]
    if ma20[i]:
        add((8 if price > ma20[i] else -8) * tp,
            f"收盘价{'站上' if price > ma20[i] else '跌破'}20日均线，中期趋势{'偏多' if price > ma20[i] else '偏空'}")
    if ma60[i]:
        add((7 if price > ma60[i] else -7) * tp,
            f"价格位于60日均线{'上方' if price > ma60[i] else '下方'}，长期趋势{'向好' if price > ma60[i] else '承压'}")
    if ma5[i] and ma10[i]:
        add((5 if ma5[i] > ma10[i] else -5) * tp,
            f"5日均线{'高于' if ma5[i] > ma10[i] else '低于'}10日均线，短期动能{'走强' if ma5[i] > ma10[i] else '走弱'}")
    if ma20[i] and ma20[i - 5]:
        up_slope = ma20[i] > ma20[i - 5]
        add((6 if up_slope else -6) * tp, f"20日均线{'向上' if up_slope else '向下'}倾斜")

    # ===== MACD =====
    add((6 if hist[i] > 0 else -6) * w["macd_cross"],
        f"MACD为{'红柱(多头)' if hist[i] > 0 else '绿柱(空头)'}")
    crossed_up = any(hist[j] <= 0 and hist[j + 1] > 0 for j in range(max(0, i - 3), i))
    crossed_dn = any(hist[j] >= 0 and hist[j + 1] < 0 for j in range(max(0, i - 3), i))
    if crossed_up:
        add(6 * w["macd_cross"], "MACD近3日金叉，动量转多")
    if crossed_dn:
        add(-6 * w["macd_cross"], "MACD近3日死叉，动量转空")

    # ===== RSI =====
    rv = r[i]
    if rv is not None:
        if rv > 75:
            add(-5 * w["rsi"], f"RSI={rv:.1f} 超买区，追高风险大")
        elif rv < 30:
            add(5 * w["rsi"], f"RSI={rv:.1f} 超卖，反弹修复动能")
        elif rv >= 50:
            add(3 * w["rsi"], f"RSI={rv:.1f} 强势区(50-75)")
        else:
            add(-3 * w["rsi"], f"RSI={rv:.1f} 弱势区(30-50)")

    # ===== KDJ =====
    if ks[i - 1] <= ds[i - 1] and ks[i] > ds[i]:
        add(4 * w["kdj"], "KDJ金叉")
    elif ks[i - 1] >= ds[i - 1] and ks[i] < ds[i]:
        add(-4 * w["kdj"], "KDJ死叉")

    # ===== 量能 =====
    if vol_ratio > 1.5:
        if chg > 0:
            add(5, f"放量上涨(量比{vol_ratio:.2f})，资金介入")
        else:
            add(-5, f"放量下跌(量比{vol_ratio:.2f})，抛压明显")
    elif vol_ratio < 0.6:
        add(-1, f"量能萎缩(量比{vol_ratio:.2f})")

    # ===== 布林带 =====
    if bu[i] and price > bu[i]:
        add(-3, "突破布林上轨，短期乖离偏大")
    elif bl[i] and price < bl[i]:
        add(3, "跌破布林下轨，超跌状态")

    # ===== 超跌反转因子(核心修复动量型踏空) =====
    rev = 0.0
    if i >= 1 and hist[i] < 0 and hist[i] > hist[i - 1]:
        rev += 4; reversal_parts.append("MACD绿柱收窄(空头动能衰减)")
    if rv is not None and r[i - 5] is not None and rv < 50 and rv > r[i - 5]:
        rev += 3; reversal_parts.append(f"RSI从低位回升({r[i - 5]:.1f}→{rv:.1f})")
    if i >= 2 and closes[i] >= closes[i - 1] >= closes[i - 2]:
        rev += 2; reversal_parts.append("近3日收盘价连续抬升(底部企稳)")
    elif i >= 2 and closes[i] > closes[i - 1] and closes[i - 1] > closes[i - 3]:
        rev += 1.5; reversal_parts.append("近3日价格回升")
    if bl[i] and bl[i - 1] and closes[i - 1] < bl[i - 1] and closes[i] > bl[i]:
        rev += 3; reversal_parts.append("价格收回布林下轨上方")
    if rev > 0:
        add(rev * w["reversal"], "超跌反转信号：" + "；".join(reversal_parts))

    # ===== 动量型过热警戒(防追高，保留右侧纪律) =====
    if style == "momentum":
        if rv is not None and rv > 80:
            add(-6, f"RSI={rv:.1f} 严重超买过热，警惕回落")
        if bu[i] and price > bu[i] * 1.03:
            add(-4, "价格远离布林上轨，追高拥挤")
        if i >= 10 and (price / closes[i - 10] - 1) > 0.30:
            add(-5, "近10日涨幅>30%，交易拥挤")

    # ===== 政策/新闻面(动量型催化上限更高) =====
    nd, related = news_score(sector, news, style)
    if nd != 0:
        add(nd, f"政策/新闻面近3日整体{'偏利好' if nd > 0 else '偏利空'}(修正{nd:+d}分，"
                f"{'动量型催化权重放大' if style == 'momentum' else '趋势型温和修正'})")
    elif related:
        reasons.append({"text": "政策/新闻面中性，无明显方向", "delta": 0})

    score = max(0, min(100, round(score, 1)))

    # ===== 信号映射(动量型加"反转/催化保底"，不轻易回避) =====
    above20 = ma20[i] and price > ma20[i]
    recent_break = ma20[i] and any(
        closes[j] <= (ma20[j] or closes[j]) and closes[j + 1] > (ma20[j + 1] or 0)
        for j in range(max(0, i - 5), i) if ma20[j] and ma20[j + 1])
    has_reversal = rev >= 6
    has_good_news = nd > 0

    if score >= 70:
        signal, advice = "加仓", "强势多头，可加仓至6-8成（分批，勿一次打满）"
    elif score >= 60:
        if recent_break or (above20 and crossed_up):
            signal, advice = "建仓", "趋势刚转多，轻仓2-3成试错"
        else:
            signal, advice = "持有", "趋势健康，持仓4-6成"
    elif score >= 45:
        signal, advice = "观望", "多空不明，空仓等待，持仓<3成"
    elif score >= 35:
        signal, advice = "减仓", "技术面转弱，减仓至2成以下"
    else:
        # 动量型保底：出现反转或利好催化时不直接回避，给小仓左侧试错机会
        if style == "momentum" and (has_reversal or has_good_news):
            signal, advice = "观望", "动量板块出现反转/催化信号，趋势虽未确认，可小仓1-2成左侧试错"
        else:
            signal, advice = "回避", "空头趋势明确，清仓回避，等待企稳信号"

    return {
        "code": code, "name": name, "sector": sector, "style": style,
        "price": round(price, 3), "chg_pct": round(chg, 2),
        "score": score, "signal": signal, "advice": advice,
        "reasons": reasons, "reversal": round(rev, 1),
        "indicators": {
            "ma5": rnd(ma5[i]), "ma10": rnd(ma10[i]), "ma20": rnd(ma20[i]), "ma60": rnd(ma60[i]),
            "rsi": rnd(rv, 1),
            "macd": {"dif": rnd(dif[i], 4), "dea": rnd(dea[i], 4), "hist": rnd(hist[i], 4)},
            "kdj": {"k": rnd(ks[i], 1), "d": rnd(ds[i], 1), "j": rnd(js_[i], 1)},
            "boll": {"up": rnd(bu[i]), "mid": rnd(bm[i]), "low": rnd(bl[i])},
            "vol_ratio": rnd(vol_ratio, 2),
        },
        "news": related[:6],
        "kline": [[b[0], b[1], b[2], b[3], b[4], b[5]] for b in bars[-90:]],
        "ma_lines": {
            "ma5": [rnd(x) for x in ma5[-90:]],
            "ma10": [rnd(x) for x in ma10[-90:]],
            "ma20": [rnd(x) for x in ma20[-90:]],
            "ma60": [rnd(x) for x in ma60[-90:]],
        },
        "macd_hist": [rnd(x, 4) for x in hist[-90:]],
    }
def rnd(v, n=3):
    return None if v is None else round(v, n)


METHODOLOGY = (
    "信号 = 技术面多因子打分(基准50分) + 政策/新闻面情绪修正，并按板块风格差异化加权。"
    "板块分两类：趋势型(券商/银行/煤炭/有色/地产/消费/白酒/医药)——趋势位置权重高、新闻修正温和(±8)；"
    "动量型(半导体/芯片/科技/人工智能/新能源车/光伏/军工)——趋势位置惩罚减半(×0.5)、MACD/KDJ/RSI加权放大、"
    "新闻催化修正放大(±15)，并新增超跌反转因子(绿柱收窄/RSI低位回升/底部抬升/收回布林下轨)捕捉V型反弹起点，"
    "同时对动量型设过热警戒(RSI>80/远离上轨/近10日涨>30%)，反转或利好催化出现时不轻易回避。"
    "技术维度：趋势(MA20/MA60位置、MA20斜率、MA5/MA10排列)、动量(MACD金死叉与红绿柱、RSI、KDJ)、"
    "量能(量比方向)、乖离(布林带)、超跌反转。映射：≥70加仓｜60-70建仓/持有｜45-60观望｜35-45减仓｜<35回避。"
    "设计取向：趋势跟踪为基，动量型兼顾左侧反转；所有信号仅供研究参考，不构成投资建议。"
)
def load_replay_news(asof):
    """历史回放模式加载该日期对应的新闻文件(若存在)。"""
    path = os.path.join(DATA_DIR, f"news_{asof}.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def main(asof=None):
    if asof:
        run_time_str = asof + " 15:30:00"
        label = "历史回放"
        news = load_replay_news(asof)
        print(f"[回放] 锚定日期 {asof}，新闻条目 {len(news)}")
    else:
        now = datetime.now()
        hh = now.hour + now.minute / 60
        label = "午盘" if hh < 13 else ("尾盘" if hh < 15.17 else "收盘后")
        run_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        news = load_news()

    indices = []
    for sid, iname in INDICES:
        try:
            _, bars = fetch_kline(sid, 2)
            if asof:
                bars = [b for b in bars if b[0] <= asof]
            if len(bars) >= 2:
                p, pv = bars[-1][2], bars[-2][2]
                indices.append({"name": iname, "price": round(p, 2),
                                "chg_pct": round((p / pv - 1) * 100, 2)})
        except Exception as e:
            print(f"[warn] index {iname}: {e}")

    import time as _t
    etfs, failed = [], []
    for code, name, sector in ETF_LIST:
        _t.sleep(0.5)
        try:
            _, bars = fetch_kline(secid(code))
            if asof:
                bars = [b for b in bars if b[0] <= asof]
                if not bars:
                    raise ValueError("asof 之前无数据")
            if len(bars) < 70:
                raise ValueError(f"bars={len(bars)} 不足")
            etfs.append(analyze(code, name, sector, bars, news))
            print(f"[ok] {name} {code} -> {etfs[-1]['signal']} ({etfs[-1]['score']})")
        except Exception as e:
            failed.append(code)
            print(f"[fail] {name} {code}: {e}")

    if not etfs:
        raise SystemExit("全部拉取失败，终止且不落盘")

    snapshot = {
        "run_time": run_time_str,
        "label": label,
        "is_replay": bool(asof),
        "indices": indices,
        "etfs": etfs,
        "news": news,
        "methodology": METHODOLOGY,
        "failed": failed,
    }

    if asof:
        fname = f"replay_{asof}.json"
        with open(os.path.join(DATA_DIR, fname), "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False)
        print(f"\n历史回放快照已保存: {fname} | ETF {len(etfs)} 只 | 失败 {len(failed)}")
        return

    fname = "snapshots/" + now.strftime("%Y-%m-%d_%H%M") + ".json"
    with open(os.path.join(DATA_DIR, fname.replace("/", os.sep)), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False)
    with open(os.path.join(DATA_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False)

    idx_path = os.path.join(DATA_DIR, "index.json")
    idx = {"runs": []}
    if os.path.exists(idx_path):
        try:
            with open(idx_path, "r", encoding="utf-8") as f:
                idx = json.load(f)
        except Exception:
            pass
    idx["runs"] = [r for r in idx.get("runs", []) if r.get("file") != fname]
    idx["runs"].append({
        "file": fname,
        "time": snapshot["run_time"],
        "label": label,
        "signals": {e["code"]: {"signal": e["signal"], "score": e["score"],
                                "price": e["price"], "chg": e["chg_pct"]} for e in etfs},
    })
    idx["runs"] = sorted(idx["runs"], key=lambda r: r["time"])[-120:]
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False)

    print(f"\n快照已保存: {fname} | ETF {len(etfs)} 只 | 失败 {len(failed)}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", help="历史回放锚定日期 YYYY-MM-DD（示例/测试用）")
    args = ap.parse_args()
    a = args.asof.strip() if args.asof else None
    if a:
        try:
            datetime.strptime(a, "%Y-%m-%d")
        except Exception:
            print("asof 格式错误，应为 YYYY-MM-DD")
            raise SystemExit(1)
    try:
        main(a)
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        raise
