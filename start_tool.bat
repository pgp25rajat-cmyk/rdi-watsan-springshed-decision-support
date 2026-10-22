@echo off
rem Starts the spring tool and opens it in your browser. Keep this window open while you use the tool.
rem Map folders: by default MapCache and Data next to this Tool folder (DOCC\MapCache, DOCC\Data).
rem The hand-downloaded layers (IMD, SoilGrids, Bhoonidhi) are read from DOCC\Data\Secondary data when that folder exists.
cd /d "%~dp0"
if not defined SPRING_LAYER_CACHE set "SPRING_LAYER_CACHE=%~dp0..\MapCache"
if not defined SPRING_LOCAL_LAYERS if exist "%~dp0..\Data\Secondary data\" set "SPRING_LOCAL_LAYERS=%~dp0..\Data\Secondary data"
if not defined SPRING_LOCAL_LAYERS set "SPRING_LOCAL_LAYERS=%~dp0..\Data"
if not exist ".venv\Scripts\python.exe" (
  echo No Python environment found in %~dp0.venv
  echo Set it up once as described in docs\run-module-a-locally.md, section 1.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\spring_tool_server.py --open
pause
