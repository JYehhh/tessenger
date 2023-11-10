"""
    Python 3
    Usage: python3 TCPClient3.py localhost 12000
    coding: utf-8
    
    Author: Wei Song (Tutor for COMP3331/9331)
"""
from socket import *
import sys

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

def send_message(message):
    clientSocket.sendall(message.encode())
    data = clientSocket.recv(1024)
    return data.decode()

################## COLLECT USERNAME
print("Please Login")
while True:
    username = input("Username: ")
    received = send_message(f"[loginusername] {username}")
    
    if received == "user found":
        break
    elif received == "user not found":
        print("Invalid Username, please try again.")

# COLLECT PASSWORD``
while True:
    password = input("Password: ")
    received = send_message(f"[loginpassword] {password}")
    
    if received == "password correct":
        break
    elif received == "account blocked":
        print("Invalid Password. Your account has been blocked. Please try again later")
        clientSocket.close()
        sys.exit(0)
        # NOTE maybe change this
    elif received == "account on cooldown":
        print("Your account is blocked due to multiple login failures. Please try again later")
        clientSocket.close()
        sys.exit(0)
    elif received == "password incorrect":
        print("Invalid Password. Please try again")

print("Welcome to Tessenger!")
print("Enter one of the following commands (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout): ")

while True:
    message = input("===== Please type any message you want to send to server: =====\n")
    received = send_message(message)
    
    # parse the message received from server and take corresponding actions
    if received == "":
        print("[recv] Message from server is empty!")
    else:
        print("[recv] Invalid command - please enter one of the following (/msgto, /activeuser, /creategroup, /joingroup, /groupmsg, /logout)")
        
    ans = input('\nDo you want to continue(y/n) :')
    if ans == 'y':
        continue
    else:
        break

# close the socket
clientSocket.close()
