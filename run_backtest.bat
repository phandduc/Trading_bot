@echo off
title MT5 Bot Strategy Backtester
echo ======================================================
echo    KHOI CHAY BACKTEST - KIEM THU CHIEN LUOC MT5
echo ======================================================
set /p sym="Nhap ma giao dich muon test (Nhap ALL de test tat ca, Mac dinh: ALL): "
if "%sym%"=="" set sym=ALL
set /p days="Nhap so ngay muon kiem thu (Mac dinh: 45): "
if "%days%"=="" set days=45


echo.
echo Dang chay kiem thu %sym% trong %days% ngay qua...
"C:\Users\Duc\AppData\Local\Programs\Python\Python312\python.exe" backtest.py %sym% %days%
echo.
pause
