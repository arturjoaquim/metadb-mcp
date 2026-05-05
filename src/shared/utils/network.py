"""Utilitários de rede."""

import socket


def find_free_port(host: str, start_port: int) -> int:
    """Encontra uma porta TCP livre começando da porta especificada."""
    port = start_port
    while port <= 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                port += 1
    raise OSError("Não há portas livres disponíveis.")
