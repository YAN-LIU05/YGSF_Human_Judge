import json
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
RECORD_DIR = BASE_DIR / "records"
RECORD_FILE = RECORD_DIR / "attempts.jsonl"
QUIZ_FILE = BASE_DIR / "data" / "quizzes.json"
HINT_MODES = {
    "with_hint": "有提示",
    "image_only": "仅图片",
}


def load_quizzes():
    with QUIZ_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("quizzes", [])


def ordered_usernames():
    names = []
    seen = set()
    if not RECORD_FILE.exists():
        return names

    with RECORD_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            username = str(item.get("username", "")).strip()
            if username and username not in seen:
                seen.add(username)
                names.append(username)
    return names


def assign_quiz(username):
    quizzes = load_quizzes()
    if not quizzes:
        raise RuntimeError("No quizzes available")

    names = ordered_usernames()
    if username in names:
        index = names.index(username)
    else:
        index = len(names)

    quiz = quizzes[index % len(quizzes)]
    return {
        "participant_order": index + 1,
        "quiz_id": quiz.get("id", ""),
        "quiz_name": quiz.get("name", ""),
        "quiz_index": index % len(quizzes),
        "quiz_count": len(quizzes),
    }


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
        if parsed.path == "/api/assignment":
            self.handle_assignment()
            return
        if parsed.path == "/api/attempts":
            self.handle_attempt()
            return

        self.send_error(404, "Not found")

    def read_json_payload(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return None

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_assignment(self):
        payload = self.read_json_payload()
        if payload is None:
            return

        username = str(payload.get("username", "")).strip()
        hint_mode = str(payload.get("hint_mode", "with_hint")).strip()
        if not username:
            self.send_error(400, "username is required")
            return
        if hint_mode not in HINT_MODES:
            self.send_error(400, "Invalid hint_mode")
            return

        try:
            assignment = assign_quiz(username)
        except RuntimeError as exc:
            self.send_error(500, str(exc))
            return

        self.send_json({
            "ok": True,
            "assignment": {
                **assignment,
                "hint_mode": hint_mode,
                "hint_mode_label": HINT_MODES[hint_mode],
            },
        })

    def handle_attempt(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/attempts":
            self.send_error(404, "Not found")
            return

        payload = self.read_json_payload()
        if payload is None:
            return

        username = str(payload.get("username", "")).strip()
        hint_mode = str(payload.get("hint_mode", "with_hint")).strip()
        answers = payload.get("answers")
        if not username or not isinstance(answers, list):
            self.send_error(400, "username and answers are required")
            return
        if hint_mode not in HINT_MODES:
            self.send_error(400, "Invalid hint_mode")
            return

        try:
            assignment = assign_quiz(username)
        except RuntimeError as exc:
            self.send_error(500, str(exc))
            return

        correct = sum(1 for item in answers if item.get("is_correct") is True)
        total = len(answers)
        record = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "username": username,
            "participant_order": assignment["participant_order"],
            "quiz_id": assignment["quiz_id"],
            "quiz_name": assignment["quiz_name"],
            "hint_mode": hint_mode,
            "hint_mode_label": HINT_MODES[hint_mode],
            "total": total,
            "correct": correct,
            "accuracy": round(correct / total, 4) if total else 0,
            "answers": answers,
        }

        RECORD_DIR.mkdir(exist_ok=True)
        with RECORD_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        self.send_json({"ok": True, "record": record})


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
