"""Get base path of user's system to access config files and resources"""

# config/config.py
import json
from pathlib import Path
import sys

# This ensures the path works both in script and exe form
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    base_path = Path(sys._MEIPASS) # pylint: disable=protected-access
else:
    # Running as script
    base_path = Path(__file__).parent.parent

config_path = base_path / 'config' / 'config.json'

with open(config_path, 'r', encoding="utf-8") as f:
    config = json.load(f)
    
