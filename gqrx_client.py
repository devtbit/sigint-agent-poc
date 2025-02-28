import socket
import os
import logging

# Get logger for this module
logger = logging.getLogger('gqrx_client')

gqrx_host = os.environ['GQRX_HOST']

# Move socket creation into the connect function
connected = False
sock = None


def connect():
    global connected, sock
    # Create a new socket each time we connect
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)  # Set a 5-second timeout
    try:
        sock.connect((gqrx_host, 7356))
        connected = True
        logger.info(f"Connected to GQRX at {gqrx_host}:7356")
    except socket.error as e:
        logger.error(f"Connection error: {e}")
        raise


def close():
    global connected, sock
    if sock:
        sock.close()
    connected = False
    logger.info("Connection closed")


def send(command: str) -> str:
    global connected, sock
    if not connected:
        connect()

    logger.info(f"Sending command: {command}")

    # Ensure command ends with newline
    if not command.endswith('\n'):
        command += '\n'

    try:
        sock.sendall(command.encode('utf-8'))
        response = sock.recv(1024).decode('utf-8')
        logger.info(f"Response: {response.strip()}")
        return response.strip()
    except socket.timeout:
        logger.error("Socket timeout - no response received")
        raise
    except socket.error as e:
        logger.error(f"Socket error: {e}")
        connected = False
        raise
