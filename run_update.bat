@echo off
REM ============================================================
REM  ETF 看板 本机自动更新脚本（北京本地网络拉行情最快最稳）
REM  用法：用 Windows「任务计划程序」在 11:35 / 14:50 / 15:30 调用本文件
REM  前置：仓库已 git clone 到本机，且已配置 git 凭据（见下方说明）
REM ============================================================
cd /d %~dp0

python scripts/update.py
if %errorlevel% neq 0 (
    echo [WARN] update.py 执行失败，本次不推送，沿用已有数据
    exit /b 1
)

git add -A
git -c user.name="etf-bot" -c user.email="bot@local" commit -m "auto: ETF 信号更新 %date% %time%" -q
if %errorlevel% neq 0 (
    echo [INFO] 无数据变化，跳过推送
    exit /b 0
)

git push
if %errorlevel% neq 0 (
    echo [ERROR] git push 失败，请检查 git 凭据/网络
    exit /b 1
)
echo [OK] 推送完成，GitHub Pages 将在 1-2 分钟内自动重建
