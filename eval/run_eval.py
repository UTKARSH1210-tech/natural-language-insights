"""Evaluation harness placeholder.

Keep expected values dataset-specific and deterministic. The final version
should submit each question to the API, normalize the returned result, and
compare it against expected answers/tolerances.
"""

import json
from pathlib import Path

questions = json.loads(Path(__file__).with_name("questions.json").read_text())

for item in questions:
    print(f"[TODO] {item['question']} ({item['type']})")
