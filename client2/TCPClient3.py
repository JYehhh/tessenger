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
            udpSocket.close()

    except Exception as e:
        print(f"Error closing connections: {e}")
##################################################
#                       MAIN                     #
##################################################

################## COLLECT USERNAME ##################
print("Please Login")
while True:
    username = input("Username: ")
    response = send_and_get_response(f"[loginusername] {username}")
    _, status_code, message, _ = split_response(response)
    
    if status_code == "200":
        break
    elif status_code == "404":
        print(f"{message}")

################## COLLECT PASSWORD ##################
while True:
    password = input("Password: ")
    # if password == '\n' or password == '':
    #     continue # NOTE what about empty passwords
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

################## PROCESS UDP RESPONSES ##################
def listen_for_udp():
    while True:
        try:
            data, addr = udpSocket.recvfrom(1024)  # buffer size is 1024 bytes
            print(f"Received data from {addr}")
            # Process the received data
        except Exception as e:
            print(f"Error in UDP communication: {e}")
            break

# Running the UDP listener in a separate thread
threading.Thread(target=listen_for_udp, daemon=True).start()

################## USE SELECT TO WATCH INPUT ##################
print("Welcome to Tessenger!")
print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)

server_commands = ["/msgto", "/activeuser", "/creategroup", "/joingroup"," /groupmsg", "/logout"]
peer_commands = ["/p2pvideo"]

def send_server_command(request):
    clientSocket.sendall(request.encode())    

def send_peer_command(request):
    parts = request.strip().split()
    command = parts[0]
    
    if command == "/p2pvideo":
        if len(parts) != 3:
            print("Error: Invalid format. Usage: /p2pvideo username filename")
            return

        recipient, filename = parts[1], parts[2]

        # Check if file exists
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' does not exist.")
            return

        # Request active users list from the server
        response = send_and_get_response("/activeuser")
        _, _, _, active_users_data = split_response(response)

        # Check if recipient is active and get their UDP details
        if recipient in active_users_data["client_ips"] and recipient in active_users_data["udp_ports"]:
            recipient_ip = active_users_data["client_ips"][recipient]
            recipient_port = int(active_users_data["udp_ports"][recipient])
        else:
            print(f"Error: Recipient '{recipient}' is not active.")
            return

        # Send file over UDP
        send_file_over_udp(filename, recipient_ip, recipient_port)
        print(f"{filename} has been uploaded to {recipient}.")

def send_file_over_udp(filename, ip, port):
    with open(filename, 'rb') as file:
        data = file.read(1024)  # Read in chunks of 1024 bytes
        while data:
            udpSocket.sendto(data, (ip, port))
            data = file.read(1024)

while True:
    readables, _, _ = select.select([sys.stdin, clientSocket], [], [])
    
    for readable in readables:
        if readable is sys.stdin:
            request = sys.stdin.readline()
            
            if request == '' or request == '\n': # NOTE might have to add a check if it's all whitepsace???
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
            
            
            command = request.split[0]
            if command in server_commands:
                send_server_command(request)
            elif command in peer_commands:
                send_peer_command(request)
            else:
                print("Error: Invalid command!")
                continue
            
        if readable is clientSocket:
            response = clientSocket.recv(1024).decode()
            process_response(response)
            print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)


