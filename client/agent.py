import os
import sys
import socket
import subprocess
import json
import time
import logging
import threading
import atexit
import signal

try:
    import keyboard
except ImportError:
    print("keyboard module is not installed. Install it using: pip install keyboard")
    sys.exit(1)

# Path to the lock file
LOCK_FILE_PATH = "agent.lock"

# Check if the lock file exists
if os.path.exists(LOCK_FILE_PATH):
    print("Another instance is already running. Exiting.")
    sys.exit(1)

# Create the lock file
open(LOCK_FILE_PATH, 'a').close()


class SocketStreamer:
    def __init__(self, host, port):
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.connect((host, port))

    def write(self, message):
        self.client_socket.sendall(message.encode('utf-8'))

    def flush(self):
        pass  # Needed for file-like objects, but can be a no-op

    def close(self):
        self.client_socket.close()


def handle_command(command, streamer, logger, host, port):
    try:
        logger.debug(f"Executing command: {command}")
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, universal_newlines=True)
        for line in iter(proc.stdout.readline, ''):
            logger.info(line.strip())  # Log each output line
            streamer.write(line)  # Send to the server without buffering

            # Send the response back to the server immediately
            response = {
                "exit_code": None,
                "output": [line.strip()]  # Include command output in the response
            }
            response_message = json.dumps(response)
            response_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            response_socket.connect((host, port + 1))  # Assuming server listens on port+1 for responses
            response_socket.sendall(response_message.encode('utf-8'))
            response_socket.close()

        # Wait for the process to complete after all lines have been sent
        exit_code = proc.wait()

    except Exception as e:
        exit_code = -1
        logger.error(f"Error executing command: {e}")

    response = {
        "exit_code": exit_code,
        "output": []  # Include command output in the response
    }
    response_message = json.dumps(response)

    logger.debug(f"Sending final response to the server: {response_message}")

    # Send the final response back to the server
    final_response_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    final_response_socket.connect((host, port + 1))  # Assuming server listens on port+1 for responses
    final_response_socket.sendall(response_message.encode('utf-8'))
    final_response_socket.close()


def start_client():
    global client_socket
    logging.basicConfig(level=logging.DEBUG)  # Set logging level to DEBUG
    logger = logging.getLogger(__name__)

    host = '127.0.0.1'
    port = 9999
    client_id = 'client_1234'  # Replace with the actual client ID
    token = 'bf137c42-c6e3-4666-bcec-52956337b5e9'  # Replace with the actual token received during registration

    while True:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((host, port))

            # Send client_id and token for validation
            client_data = json.dumps({'client_id': client_id, 'token': token})
            client_socket.send(client_data.encode('utf-8'))

            response = client_socket.recv(1024).decode('utf-8')
            if 'Connection accepted' not in response:
                logger.error(f"Connection rejected: {response}")
                client_socket.close()
                break

            logger.debug("Client connected to the server.")

            streamer = SocketStreamer(host, port)

            while True:
                message = client_socket.recv(1024)
                if message:
                    command = message.decode('ascii')
                    logger.debug(f"Received command: {command}")

                    # Execute the command in a separate thread to stream output in real-time
                    command_thread = threading.Thread(target=handle_command,
                                                      args=(command, streamer, logger, host, port))
                    command_thread.start()
                else:
                    break
        except (ConnectionResetError, ConnectionRefusedError) as e:
            logger.error(f"Connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            client_socket.close()


def cleanup():
    # Clean up: Remove the lock file when the script exits
    os.remove(LOCK_FILE_PATH)


def signal_handler(sig, frame):
    print("\nGracefully terminating...")
    cleanup()
    sys.exit(0)


def keyboard_handler():
    while True:
        try:
            keyboard.wait('ctrl+c')
            print("\nGracefully terminating...")
            cleanup()
            sys.exit(0)
        except Exception as e:
            print(f"Error occurred: {e}")


# Register cleanup function to be called upon script exit
atexit.register(cleanup)

# Register signal handler for SIGINT (Ctrl+C)
signal.signal(signal.SIGINT, signal_handler)

# Start keyboard handler for Ctrl+Break
keyboard_thread = threading.Thread(target=keyboard_handler)
keyboard_thread.start()

if __name__ == "__main__":
    start_client()