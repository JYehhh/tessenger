"""
    Python 3
    Usage: python3 TCPClient3.py localhost 12000
    coding: utf-8
    
    Author: Wei Song (Tutor for COMP3331/9331)
"""
from socket import *
import threading
import sys
import select
import json
import os
import time


##################################################
#                    CONSTANTS                   #
##################################################
# Socket Configuration Constants:
BUFFER_SIZE = 1024

# Command Lists:
SERVER_COMMANDS = ["/msgto", "/activeuser", "/creategroup", "/joingroup", "/groupmsg", "/logout"]
PEER_COMMANDS = ["/p2pvideo"]

# File Transfer Constants:
FILE_CHUNK_SIZE = 1024
TRANSFER_INITIATION_PREFIX = "initiate_transfer"
EOF_SIGNAL = 'EOF'

# User Interface Constants
LOGIN_PROMPT = "Please Login"
WELCOME_MESSAGE = "Welcome to Tessenger!"
COMMAND_PROMPT = "Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout, /p2pvideo): "
EMPTY_INPUT_PROMPT = "Input is empty, do you want to continue (y/n)? "

# Error Messages and Prompts:
INVALID_COMMAND_ERROR = "Error: Invalid command!"

# Network Constants
UDP_PACKET_SEND_INTERVAL = 0.00001
TIMEOUT_FOR_THREAD_SHUTDOWN = 0.5

# Status Code Constants:
SUCCESS = 200
CLIENT_ERROR = 400
UNAUTHORIZED = 401
FORBIDDEN = 403
NOT_FOUND = 404
CONFLICT = 409
INTERNAL_SERVER_ERROR = 500

##################################################
#                 SETUP CONNECTION               #
##################################################

#Server would be running on the same host as Client
if len(sys.argv) != 4:
    print("\n===== Error usage, python3 TCPClient3.py SERVER_IP SERVER_PORT UDP_PORT ======\n")
    exit(0)
server_host = sys.argv[1]
server_port = int(sys.argv[2])
udp_port = int(sys.argv[3])
listening_on_udp = True
server_address = (server_host, server_port)

host_name = gethostname()
local_ip = gethostbyname(host_name)

# setup sockets
client_socket = socket(AF_INET, SOCK_STREAM)
udp_socket = socket(AF_INET, SOCK_DGRAM)
udp_socket.bind(('', udp_port))

# build connection with the server and send message to it
client_socket.connect(server_address)

##################################################
#                 HELPER FUNCTIONS               #
##################################################
def send_and_get_response(message):
    client_socket.sendall(message.encode())
    data = client_socket.recv(BUFFER_SIZE)
    return data.decode()

def split_response(response):
    try:
        response_data = json.loads(response)
        command = response_data.get("command")
        status_code = response_data.get("statusCode")
        message = response_data.get("clientMessage")
        data = response_data.get("data")
    except json.JSONDecodeError:
        print("Error: Received an invalid JSON response.")

    return command, status_code, message, data

def close_connections():
    try:
        # Close the TCP connection
        if client_socket:
            client_socket.close()
        # Close the UDP connection
        if udp_socket:
            global listening_on_udp
            listening_on_udp = False
            time.sleep(TIMEOUT_FOR_THREAD_SHUTDOWN)  # Give the thread time to exit gracefully
            udp_socket.close()

    except Exception as e:
        print(f"Error closing connections: {e}")
##################################################
#                       MAIN                     #
##################################################

################## COLLECT USERNAME ##################
client_username = ""
print(LOGIN_PROMPT)

while True:
    username = input("Username: ")
    response = send_and_get_response(f"[loginusername] {username}")
    _, status_code, message, _ = split_response(response)
    
    if status_code == SUCCESS:
        client_username = username
        break
    elif status_code == NOT_FOUND:
        print(f"{message}")

################## COLLECT PASSWORD ##################
while True:
    password = input("Password: ")
    if password.strip() == '': # assumes a password can't be all whitespaces
        continue
    response = send_and_get_response(f"[loginpassword] {password} {local_ip} {udp_port}")
    _, status_code, message, _ = split_response(response)
    
    if status_code == SUCCESS:
        break
    elif status_code == UNAUTHORIZED:
        print(f"{message}")
    elif status_code == FORBIDDEN:
        print(f"{message}")
        client_socket.close()
        sys.exit(1)
    else:
        print(f"Critical Server Error: Bad Status Code {status_code}")
        sys.exit(1)

################## PROCESS RESPONSES ##################
def process_response(response):
    command, _, message, _ = split_response(response)
    if command == "incomingmessage":
        print(f"\n{message}", end='')
    elif command == "incominggroupmsg":
        print(f"\n{message}", end='')
    elif command == "msgto":
        print(f"{message}")
    elif command == "activeuser":
        print(f"{message}")
    elif command == "creategroup":
        print(f"{message}")
    elif command == "joingroup":
        print(f"{message}")
    elif command == "groupmsg":
        print(f"{message}")
    elif command == "logout":
        print(f"{message}")
        close_connections()
        sys.exit(0)
    elif command == "unknown":
        print(f"{message}")
    else:
        print(f"Critical Server Error: Bad Response Command {command}")
        sys.exit(1)

