import socket
import threading
import time
import json
import logging
from flask import Flask, request, jsonify

app = Flask(__name__)

# Shared variables to store the command and response
command_to_send = None
command_lock = threading.Lock()
response_lock = threading.Lock()
latest_response = []

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.route('/send-command', methods=['POST'])
def send_command():
    global command_to_send
    data = request.get_json()
    command = data.get('command')
    if not command:
        return jsonify({'error': 'No command provided'}), 400
    with command_lock:
        command_to_send = command
    return jsonify({'message': 'Command received', 'command': command}), 200

@app.route('/get-response', methods=['GET'])
def get_response():
    global latest_response
    with response_lock:
        response = latest_response.copy()  # Get a copy of the response to avoid race conditions
    return jsonify({'output': response})

def start_flask_server():
    app.run(host='0.0.0.0', port=5000)

def start_socket_server():
    global command_to_send
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host = '127.0.0.1'
    port = 9999
    server_socket.bind((host, port))
    server_socket.listen(5)
    logger.debug("Socket server is listening...")

    while True:
        client_socket, addr = server_socket.accept()
        logger.debug(f"Got a connection from {addr}")

        while True:
            try:
                with command_lock:
                    if command_to_send:
                        logger.debug(f"Sending command: {command_to_send}")
                        client_socket.send(command_to_send.encode('ascii'))
                        command_to_send = None
                time.sleep(1)
            except (ConnectionResetError, ConnectionAbortedError):
                logger.debug(f"Connection to {addr} was lost. Waiting for new connection.")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break
        client_socket.close()

def start_response_server():
    global latest_response
    response_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    host = '127.0.0.1'
    port = 10000  # Response port
    response_socket.bind((host, port))
    response_socket.listen(5)
    logger.debug("Response server is listening...")

    while True:
        client_socket, addr = response_socket.accept()
        logger.debug(f"Got a response connection from {addr}")

        try:
            data = b''
            while True:
                packet = client_socket.recv(4096)
                if not packet:
                    break
                data += packet

            if data:
                response = json.loads(data.decode('utf-8'))
                with response_lock:
                    output = response.get('output', [])
                    latest_response.extend(output)  # Append to the list
                logger.debug(f"Received response: {response}")
                logger.debug(f"Received output: {output}")
                logger.debug(f"Latest response: {latest_response}")

        except (ConnectionResetError, ConnectionAbortedError):
            logger.debug(f"Connection to {addr} was lost. Waiting for new connection.")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            client_socket.close()

if __name__ == '__main__':
    # Start the Flask server in a separate thread
    flask_thread = threading.Thread(target=start_flask_server)
    flask_thread.start()

    # Start the socket server in a separate thread
    socket_thread = threading.Thread(target=start_socket_server)
    socket_thread.start()

    # Start the response server in the main thread
    start_response_server()
