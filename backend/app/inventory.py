"""Contract of the active bundled catalogue."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'data'
def inventory():
    return json.loads((DATA/'metra-demo/inventory.json').read_text(encoding='utf-8'))