################## USE SELECT TO WATCH INPUT ##################
print(WELCOME_MESSAGE)
print(COMMAND_PROMPT, end = '', flush=True)

server_commands = ["/msgto", "/activeuser", "/creategroup", "/joingroup", "/groupmsg", "/logout"]
peer_commands = ["/p2pvideo"]

def send_server_command(request):
    client_socket.sendall(request.encode())    

def send_peer_command(request):
    parts = request.strip().split()
    command = parts[0]
    
    if command == "/p2pvideo":
        if len(parts) != 3:
            print("Error: Invalid format. Usage: /p2pvideo username filename")
            print(COMMAND_PROMPT, end = '', flush=True)
            return

        recipient, filename = parts[1], parts[2]
        # Check if file exists
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' does not exist.")
            print(COMMAND_PROMPT, end = '', flush=True)
            return

        # Check if recipient is active and get their UDP details
        response = send_and_get_response("/activeuser")
        _, _, _, active_users_data = split_response(response)

        if recipient in active_users_data["client_ips"] and recipient in active_users_data["udp_ports"]:
            recipient_ip = active_users_data["client_ips"][recipient]
            recipient_port = int(active_users_data["udp_ports"][recipient])
        else:
            print(f"Error: Recipient '{recipient}' is not active.")
            print(COMMAND_PROMPT, end = '', flush=True)
            return
        
        send_file_over_udp(filename, recipient_ip, recipient_port)
        print(COMMAND_PROMPT, end = '', flush=True)

def send_file_over_udp(filename, audience_ip, audience_udp_port):
    global client_username
    sending_socket = socket(AF_INET, SOCK_DGRAM)
    
    initial_packet = f"initiate_transfer {filename} {client_username}"
    sending_socket.sendto(initial_packet.encode(), (audience_ip, audience_udp_port))
    
    with open(filename, 'rb') as file:
        data = file.read(FILE_CHUNK_SIZE) # Read in chunks of 1024 bytes
        while data:
            sending_socket.sendto(data, (audience_ip, audience_udp_port))
            time.sleep(UDP_PACKET_SEND_INTERVAL)
            data = file.read(FILE_CHUNK_SIZE)
            
    print(f"{filename} has been uploaded.")
    sending_socket.sendto(EOF_SIGNAL.encode(), (audience_ip, int(audience_udp_port)))
    
    sending_socket.close()


def listening_for_udp(socket):
    global listening_on_udp
    while listening_on_udp:
        try:
            data, _ = socket.recvfrom(FILE_CHUNK_SIZE)
            packet = data.decode()
            if packet.startswith("initiate_transfer"):
                filename = packet.split()[1]
                username = packet.split()[2]
                with open(f"{username}_{filename}", 'wb') as f:
                    try:
                        while True:
                            video_data, _ = socket.recvfrom(FILE_CHUNK_SIZE)
                            if video_data.endswith(EOF_SIGNAL.encode()):
                                f.write(video_data[:-len(EOF_SIGNAL.encode())]) # NOTE Change this
                                print(f"\nReceived {filename} from {username}")
                                print(COMMAND_PROMPT, end = '', flush=True)
                                break
                            f.write(video_data)
                    except KeyboardInterrupt:
                        print("Receiving interrupted by user")
        except OSError as e:
            # Handle socket closure
            if not listening_on_udp:
                break
            print(f"Error in UDP communication: {e}")

threading.Thread(target=listening_for_udp, args=(udp_socket,), daemon=True).start()

while True:
    readables, _, _ = select.select([sys.stdin, client_socket], [], [])
    
    for readable in readables:
        if readable is sys.stdin:
            request = sys.stdin.readline()
            
            if request.strip() == '':
                cont = input(EMPTY_INPUT_PROMPT)
                if cont == 'y':
                    # don't send the packet and continue
                    print(COMMAND_PROMPT, end = '', flush=True)
                    continue
                elif cont == 'n':
                    client_socket.sendall(request.encode())
                    close_connections()
                    sys.exit(0)
                else:
                    print("User did not enter y/n, continuing...")
                    print(COMMAND_PROMPT, end = '', flush=True)
                    continue
            
            command = request.split()[0]
            if command in server_commands:
                send_server_command(request)
            elif command in peer_commands:
                send_peer_command(request)
            else:
                print(INVALID_COMMAND_ERROR)
                print(COMMAND_PROMPT, end = '', flush=True)
                continue
            
        if readable is client_socket:
            response = client_socket.recv(BUFFER_SIZE).decode()
            process_response(response)
            print(COMMAND_PROMPT, end = '', flush=True)


