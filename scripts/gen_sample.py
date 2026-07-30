# -*- coding: utf-8 -*-
"""回放快照 -> 离线自包含示例页（双击即开，无需服务器）。
用法: python gen_sample.py --asof 2026-04-07
读取 web/data/replay_{asof}.json，套用 web/sample_template.html，
把数据内嵌进页面，输出 web/sample_{asof}.html。
"""
import json, os, argparse
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument("--asof", default="2026-06-01", help="回放锚定日期，对应 replay_{asof}.json")
a = ap.parse_args().asof

tpl_path = os.path.join(BASE, "sample_template.html")
data_path = os.path.join(BASE, "data", "replay_%s.json" % a)
out_path = os.path.join(BASE, "sample_%s.html" % a)

with open(data_path, encoding="utf-8") as f:
    data = json.load(f)
data_json = json.dumps(data, ensure_ascii=False)

html = open(tpl_path, encoding="utf-8").read()
# 1) 注入数据 + 改为同步加载（保持原始锚点，日期仍 2026-06-01）
html = html.replace('async function loadSnapshot(file) {',
                    'const SNAP = ' + data_json + ';\nfunction loadSnapshot() {', 1)
html = html.replace('snap = await (await fetch("data/" + file + "?_=" + Date.now())).json();',
                    'snap = SNAP;', 1)
html = html.replace('await loadSnapshot("replay_2026-06-01.json");', 'loadSnapshot();', 1)
# 2) 最后把静态文案里的占位日期替换为目标日期
html = html.replace("2026-06-01", a)

open(out_path, "w", encoding="utf-8").write(html)
print("generated:", out_path, "bytes =", len(html), "| has SNAP:", "const SNAP =" in html)
