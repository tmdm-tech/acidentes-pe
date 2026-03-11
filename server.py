from wsgiref.simple_server import make_server


def app(environ, start_response):
    path = environ.get('PATH_INFO', '/')
    status = '200 OK'
    headers = [('Content-Type', 'application/json')]

    if path == '/' or path == '/health':
        body = b'{"status": "ok", "path": "%s"}' % path.encode('utf-8')
    else:
        status = '404 Not Found'
        body = b'{"error": "not found"}'

    start_response(status, headers)
    return [body]


if __name__ == '__main__':
    port = 8000
    with make_server('0.0.0.0', port, app) as httpd:
        print(f'Serving on port {port}...')
        httpd.serve_forever()
