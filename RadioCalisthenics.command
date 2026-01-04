#!/bin/bash
cd "$(dirname "$0")"
source venv_gui/bin/activate
python scripts/gui_app.py
