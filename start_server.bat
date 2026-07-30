@echo off
cd /d "%~dp0"
echo ETF board running at http://localhost:8020
"C:\Users\liuze\.workbuddy\binaries\python\versions\3.13.12\python.exe" -m http.server 8020
