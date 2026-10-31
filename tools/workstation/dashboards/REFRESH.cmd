@echo off
rem Rebuild the dashboard launcher and open it.
set GITHUB_TOKEN=
set GH_TOKEN=
python "%~dp0build_dashboards.py" %*
start "" "%~dp0index.html"
