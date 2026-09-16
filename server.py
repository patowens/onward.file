"""Public, read-only Onward site. No user data is accepted or stored."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from html.parser import HTMLParser
import base64
import hashlib
import socket
import threading

ASSETS = {'/': 'index.html', '/index.html': 'index.html'}


class ScriptHashes(HTMLParser):
    """Hash only the inline script text in the exact document being served."""
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.script = None
        self.hashes = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.script = [] if 'src' not in dict(attrs) else None

    def handle_data(self, data):
        if self.script is not None:
            self.script.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.script is not None:
            digest = hashlib.sha256(''.join(self.script).encode('utf-8')).digest()
            self.hashes.append("'sha256-" + base64.b64encode(digest).decode('ascii') + "'")
            self.script = None


def security_policy(body):
    parser = ScriptHashes()
    parser.feed(body.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n'))
    scripts = ' '.join(sorted(set(parser.hashes))) or "'none'"
    return ("default-src 'none'; script-src " + scripts + "; script-src-attr 'none'; "
            "frame-src 'none'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; "
            "connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(self.server.connection_timeout)
        # An absolute deadline also defeats slow-drip request headers.
        def expire():
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.deadline_timer = threading.Timer(self.server.connection_timeout, expire)
        self.deadline_timer.daemon = True
        self.deadline_timer.start()

    def finish(self):
        self.deadline_timer.cancel()
        try:
            super().finish()
        except (ConnectionError, TimeoutError):
            pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionError, TimeoutError):
            pass

    def send_error(self, code, message=None, explain=None):
        # Never echo request lines, headers, paths or exception details.
        self.respond(405 if code == 501 else code,
                     headers={'Allow': 'GET, HEAD'} if code == 501 else None)

    def log_message(self, *args):
        pass

    def respond(self, status, body=b'', headers=None):
        self.send_response_only(status)
        self.send_header('Date', self.date_time_string())
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy', security_policy(body))
        self.send_header('Content-Length', str(len(body)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if getattr(self, 'command', None) != 'HEAD':
            self.wfile.write(body)

    def do_GET(self):
        entry = ASSETS.get(self.path.split('?', 1)[0])
        if entry:
            path = self.server.site_root / entry
            try:
                if path.is_file() and not path.is_symlink():
                    body = path.read_bytes()
                    return self.respond(200, body, {'Content-Type': 'text/html; charset=utf-8'})
            except OSError:
                pass
        self.respond(404)

    do_HEAD = do_GET


class PublicServer(ThreadingHTTPServer):
    request_queue_size = 32

    def __init__(self, *args, **kwargs):
        self.worker_slots = threading.BoundedSemaphore(32)
        super().__init__(*args, **kwargs)

    def handle_error(self, request, client_address):
        # Default socketserver tracebacks can contain request data and paths.
        pass

    def process_request(self, request, client_address):
        if not self.worker_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.worker_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.worker_slots.release()


def make_server(address, site_root):
    server = PublicServer(address, Handler)
    server.connection_timeout = 10.0
    server.site_root = Path(site_root).resolve()
    return server


def main():
    import os
    import sys
    try:
        httpd = make_server(
            (os.environ.get('HOST', '127.0.0.1'), int(os.environ.get('PORT', '8000'))),
            Path(__file__).parent / 'site',
        )
    except (ValueError, OSError):
        sys.exit('Unable to start public HTTP server; check host and port configuration.')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == '__main__':
    main()
