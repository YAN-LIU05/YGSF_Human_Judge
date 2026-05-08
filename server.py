import json
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
RECORD_DIR = BASE_DIR / "records"
RECORD_FILE = RECORD_DIR / "attempts.jsonl"


class QuizHandler(SimpleHTTPRequestHandler):
    index_file = "index.html"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.path = f"/{self.index_file}"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/attempts":
            self.send_error(404, "Not found")
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return

        username = str(payload.get("username", "")).strip()
        quiz_id = str(payload.get("quiz_id", "")).strip()
        answers = payload.get("answers")
        if not username or not quiz_id or not isinstance(answers, list):
            self.send_error(400, "username, quiz_id and answers are required")
            return

        correct = sum(1 for item in answers if item.get("is_correct") is True)
        total = len(answers)
        record = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "username": username,
            "quiz_id": quiz_id,
            "quiz_name": payload.get("quiz_name", ""),
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 4) if total else 0,
            "answers": answers,
        }

        RECORD_DIR.mkdir(exist_ok=True)
        with RECORD_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        data = json.dumps({"ok": True, "record": record}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def make_handler(index_file):
    class ConfiguredQuizHandler(QuizHandler):
        pass

    ConfiguredQuizHandler.index_file = index_file
    return ConfiguredQuizHandler


def run_server(host="127.0.0.1", port=9000, index_file="index.html"):
    handler = make_handler(index_file)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"Serving on http://{host}:{port}")
    print(f"Homepage: {index_file}")
    print(f"Records will be appended to {RECORD_FILE}")
    httpd.serve_forever()


def main():
    run_server()


if __name__ == "__main__":
    main()
