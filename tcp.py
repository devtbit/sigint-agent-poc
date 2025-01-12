import socket
import os


gqrx_host = os.environ['GQRX_HOST']

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connected = False


def connect():
    sock.connect((gqrx_host, 7356))
    connected = True


def close():
    sock.close()
    connected = False

def send_command(command: str) -> str:
    if not connected:
        connect()
