@echo off
rem Rebuild the website from the reviews, then open it.
rem After editing output_project\data\site_reviews.csv, double-click this again.
cd /d "%~dp0"
.venv\Scripts\python src\run_pipeline.py || (pause & exit /b 1)
rem Open in Microsoft Edge (full path, because Edge needs it for a local file)
start "" msedge "%~dp0output_project\web\index.html"
