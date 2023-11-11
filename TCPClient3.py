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


##################################################
#                 SETUP CONNECTION               #
##################################################

#Server would be running on the same host as Client
if len(sys.argv) != 3:
    print("\n===== Error usage, python3 TCPClient3.py SERVER_IP SERVER_PORT ======\n")
    exit(0)
serverHost = sys.argv[1]
serverPort = int(sys.argv[2])
serverAddress = (serverHost, serverPort)

# define a socket for the client side, it would be used to communicate with the server
clientSocket = socket(AF_INET, SOCK_STREAM)

# build connection with the server and send message to it
clientSocket.connect(serverAddress)


##################################################
#                 HELPER FUNCTIONS               #
##################################################
def send_request(message):
    clientSocket.sendall(message.encode())
    data = clientSocket.recv(1024)
    return data.decode()

def split_response(response):
    parts = response.split(";")
    if len(parts) < 3:
        print("Critical Server Error: Bad Response Format")
        sys.exit(1)

    command, status_code, message = parts
    return command, status_code, message

##################################################
#                       MAIN                     #
##################################################

################## COLLECT USERNAME ##################
print("Please Login")
while True:
    username = input("Username: ")
    response = send_request(f"[loginusername] {username}")
    _, status_code, message = split_response(response)
    
    if status_code == "200":
        break
    elif status_code == "404":
        print(f"{message}")

################## COLLECT PASSWORD ##################
while True:
    password = input("Password: ")
    response = send_request(f"[loginpassword] {password}")
    _, status_code, message = split_response(response)
    
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

def process_response(response):
    command, status_code, message = split_response(response)
    if command == "incomingmessage":
        print(f"{message}")
    elif command == "msgto":
        print(f"{message}")
    elif command == "unknown":
        print(f"{message}")
    else:
        print(f"Critical Server Error: Bad Response Command {command}")
        sys.exit(1)
        
################## USE SELECT TO WATCH INPUT ##################
print("Welcome to Tessenger!")
print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)

while True:
    readables, _, _ = select.select([sys.stdin, clientSocket], [], [])
    
    for readable in readables:
        if readable is sys.stdin:
            request = sys.stdin.readline()
            clientSocket.sendall(request.encode())
        if readable is clientSocket:
            response = clientSocket.recv(1024).decode()
            process_response(response)
            print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ", end = '', flush=True)
    