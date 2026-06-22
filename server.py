#!/usr/bin/env python3
"""RSDW Map Server — serves static files + POST /refresh runs the parser."""
import http.server, json, os, subprocess, sys

PORT = 8765
BASE = os.path.dirname(os.path.abspath(__file__))
PARSER = os.path.join(BASE, 'parse_worlds.py')

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE, **kwargs)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path == '/refresh':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self._cors()
            self.end_headers()
            try:
                result = subprocess.run(
                    [sys.executable, PARSER],
                    capture_output=True, text=True, timeout=120, cwd=BASE
                )
                ok  = result.returncode == 0
                log = result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                ok  = False
                log = 'Parser timed out after 120 seconds.'
            except Exception as e:
                ok  = False
                log = str(e)
            self.wfile.write(json.dumps({'ok': ok, 'log': log}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, fmt, *args):
        # Quiet — only print refresh calls
        if '/refresh' in (args[0] if args else ''):
            print(f'[refresh] {args}')

if __name__ == '__main__':
    os.chdir(BASE)
    print(f'\n  RSDW Map Server')
    print(f'  http://localhost:{PORT}/RSDW_Tile_Map.html')
    print(f'  POST /refresh  →  runs parse_worlds.py')
    print(f'  Ctrl+C to stop\n')
    with http.server.ThreadingHTTPServer(('', PORT), Handler) as httpd:
        httpd.serve_forever()
