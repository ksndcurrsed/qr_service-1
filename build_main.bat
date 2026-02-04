@echo off
REM Сборка main.py в exe
echo Installing dependencies...
pip install pyinstaller aiohttp pillow pylibdmtx pynput openpyxl python-dotenv pywin32

echo.
echo Building main.exe...
pyinstaller --noconfirm --onefile ^
    --name "qr_print_client" ^
    --hidden-import=pylibdmtx ^
    --hidden-import=pylibdmtx.pylibdmtx ^
    --collect-all pylibdmtx ^
    --hidden-import=pynput ^
    --hidden-import=pynput.keyboard ^
    --hidden-import=win32print ^
    --hidden-import=win32ui ^
    --hidden-import=win32con ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    --hidden-import=PIL.ImageWin ^
    --hidden-import=openpyxl ^
    --hidden-import=openpyxl.cell.cell ^
    --hidden-import=aiohttp ^
    --hidden-import=dotenv ^
    --console ^
    main.py

echo.
echo Done! EXE: dist\qr_print_client.exe
pause
