import os
from http.server import BaseHTTPRequestHandler, HTTPServer


MESSAGE_PATH = "/data/message.txt"


def volume_message():
    try:
        with open(MESSAGE_PATH) as message_file:
            return message_file.read().strip()
    except OSError as exc:
        return f"could not read {MESSAGE_PATH}: {exc}"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"handled GET {self.path}", flush=True)
        body = (
            "hello from axis\n"
            f"env={os.environ.get('APP_ENV', '')}\n"
            f"volume={volume_message()}\n"
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "text/plain")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
