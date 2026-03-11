def app(environ, start_response):
    status = '200 OK'
    headers = [('Content-Type', 'text/plain')]
    start_response(status, headers)
    return [b'Hello from server.py']

if __name__ == '__main__':
    from wsgiref.simple_server import make_server
    with make_server('0.0.0.0', 8000, app) as httpd:
        print('Serving on port 8000...')
        httpd.serve_forever()
