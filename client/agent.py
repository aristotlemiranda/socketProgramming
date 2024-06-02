import socket
import subprocess
import json
import time
import logging
import threading


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

'''
def handle_command(command, streamer, logger, host, port):
    try:
        logger.debug(f"Executing command: {command}")
        proc = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, universal_newlines=True)
        for line in iter(proc.stdout.readline, ''):
            logger.info(line.strip())  # Log each output line
            streamer.write(line)  # Send to the server without buffering

        # No need to wait for the process to complete here

        exit_code = proc.poll()  # Check if the process has terminated
        while exit_code is None:
            exit_code = proc.poll()  # Check again until process is terminated

    except Exception as e:
        exit_code = -1
        logger.error(f"Error executing command: {e}")

    response = {
        "exit_code": exit_code,
        "output": []  # Include command output in the response
    }
    response_message = json.dumps(response)

    logger.debug(f"Sending response to the server: {response_message}")

    # Send the response back to the server
    response_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    response_socket.connect((host, port + 1))  # Assuming server listens on port+1 for responses
    response_socket.sendall(response_message.encode('utf-8'))
    response_socket.close()
'''
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

    logger.debug(f"Sending response to the server: {response_message}")

    # Send the final response back to the server
    final_response_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    final_response_socket.connect((host, port + 1))  # Assuming server listens on port+1 for responses
    final_response_socket.sendall(response_message.encode('utf-8'))
    final_response_socket.close()



def start_client():
    logging.basicConfig(level=logging.DEBUG)  # Set logging level to DEBUG
    logger = logging.getLogger(__name__)

    host = '127.0.0.1'
    port = 9999

    while True:
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect((host, port))
            streamer = SocketStreamer(host, port)

            logger.debug("Client connected to the server.")

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


if __name__ == "__main__":
    start_client()
