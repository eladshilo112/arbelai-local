@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "& python '%USERPROFILE%\ARBELAI_COMPUTE_NODE\portable.py' rollback --target '%USERPROFILE%\ARBELAI_COMPUTE_NODE' --confirm-rollback"
pause
