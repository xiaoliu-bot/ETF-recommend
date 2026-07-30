# -*- coding: utf-8 -*-
"""
板块新闻自动抓取（GitHub Actions 每日调用，尽力而为）。
数据源: 东方财富快讯接口(免费)。失败不影响主流程(update.py 仍用已有 news.json)。
命中板块关键词 -> 写入 data/news.json（保留近3日，上限40条）。
"""
import json
import os
import ssl
import urllib.request
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "news.json")
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# 板块 -> 关键词（命中任一词即归为该板块）
SECTOR_KW = {
    "券商": ["券商", "证券", "投行", "中信证券", "华泰证券"],
    "银行": ["银行", "央行", "降息", "降准", "信贷", "银保监"],
    "半导体": ["半导体", "晶圆", "中芯", "光刻"],
    "芯片": ["芯片", "半导体"],
    "医药": ["医药", "创新药", "医保", "集采", "生物科技", "CXO", "中药"],
    "白酒": ["白酒", "茅台", "五粮液", "汾酒"],
    "新能源车": ["新能源车", "电动车", "锂电", "比亚迪", "宁德", "固态电池"],
    "光伏": ["光伏", "硅料", "组件", "逆变器"],
    "军工": ["军工", "国防", "航天", "兵装", "中航"],
    "煤炭": ["煤炭", "焦煤", "动力煤", "煤矿"],
    "有色": ["有色", "稀土", "黄金", "铜", "铝"],
    "地产": ["房地产", "楼市", "限购", "住建部", "棚改"],
    "科技": ["科技", "华为", "算力", "鸿蒙", "信创"],
    "消费": ["消费", "社零", "内需", "促消费", "零售"],
    "人工智能": ["人工智能", "AI", "大模型", "机器人", "智算"],
}
GOOD = ["利好", "上涨", "支持", "批复", "获批", "加码", "扶持", "超预期", "增长", "创新高", "上调", "回暖", "扩容"]
BAD = ["利空", "下跌", "打压", "处罚", "下调", "风险", "收紧", "违约", "暴跌", "调查", "问询", "退市", "警示"]


def fetch_kuaixun():
    url = ("https://newsapi.eastmoney.com/kuaixun/v1/getlist?type=1"
           "&page_size=120&page_index=1")
    req = urllib.request.Request(url, headers={**UA, "Referer": "https://kuaixun.eastmoney.com/"})
    with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
        txt = r.read().decode("utf-8", "ignore")
    # 可能是 var kuaixun_v1=...; 或纯 JSON
    if txt.strip().startswith("var"):
        txt = txt.split("=", 1)[1].rsplit(";", 1)[0]
    return json.loads(txt)


def sentiment_of(text):
    if any(w in text for w in BAD):
        return "利空"
    if any(w in text for w in GOOD):
        return "利好"
    return "中性"


def main():
    try:
        js = fetch_kuaixun()
    except Exception as e:
        print("[news_fetch] 抓取失败，保留旧 news.json:", e)
        return  # 不阻断主流程

    items = []
    seen = set()
    for it in js.get("data") or []:
        title = (it.get("title") or "").strip()
        if not title:
            continue
        ts = int(it.get("emit_time") or it.get("time") or 0)
        day = datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else datetime.now().strftime("%Y-%m-%d")
        text = title + " " + (it.get("content") or it.get("summary") or "")
        for sector, kws in SECTOR_KW.items():
            if any(k in text for k in kws):
                key = sector + title
                if key in seen:
                    continue
                seen.add(key)
                items.append({
                    "time": day,
                    "sector": sector,
                    "title": title,
                    "summary": (it.get("content") or it.get("summary") or "")[:120],
                    "sentiment": sentiment_of(text),
                    "source": "东方财富快讯",
                })

    # 保留近3日 + 已有条目中近3日的，去重，上限40
    cutoff = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
    old = []
    if os.path.exists(OUT):
        try:
            old = json.load(open(OUT, encoding="utf-8"))
        except Exception:
            old = []
    merged = items + [x for x in old if str(x.get("time", ""))[:10] >= cutoff]
    # 去重（sector+title）
    uniq = {}
    for x in merged:
        uniq[(x["sector"], x["title"])] = x
    final = sorted(uniq.values(), key=lambda x: x["time"], reverse=True)[:40]

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=1)
    print(f"[news_fetch] 写入 {len(final)} 条（本次新抓 {len(items)} 条）")


if __name__ == "__main__":
    main()
