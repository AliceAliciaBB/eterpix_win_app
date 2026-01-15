@echo off
rmdir /s /y %~dp0build
pyinstaller "EterPix VRC Uploader.spec"
pause