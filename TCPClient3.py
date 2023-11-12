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
def send_request(message):
    clientSocket.sendall(message.encode())
    # data = clientSocket.recv(1024)
    # return data.decode()

def process_response(response):
    try:
        response_data = json.loads(response)
        command = response_data.get("command")
        status_code = response_data.get("statusCode")
        message = response_data.get("clientMessage")
        data = response_data.get("data")
    except json.JSONDecodeError:
        print("Error: Received an invalid JSON response.")
        
    
    parts = response.split(";")
    if len(parts) < 3:
        print("Critical Server Error: Bad Response Format")
        sys.exit(1)

    command, status_code, message = parts
    return command, status_code, message, data

##################################################
#                       MAIN                     #
##################################################

################## COLLECT USERNAME ##################
print("Please Login")
while True:
    username = input("Username: ")
    response = send_request(f"[loginusername] {username}")
    _, status_code, message, _ = process_response(response)
    
    if status_code == "200":
        break
    elif status_code == "404":
        print(f"{message}")

################## COLLECT PASSWORD ##################
while True:
    password = input("Password: ")
    # if password == '\n' or password == '':
    #     continue # NOTE what about empty passwords
    response = send_request(f"[loginpassword] {password} {local_ip} {udpPort}")
    _, status_code, message, _ = process_response(response)
    
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
    command, _, message, _ = process_response(response)
    if command == "incomingmessage":
        print(f"{message}")
    elif command == "incominggroupmsg":
        print(f"{message}")
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
    elif command == "unknown":
        print(f"{message}")
    else:
        print(f"Critical Server Error: Bad Response Command {command}")
        sys.exit(1)

################## PROCESS RESPONSES ##################
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
                    sys.exit(0)
                else:
                    print("User did not enter y/n, continuing...")
                    print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)
                    continue
                
            clientSocket.sendall(request.encode())
            
        if readable is clientSocket:
            response = clientSocket.recv(1024).decode()
            process_response(response)
            print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)

# create UDP receiving socket in main
# create thread that runs a function
# constant listening for bytes sent over udp - via socket library - lab code.

# implement one funciton in server to get credentials and UDP port number of the other client - contacts server

