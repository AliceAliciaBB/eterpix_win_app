@echo off
cd /d %~dp0

set /p COMMIT_MSG=commitメッセージを入力してください: 

if "%COMMIT_MSG%"=="" (
    echo commitメッセージが空のためキャンセルしました
    exit /b
)

git add .
git commit -m "%COMMIT_MSG%"
git push -u origin master
pause