import json
import os
from wsgiref.simple_server import make_server


def _json_response(start_response, status_code, payload):
    body = json.dumps(payload).encode("utf-8")
    status_map = {200: "200 OK", 404: "404 Not Found"}
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ]
    start_response(status_map[status_code], headers)
    return [body]


def app(environ, start_response):
    path = environ.get("PATH_INFO", "/")

    if path == "/":
        return _json_response(
            start_response,
            200,
            {
                "status": "ok",
                "service": "acidentes-pe",
                "message": "API online",
            },
        )

    if path == "/health":
        return _json_response(start_response, 200, {"status": "healthy"})

    if path == "/version":
        return _json_response(start_response, 200, {"version": "1.0.0"})

    return _json_response(start_response, 404, {"error": "not found", "path": path})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    with make_server("0.0.0.0", port, app) as httpd:
        print(f"Serving on port {port}...")
        httpd.serve_forever()
