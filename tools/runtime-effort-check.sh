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
TMP_DIR="$(mktemp -d)"
OPENAI_PID=""

cleanup() {
  if [[ -n "$OPENAI_PID" ]]; then
    kill "$OPENAI_PID" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

cat > "$TMP_DIR/mock-openai-effort.py" <<'PY'
#!/usr/bin/env python3
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        if not self.path.endswith("/chat/completions"):
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        model = str(payload.get("model", ""))
        effort = payload.get("reasoning_effort")
        if model == "gpt-5.3-codex" and effort != "high":
            response = {
                "error": {
                    "message": f"expected reasoning_effort=high for {model}, got {effort!r}",
                    "type": "invalid_request_error",
                }
            }
            raw = json.dumps(response).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        if model == "gpt-4.1-mini" and effort is not None:
            response = {
                "error": {
                    "message": f"reasoning_effort must be omitted for {model}",
                    "type": "invalid_request_error",
                }
            }
            raw = json.dumps(response).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return

        plan = {"reasoning": "effort-check-ok", "actions": []}
        response = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(plan),
                    }
                }
            ]
        }
        raw = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


server = HTTPServer(("127.0.0.1", int(sys.argv[1])), Handler)
server.serve_forever()
PY

python3 "$TMP_DIR/mock-openai-effort.py" "$OPENAI_PORT" &
OPENAI_PID=$!
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
reasoning["model"] = "gpt-5.3-codex"
reasoning["effort"] = "high"
reasoning["explicit_provider_override"] = True
cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
PY

run_supported="$(
  OPENAI_API_KEY="test-openai-key" \
  OPENAI_BASE_URL="http://127.0.0.1:${OPENAI_PORT}/v1" \
  node ./bin/gaia.js run --mode single 2>&1
)"

[[ "$run_supported" == *"Reasoning provider: openai (from launcher config)"* ]]
[[ "$run_supported" == *"Reasoning model: gpt-5.3-codex (from launcher config)"* ]]
[[ "$run_supported" == *"Reasoning effort: high (from launcher config)"* ]]
[[ "$run_supported" == *"Applied reasoning effort: provider=openai model=gpt-5.3-codex effort=high"* ]]
[[ "$run_supported" == *"No actions proposed this cycle."* ]]

python3 - <<'PY'
import json
import os
from pathlib import Path

cfg_path = Path(os.environ["GAIA_ASSISTANT_HOME"]) / "config.json"
cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
reasoning = cfg.setdefault("reasoning", {})
reasoning["provider"] = "openai"
reasoning["model"] = "gpt-4.1-mini"
reasoning["effort"] = "high"
reasoning["explicit_provider_override"] = True
cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
PY

run_unsupported="$(
  OPENAI_API_KEY="test-openai-key" \
  OPENAI_BASE_URL="http://127.0.0.1:${OPENAI_PORT}/v1" \
  node ./bin/gaia.js run --mode single 2>&1
)"

[[ "$run_unsupported" == *"Reasoning provider: openai (from launcher config)"* ]]
[[ "$run_unsupported" == *"Reasoning model: gpt-4.1-mini (from launcher config)"* ]]
[[ "$run_unsupported" == *"Reasoning effort: high (from launcher config)"* ]]
[[ "$run_unsupported" == *"Reasoning effort not applied: provider=openai model=gpt-4.1-mini effort=high (unsupported provider/model)"* ]]
[[ "$run_unsupported" == *"No actions proposed this cycle."* ]]
