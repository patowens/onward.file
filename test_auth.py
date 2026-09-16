"""Public read-only HTTP regression tests (historical filename)."""
import http.client
import pathlib
import socket
import threading
import time

import pytest
import server

ROOT = pathlib.Path(__file__).parent


@pytest.fixture
def service(tmp_path):
    document = b'<!doctype html><h1>Public app</h1><script>console.log("offline");</script>'
    (tmp_path / 'index.html').write_bytes(document)
    httpd = server.make_server(('127.0.0.1', 0), tmp_path)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, tmp_path, document
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def request(service, method='GET', path='/', headers=None):
    conn = http.client.HTTPConnection(*service[0].server_address, timeout=2)
    try:
        conn.request(method, path, headers=headers or {})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def test_security_policy_on_success_and_errors(service):
    for method, path in [('GET', '/'), ('GET', '/missing'), ('POST', '/')]:
        _, headers, _ = request(service, method, path)
        assert 'Python' not in headers.get('Server', '')
        assert headers['Cache-Control'] == 'no-store'
        assert headers['X-Content-Type-Options'] == 'nosniff'
        assert headers['Referrer-Policy'] == 'no-referrer'
        assert headers['X-Frame-Options'] == 'DENY'
        assert headers['Permissions-Policy'] == 'camera=(), microphone=(), geolocation=()'
        policy = headers['Content-Security-Policy']
        for directive in ("default-src 'none'", "connect-src 'none'", "form-action 'none'",
                          "base-uri 'none'", "object-src 'none'", "frame-ancestors 'none'",
                          "script-src-attr 'none'"):
            assert directive in policy


def test_index_read_failure_is_generic(service, monkeypatch, capsys):
    def fail_read(self):
        raise OSError('sensitive-filesystem-probe')
    monkeypatch.setattr(pathlib.Path, 'read_bytes', fail_read)
    status, _, body = request(service)
    assert status == 404
    assert body == b''
    assert 'sensitive-filesystem-probe' not in capsys.readouterr().err


def test_unsupported_methods_are_rejected_without_reading_body(service):
    for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'TRACE', 'CONNECT', 'BOGUS'):
        status, headers, body = request(service, method, '/api/vault',
                                        {'Content-Length': '999999999'})
        assert status == 405
        assert headers.get('Allow') == 'GET, HEAD'
        assert body == b''
        assert 'Set-Cookie' not in headers


def test_unexpected_worker_errors_do_not_log_request_data(service, monkeypatch, capsys):
    def fail(self):
        raise RuntimeError(self.path)
    monkeypatch.setattr(server.Handler, 'do_GET', fail)
    with pytest.raises(http.client.RemoteDisconnected):
        request(service, path='/sensitive-request-probe')
    assert capsys.readouterr().err == ''


def test_public_constructor_requires_no_credentials():
    import inspect
    required = [p.name for p in inspect.signature(server.make_server).parameters.values()
                if p.default is inspect.Parameter.empty]
    assert required == ['address', 'site_root']


def test_public_get_head_without_cookies(service):
    for path in ('/', '/index.html', '/?v=1'):
        status, headers, body = request(service, path=path)
        assert status == 200
        assert body == service[2]
        assert 'Set-Cookie' not in headers
        status, head, body = request(service, 'HEAD', path)
        assert status == 200
        assert body == b''
        assert head['Content-Length'] == headers['Content-Length']



@pytest.mark.parametrize('path', ['/login', '/api/login', '/api/logout', '/api/vault',
    '/.env', '/.env.local', '/server.py', '/test_auth.py', '/CONTEXT.md', '/notes/',
    '/../index.html', '/%2e%2e/index.html', '/site/index.html', '/export.js',
    '/app.js', '/styles.css', '/favicon.svg', '/index.html/extra', '/index.html%00'])
def test_only_built_index_is_public(service, path):
    # Even files present in the web root remain private unless allowlisted.
    (service[1] / '.env').write_text('not-public')
    (service[1] / 'app.js').write_text('not-public')
    for method in ('GET', 'HEAD'):
        status, headers, body = request(service, method, path)
        assert status == 404
        assert body == b''
        assert 'Location' not in headers
        assert 'Set-Cookie' not in headers


