#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${GAIA_ASSISTANT_HOME:-}" ]]; then
  echo "GAIA_ASSISTANT_HOME must be set" >&2
  exit 1
fi

pick_port() {
  python3 - <<'PY'
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("127.0.0.1", 0))
print(sock.getsockname()[1])
sock.close()
PY
}

OPENAI_PORT="$(pick_port)"
OPENROUTER_PORT="$(pick_port)"
TMP_DIR="$(mktemp -d)"

OPENAI_PID=""
OPENROUTER_PID=""
cleanup() {
  if [[ -n "$OPENAI_PID" ]]; then
    kill "$OPENAI_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$OPENROUTER_PID" ]]; then
    kill "$OPENROUTER_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

cat > "$TMP_DIR/mock-openai.py" <<'PY'
#!/usr/bin/env python3
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        if self.path.endswith("/chat/completions"):
            payload = {
                "error": {
                    "message": "You exceeded your current quota",
                    "type": "insufficient_quota",
                    "code": "insufficient_quota",
                }
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()


server = HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler)
server.serve_forever()
PY

cat > "$TMP_DIR/mock-openrouter.py" <<'PY'
#!/usr/bin/env python3
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        if self.path.endswith("/chat/completions"):
            plan = {"reasoning": "fallback-openrouter", "actions": []}
            payload = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(plan),
                        }
                    }
                ]
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()


server = HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler)
server.serve_forever()
PY

python3 "$TMP_DIR/mock-openai.py" "$OPENAI_PORT" &
OPENAI_PID=$!
python3 "$TMP_DIR/mock-openrouter.py" "$OPENROUTER_PORT" &
OPENROUTER_PID=$!
sleep 1

node ./bin/gaia.js init --force >/dev/null

python3 - <<'PY'
import json
import os
from pathlib import Path

cfg_path = Path(os.environ["GAIA_ASSISTANT_HOME"]) / "config.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
reasoning = cfg.setdefault("reasoning", {})
reasoning["provider"] = "openai"
reasoning["model"] = "gpt-4.1-mini"
reasoning["explicit_provider_override"] = True
reasoning["failover"] = {
    "enabled": True,
    "hard_error_classes": ["quota", "auth"],
    "order": ["openrouter", "anthropic"],
    "models": {
        "openai": "gpt-4.1-mini",
        "openrouter": "openrouter/auto",
        "anthropic": "claude-sonnet-4-5-20250929",
    },
}
cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
PY

run_out="$(
  OPENAI_API_KEY="test-openai-key" \
  OPENAI_BASE_URL="http://127.0.0.1:${OPENAI_PORT}/v1" \
  OPENROUTER_API_KEY="test-openrouter-key" \
  OPENROUTER_BASE_URL="http://127.0.0.1:${OPENROUTER_PORT}/api/v1" \
  node ./bin/gaia.js run --mode single 2>&1
)"

[[ "$run_out" == *"Reasoning provider: openai (from launcher config)"* ]]
[[ "$run_out" == *"Reasoning failover: enabled"* ]]
[[ "$run_out" == *"Reasoning failover triggered:"* ]]
[[ "$run_out" == *"Reasoning failover succeeded: openai/gpt-4.1-mini -> openrouter/openrouter/auto"* ]]
[[ "$run_out" == *"No actions proposed this cycle."* ]]
