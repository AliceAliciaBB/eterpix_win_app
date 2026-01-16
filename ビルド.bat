@echo off
echo EterPix VRC Uploader をビルドします...
echo.

REM 実行中のプロセスを終了
taskkill /F /IM "EterPix VRC Uploader.exe" 2>nul

REM ビルドフォルダを削除
rmdir /s /q "%~dp0build" 2>nul
rmdir /s /q "%~dp0dist" 2>nul

REM PyInstallerでビルド
pyinstaller "EterPix VRC Uploader.spec" --noconfirm

echo.
echo ビルド完了！
pause