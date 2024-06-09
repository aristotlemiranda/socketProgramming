import socket
import threading
import time
import json
import logging
import sqlite3
import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)

# Shared variables to store the command and response
command_to_send = {}
command_lock = threading.Lock()
response_lock = threading.Lock()
latest_response = []
client_connections = {}

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('clients.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL UNIQUE,
            token TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


init_db()


@app.route('/register', methods=['POST'])
def register_client():
    data = request.get_json()
    client_id = data.get('client_id')
    if not client_id:
        return jsonify({'error': 'No client ID provided'}), 400

    token = str(uuid.uuid4())

    conn = sqlite3.connect('clients.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO clients (client_id, token) VALUES (?, ?)', (client_id, token))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Client already registered'}), 400
    conn.close()

    return jsonify({'message': 'Registration successful', 'token': token}), 200


@app.route('/send-command', methods=['POST'])
def send_command():
    global command_to_send
    data = request.get_json()
    command = data.get('command')
    target_client = data.get('client_id')

    if not command or not target_client:
        return jsonify({'error': 'No command or client ID provided'}), 400

    with command_lock:
        if target_client in client_connections:
            command_to_send[target_client] = command
            return jsonify({'message': 'Command received', 'command': command}), 200
        else:
            return jsonify({'error': 'Client not connected'}), 400


@app.route('/get-response', methods=['GET'])
def get_response():
    global latest_response
    with response_lock:
        response = latest_response.copy()  # Get a copy of the response to avoid race conditions
    return jsonify({'output': response})


def validate_client(client_id, token):
    conn = sqlite3.connect('clients.db')
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM clients WHERE client_id = ? AND token = ?', (client_id, token))
    result = cursor.fetchone()
    conn.close()
    return result is not None


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

        try:
            # Client ID and Token validation
            data = client_socket.recv(1024).decode('utf-8')
            client_data = json.loads(data)
            client_id = client_data['client_id']
            token = client_data['token']

            if not validate_client(client_id, token):
                client_socket.send(b'Invalid client ID or token. Connection rejected.')
                client_socket.close()
                logger.debug(f"Invalid client ID or token from {addr}. Connection closed.")
                continue

            client_socket.send(b'Client validated. Connection accepted.')
            client_connections[client_id] = client_socket
            logger.debug(f"Client {client_id} connected.")

            threading.Thread(target=handle_client, args=(client_socket, client_id)).start()

        except json.JSONDecodeError:
            client_socket.send(b'Invalid data format. Connection rejected.')
            client_socket.close()
            logger.debug(f"Invalid data format from {addr}. Connection closed.")
        except ConnectionResetError:
            logger.debug(f"Connection to {addr} was forcibly closed by the remote host.")
            client_socket.close()


'''
def handle_client(client_socket, client_id):
    global command_to_send
    while True:
        try:
            with command_lock:
                if client_id in command_to_send:
                    command = command_to_send[client_id]
                    logger.debug(f"Sending command to {client_id}: {command}")
                    client_socket.send(command.encode('ascii'))
                    del command_to_send[client_id]
            time.sleep(1)
        except (ConnectionResetError, ConnectionAbortedError):
            logger.debug(f"Connection to {client_id} was lost. Removing client.")
            del client_connections[client_id]
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            break
    client_socket.close()
'''


def handle_client(client_socket, client_id):
    global command_to_send
    try:
        while True:
            with command_lock:
                if client_id in command_to_send:
                    command = command_to_send[client_id]
                    logger.debug(f"Sending command to {client_id}: {command}")
                    client_socket.send(command.encode('ascii'))
                    del command_to_send[client_id]
            time.sleep(1)
    except (ConnectionResetError, ConnectionAbortedError):
        logger.debug(f"Connection to {client_id} was lost. Removing client.")
        del client_connections[client_id]  # Remove client from the connections dictionary
        client_socket.close()  # Close the client socket
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        client_socket.close()  # Close the client socket


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
