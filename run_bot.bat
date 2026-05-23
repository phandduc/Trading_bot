@echo off
title XAU/USD Trading Bot
echo ======================================================
echo    KHOI CHAY XAU/USD TELEGRAM TRADING BOT
echo ======================================================
echo Dang khoi dong Python va quet thi truong...
"C:\Users\Duc\AppData\Local\Programs\Python\Python312\python.exe" main.py
if errorlevel 1 (
    echo.
    echo [LOI] Bot da bi dung dot ngot hoac gap loi khoi dong.
    echo Vui long kiem tra xem:
    echo 1. MetaTrader 5 da duoc mo.
    echo 2. Tai khoan dang nhap chinh xac.
    echo 3. Quyen 'Allow Algorithmic Trading' da duoc bat.
    echo.
)
pause
