#!/usr/bin/env python3
"""
Script para gerar QR Code em PNG para acesso ao app.
"""

import os
import socket

import qrcode
from PIL import ImageOps

def get_local_ip():
    """Obtém o IP local da máquina"""
    try:
        # Tenta obter IP via socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "localhost"

def get_app_url():
    """Obtém a URL pública do app ou cai para acesso local."""
    configured_url = os.getenv("OBSERVAATT_APP_URL") or os.getenv("OBSERVAPE_APP_URL") or os.getenv("REDEVITIMA_APP_URL")
    if configured_url:
        return configured_url.strip()

    local_ip = get_local_ip()
    return f"http://{local_ip}:8000"


def generate_qr_code():
    """Gera QR Code para acesso ao app."""
    url = get_app_url()
    output_file = os.getenv("QR_OUTPUT_FILE", "qrcode_redevitima.png")

    print("=== ObservaATT PE - QR Code ===")
    print(f"URL do app: {url}")
    print(f"Arquivo de saída: {output_file}")

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=20,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    img = ImageOps.expand(img, border=40, fill="white")
    img.save(output_file, format="PNG", optimize=False)

    print()
    print("Instruções:")
    print("1. Certifique-se de que o servidor está rodando")
    print("2. Escaneie o QR Code com a câmera do celular")
    print("3. Toque em 'Adicionar à tela inicial' para instalar")
    print()
    print("Ou acesse diretamente:", url)
    print("PNG gerado em:", output_file)

if __name__ == "__main__":
    try:
        generate_qr_code()
    except ImportError:
        print("Para gerar QR Code, instale a biblioteca qrcode:")
        print("pip3 install qrcode[pil]")
        print()
        local_ip = get_local_ip()
        print(f"Acesse o app em: http://{local_ip}:8000")