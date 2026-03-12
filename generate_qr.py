#!/usr/bin/env python3
"""
Script para gerar QR Code do ObservaTrânsito
Facilita o acesso móvel ao app
"""

import socket
import qrcode
import os

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

def generate_qr_code():
    """Gera QR Code para acesso ao app"""
    local_ip = get_local_ip()
    url = f"http://{local_ip}:8000"

    print("=== ObservaTrânsito - QR Code ===")
    print(f"URL do app: {url}")
    print("Escaneie o QR Code abaixo com seu celular:")
    print()

    # Gerar QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=2,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Imprimir QR Code no terminal
    qr.print_ascii()

    print()
    print("Instruções:")
    print("1. Certifique-se de que o servidor está rodando")
    print("2. Escaneie o QR Code com a câmera do celular")
    print("3. Toque em 'Adicionar à tela inicial' para instalar")
    print()
    print("Ou acesse diretamente:", url)

if __name__ == "__main__":
    try:
        generate_qr_code()
    except ImportError:
        print("Para gerar QR Code, instale a biblioteca qrcode:")
        print("pip3 install qrcode[pil]")
        print()
        local_ip = get_local_ip()
        print(f"Acesse o app em: http://{local_ip}:8000")