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
#                 SETUP CONNECTION               #
##################################################

#Server would be running on the same host as Client
if len(sys.argv) != 4:
    print("\n===== Error usage, python3 TCPClient3.py SERVER_IP SERVER_PORT UDP_PORT ======\n")
    exit(0)
serverHost = sys.argv[1]
serverPort = int(sys.argv[2])
udpPort = int(sys.argv[3])
listening_on_udp = True
serverAddress = (serverHost, serverPort)

host_name = gethostname()
local_ip = gethostbyname(host_name)

# setup sockets
clientSocket = socket(AF_INET, SOCK_STREAM)
udpSocket = socket(AF_INET, SOCK_DGRAM)
udpSocket.bind(('', udpPort))

# build connection with the server and send message to it
clientSocket.connect(serverAddress)

##################################################
#                 HELPER FUNCTIONS               #
##################################################
def send_and_get_response(message):
    clientSocket.sendall(message.encode())
    data = clientSocket.recv(1024)
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
        if clientSocket:
            clientSocket.close()
        # Close the UDP connection
        if udpSocket:
            global listening_on_udp
            listening_on_udp = False
            time.sleep(0.5)  # Give the thread time to exit gracefully
            udpSocket.close()

    except Exception as e:
        print(f"Error closing connections: {e}")
##################################################
#                       MAIN                     #
##################################################

################## COLLECT USERNAME ##################
client_username = ""

print("Please Login")
while True:
    username = input("Username: ")
    response = send_and_get_response(f"[loginusername] {username}")
    _, status_code, message, _ = split_response(response)
    
    if status_code == "200":
        client_username = username
        break
    elif status_code == "404":
        print(f"{message}")

################## COLLECT PASSWORD ##################
while True:
    password = input("Password: ")
    if password.strip() == '': # assumes a password can't be all whitespaces
        continue
    response = send_and_get_response(f"[loginpassword] {password} {local_ip} {udpPort}")
    _, status_code, message, _ = split_response(response)
    
    if status_code == "200": # SUCCESS
        break
    elif status_code == "401": # UNAUTHORISED
        print(f"{message}")
    elif status_code == "403": # FORBIDDEN
        print(f"{message}")
        clientSocket.close()
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
print("Welcome to Tessenger!")
print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)

server_commands = ["/msgto", "/activeuser", "/creategroup", "/joingroup", "/groupmsg", "/logout"]
peer_commands = ["/p2pvideo"]

def send_server_command(request):
    clientSocket.sendall(request.encode())    

def send_peer_command(request):
    parts = request.strip().split()
    command = parts[0]
    
    if command == "/p2pvideo":
        if len(parts) != 3:
            print("Error: Invalid format. Usage: /p2pvideo username filename")
            print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)
            return

        recipient, filename = parts[1], parts[2]
        # Check if file exists
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' does not exist.")
            print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)
            return

        # Check if recipient is active and get their UDP details
        response = send_and_get_response("/activeuser")
        _, _, _, active_users_data = split_response(response)

        if recipient in active_users_data["client_ips"] and recipient in active_users_data["udp_ports"]:
            recipient_ip = active_users_data["client_ips"][recipient]
            recipient_port = int(active_users_data["udp_ports"][recipient])
        else:
            print(f"Error: Recipient '{recipient}' is not active.")
            print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)
            return
        
        send_file_over_udp(filename, recipient_ip, recipient_port)
        print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)

def send_file_over_udp(filename, audience_ip, audience_udp_port):
    global client_username
    sending_socket = socket(AF_INET, SOCK_DGRAM)
    
    initial_packet = f"initiate_transfer {filename} {client_username}"
    sending_socket.sendto(initial_packet.encode(), (audience_ip, audience_udp_port))
    
    with open(filename, 'rb') as file:
        data = file.read(1024) # Read in chunks of 1024 bytes
        while data:
            sending_socket.sendto(data, (audience_ip, audience_udp_port))
            time.sleep(0.00001)
            data = file.read(1024)
            
    print(f"{filename} has been uploaded.")
    end_signal = 'EOF'
    sending_socket.sendto(end_signal.encode(), (audience_ip, int(audience_udp_port)))
    
    sending_socket.close()


def listening_for_udp(socket):
    global listening_on_udp
    while listening_on_udp:
        try:
            data, _ = socket.recvfrom(1024)
            packet = data.decode()
            if packet.startswith("initiate_transfer"):
                filename = packet.split()[1]
                username = packet.split()[2]
                with open(f"{username}_{filename}", 'wb') as f:
                    try:
                        while True:
                            video_data, _ = socket.recvfrom(1024)
                            if video_data.endswith(b'EOF'):
                                f.write(video_data[:-len(b'EOF')]) # NOTE Change this
                                print(f"\nReceived {filename} from {username}")
                                print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)
                                break
                            f.write(video_data)
                    except KeyboardInterrupt:
                        print("Receiving interrupted by user")
        except OSError as e:
            # Handle socket closure
            if not listening_on_udp:
                break
            print(f"Error in UDP communication: {e}")

threading.Thread(target=listening_for_udp, args=(udpSocket,), daemon=True).start()

while True:
    readables, _, _ = select.select([sys.stdin, clientSocket], [], [])
    
    for readable in readables:
        if readable is sys.stdin:
            request = sys.stdin.readline()
            
            if request.strip() == '':
                cont = input("Input is empty, do you want to continue (y/n)? ")
                if cont == 'y':
                    # don't send the packet and continue
                    print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)
                    continue
                elif cont == 'n':
                    clientSocket.sendall(request.encode())
                    close_connections()
                    sys.exit(0)
                else:
                    print("User did not enter y/n, continuing...")
                    print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)
                    continue
            
            command = request.split()[0]
            if command in server_commands:
                send_server_command(request)
            elif command in peer_commands:
                send_peer_command(request)
            else:
                print("Error: Invalid command!")
                print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)
                continue
            
        if readable is clientSocket:
            response = clientSocket.recv(1024).decode()
            process_response(response)
            print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)