def test_missing_and_symlink_index_are_not_served(service):
    index = service[1] / 'index.html'
    index.unlink()
    assert request(service)[0] == 404
    private = service[1] / 'private.txt'
    private.write_text('private')
    index.symlink_to(private)
    assert request(service)[0] == 404


def test_cookies_are_ignored_and_request_content_not_logged(service, capsys):
    status, headers, body = request(service, headers={'Cookie': 'onward_session=sensitive-probe'})
    assert status == 200
    assert body == service[2]
    assert 'Set-Cookie' not in headers
    status, headers, body = request(service, 'BOGUS', '/sensitive-probe')
    assert status == 405
    assert body == b''
    assert capsys.readouterr().err == ''


def test_idle_and_slow_drip_headers_expire(service):
    service[0].connection_timeout = 0.2
    for drip in (False, True):
        with socket.create_connection(service[0].server_address, timeout=1) as sock:
            sock.sendall(b'GET / HTTP/1.1\r\nHost:')
            if drip:
                for _ in range(6):
                    time.sleep(0.05)
                    try:
                        sock.sendall(b'x')
                    except OSError:
                        break
            assert sock.recv(1024) == b''
    assert request(service)[0] == 200


def test_workers_are_bounded_and_released(service):
    sockets = []
    try:
        for _ in range(32):
            sock = socket.create_connection(service[0].server_address, timeout=2)
            sockets.append(sock)
            sock.sendall(b'GET / HTTP/1.1\r\n')
        with socket.create_connection(service[0].server_address, timeout=1) as extra:
            assert extra.recv(1024) == b''
    finally:
        for sock in sockets:
            sock.close()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            if request(service)[0] == 200:
                return
        except (OSError, http.client.HTTPException):
            time.sleep(0.01)
    pytest.fail('worker capacity was not released')


def test_container_build_context_is_minimal():
    dockerfile = (ROOT / 'Dockerfile').read_text()
    copies = [line for line in dockerfile.splitlines() if line.startswith('COPY ')]
    assert copies == ['COPY --chown=10001:10001 server.py /app/server.py',
                      'COPY --chown=10001:10001 site/index.html /app/site/index.html']
    allowed = [line for line in (ROOT / '.dockerignore').read_text().splitlines()
               if line.startswith('!')]
    assert allowed == ['!server.py', '!site/', '!site/index.html']
    assert 'USER 10001:10001' in dockerfile



def test_main_starts_without_auth_environment():
    import os
    import subprocess
    import sys
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env = {k: v for k, v in os.environ.items()
           if k not in ('SITE_PASSWORD', 'AUTH_SECRET', 'TRUSTED_PROXIES')}
    env.update(HOST='127.0.0.1', PORT=str(port))
    process = subprocess.Popen([sys.executable, str(ROOT / 'server.py')],
                               env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            assert process.poll() is None, 'public server exited without auth configuration'
            try:
                conn = http.client.HTTPConnection('127.0.0.1', port, timeout=1)
                conn.request('GET', '/')
                response = conn.getresponse()
                assert response.status == 200
                assert response.read() == (ROOT / 'site/index.html').read_bytes()
                conn.close()
                break
            except ConnectionRefusedError:
                time.sleep(0.02)
        else:
            pytest.fail('public server did not become ready')
    finally:
        process.terminate()
        out, err = process.communicate(timeout=3)
    assert out == err == b''


def test_malformed_http_does_not_echo_or_log(service, capsys):
    with socket.create_connection(service[0].server_address, timeout=2) as sock:
        sock.sendall(b'GET /sensitive-probe HTTP/not-a-version\r\n\r\n')
        response = bytearray()
        while chunk := sock.recv(4096):
            response.extend(chunk)
    assert b'sensitive-probe' not in response
    assert b'Python' not in response
    assert capsys.readouterr().err == ''
