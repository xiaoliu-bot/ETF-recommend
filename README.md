# 板块ETF技术分析网站

技术面 + 政策面的板块ETF信号看板，定时更新、全量快照、支持回溯。

## 架构

```
数据层（免费源）
  东方财富公开行情接口（主，CDN节点轮换） + 腾讯行情接口（兜底）
  新闻政策面：网络收集 → web/data/news.json（定时任务由 AI 自动搜集更新）
        ↓
引擎层  scripts/update.py
  拉取15只板块ETF日K(前复权160根) + 三大指数
  指标：MA5/10/20/60、MACD、RSI14、KDJ、BOLL、量比
  信号：多因子打分(基准50) + 新闻情绪修正(±8上限) → 0-100分
        ↓
存储层（回溯）
  web/data/snapshots/YYYY-MM-DD_HHMM.json   每次更新的完整快照（K线+信号+理由+新闻）
  web/data/index.json                        快照索引 + 每次各ETF信号摘要（信号历史）
  web/data/latest.json                       最新快照
        ↓
展示层  web/index.html（纯静态，ECharts）
  信号卡片 / K线+MACD+成交量 / 打分明细(思考过程) / 信号历史曲线 / 新闻池 / 快照回溯选择器
```

## 信号规则

| 评分 | 信号 | 仓位建议 |
|------|------|---------|
| ≥70 | 加仓 | 6-8成，分批 |
| 60-70 | 建仓（刚突破MA20/MACD金叉）或 持有 | 2-3成试错 / 4-6成续持 |
| 45-60 | 观望 | ≤3成 |
| 35-45 | 减仓 | ≤2成 |
| <35 | 回避 | 清仓等待企稳 |

打分维度：趋势(MA20/MA60位置、MA20斜率、均线排列) > 动量(MACD/RSI/KDJ) > 量能(量比放量方向) > 乖离(BOLL) + 政策新闻情绪修正。右侧交易，趋势跟踪取向。

## 更新时刻（工作日，已配置自动化任务）

- 11:35 午盘更新
- 14:50 尾盘更新（收盘前最后决策窗口）
- 15:30 收盘后更新

每次自动化任务会先联网收集板块政策新闻更新 `news.json`，再运行 `update.py` 落一个新快照。

## 使用

1. 双击 `start_server.bat` 启动本地服务
2. 浏览器打开 http://localhost:8020
3. 手动更新数据：`python scripts/update.py`（用 WorkBuddy 托管的 python3 路径）

## 历史回放 / 示例

`scripts/update.py` 支持 `--asof YYYY-MM-DD` 参数：以该交易日收盘为锚点，用截至当日的真实日K线 + 当日板块新闻（需提供 `web/data/news_YYYY-MM-DD.json`）回放生成快照，输出到 `web/data/replay_YYYY-MM-DD.json`，**不污染真实 latest.json / index.json 回溯链**。

生成的回放快照可通过 `scripts/gen_sample.py` 内嵌进 `web/sample.html`，得到**离线自包含示例页**（数据已内嵌，双击即开，无需起服务），适合做演示或把历史某日当作样本测试信号引擎。

## 免责声明

信号由规则化模型自动生成，仅供学习研究，不构成投资建议。
