# -*- coding: utf-8 -*-
# 今日真实快照(latest.json) -> 离线自包含示例页, 重点演示"上行周期回调加仓"
import json, os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tpl_path = os.path.join(BASE, "sample_template.html")
data_path = os.path.join(BASE, "data", "latest.json")
out_path = os.path.join(BASE, "sample_today.html")

with open(data_path, encoding="utf-8") as f:
    data = json.load(f)
data_json = json.dumps(data, ensure_ascii=False)

html = open(tpl_path, encoding="utf-8").read()
# 1) 注入今日数据 + 改为同步加载
html = html.replace('async function loadSnapshot(file) {',
                    'const SNAP = ' + data_json + ';\nfunction loadSnapshot() {', 1)
html = html.replace('snap = await (await fetch("data/" + file + "?_=" + Date.now())).json();',
                    'snap = SNAP;', 1)
html = html.replace('await loadSnapshot("replay_2026-06-01.json");', 'loadSnapshot();', 1)
# 2) 文案替换为"今日实时 / 上行回调演示"
html = html.replace('<title>板块ETF技术分析 · 历史回放示例（2026-06-01）</title>',
                    '<title>板块ETF技术分析 · 上行回调加仓演示（今日实时）</title>')
html = html.replace('历史回放示例', '上行回调加仓演示')
html = html.replace('本页数据锚定 <b>2026-06-01 收盘</b>，由截至该交易日的真实日K线 + 当日板块政策新闻，经信号引擎回放生成。',
                    '本页为<b>今日实时快照</b>，重点演示新引擎（v3）如何识别「上行周期中的健康回调=加仓点」（如券商ETF），而非追涨杀跌。')
html = html.replace('（2026-06-01）', '（今日实时）')
html = html.replace('历史回放', '实时演示')
html = html.replace('2026-06-01', '今日')
open(out_path, "w", encoding="utf-8").write(html)
print("generated:", out_path, "bytes =", len(html), "| has SNAP:", "const SNAP =" in html)
