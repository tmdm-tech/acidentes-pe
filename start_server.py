#!/usr/bin/env python3
import http.server
import socketserver
import os
from pathlib import Path

PORT = 8000
DIRECTORY = "/Users/thaiany.matoso/Desktop/Planilhas Internações ATT/flutter_application_1/acidentes_pe/web"

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def log_message(self, format, *args):
        print(f"{self.client_address[0]} - {format % args}")

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        print(f"\n🚀 ObservaATT PE está rodando!")
        print(f"📱 Abra no seu navegador: http://localhost:{PORT}/index_simple.html")
        print(f"📂 Servindo arquivos de: {DIRECTORY}\n")
        print("Pressione Ctrl+C para parar...\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✓ Servidor parado com sucesso!")
