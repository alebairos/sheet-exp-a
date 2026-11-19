"""Serves the UI (web/) and computes workbooks with the engine (intent a-i11-open-save).

    python3 web/io/serve.py [port]      then open http://127.0.0.1:<port>/io/index.html (port 8000 by default)

GET serves the files under web/ (JavaScript with its MIME type, which ES modules need);
POST /compute takes a workbook as JSON and answers with what ./engine computes for it.
Python standard library only, like the engine.
"""

import http.server
import json
import os
import sys

WEB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(WEB))

from src.cli import compute  # noqa: E402  (the repo root is on the path only now)


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".json": "application/json",
        ".css": "text/css",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB, **kwargs)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/compute":
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            book = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as e:
            self.send_error(400, "not a JSON workbook: %s" % e)
            return
        body = json.dumps(compute(book)).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main(argv):
    port = int(argv[1]) if len(argv) > 1 else 8000
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("Serving http://127.0.0.1:%d/io/index.html" % port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main(sys.argv)
