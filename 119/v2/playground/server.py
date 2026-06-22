"""
Triage RAG Playground - Static file server
Usage: python playground/server.py [port]
"""
import http.server
import os
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        pass  # suppress per-request logs


if __name__ == "__main__":
    import socketserver
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Playground: http://localhost:{PORT}")
        httpd.serve_forever()
