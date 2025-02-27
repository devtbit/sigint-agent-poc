import socket
import os
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("gqrx_client.log")
    ]
)
logger = logging.getLogger('gqrx_client')

gqrx_host = os.environ['GQRX_HOST']

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)  # Set a 5-second timeout
connected = False


def connect():
    global connected
    try:
        sock.connect((gqrx_host, 7356))
        connected = True
        logger.info(f"Connected to GQRX at {gqrx_host}:7356")
    except socket.error as e:
        logger.error(f"Connection error: {e}")
        raise


def close():
    global connected
    sock.close()
    connected = False
    logger.info("Connection closed")

def send_command(command: str) -> str:
    global connected
    if not connected:
        connect()

    logger.info(f"Sending command: {command}")

    # Ensure command ends with newline
    if not command.endswith('\n'):
        command += '\n'
    
    try:
        sock.sendall(command.encode('utf-8'))
        response = sock.recv(1024).decode('utf-8')
        return response
    except socket.timeout:
        logger.error("Socket timeout - no response received")
        raise
    except socket.error as e:
        logger.error(f"Socket error: {e}")
        connected = False
        raise

try:
    # Get current frequency
    response = send_command("f")
    logger.info(f"Response: {response.strip()}")
finally:
    close()
