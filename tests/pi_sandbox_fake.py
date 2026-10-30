"""Helper for tests: fake Pi JSONL on stdout (invoked as `pi`)."""
import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
marker = (root / "marker.txt").read_text().strip()
secret = "READ" if (Path.home() / "secret.txt").is_file() and os.access(Path.home() / "secret.txt", os.R_OK) else "NO"
agent_dir = os.environ.get("PI_CODING_AGENT_DIR", "")
auth = Path(agent_dir, "auth.json").read_text() if agent_dir and Path(agent_dir, "auth.json").is_file() else ""
text = f"{marker}|{secret}|{agent_dir}|{auth}"
print(json.dumps({"type": "message_end", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}))
