@echo off
title UiPath to PAD Offline Converter
echo Starting UiPath to PAD Offline Converter on port 8505...
streamlit run app_offline.py --server.port 8505
pause
