import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"Response: {sys.argv[1]}\n".encode())


if __name__ == "__main__":
    HTTPServer(("", 8080), SimpleHTTPRequestHandler).serve_forever()
