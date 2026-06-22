@echo off
title RSDW Storage Map
cd /d "%~dp0"
echo.
echo  ============================================
echo   RSDW Storage Map - Local Server
echo  ============================================
echo.
echo  Server running at http://localhost:8765/RSDW_Tile_Map.html
echo  Use the Refresh button in the map to reload from save files.
echo  Press Ctrl+C here to stop.
echo.
python server.py
pause
