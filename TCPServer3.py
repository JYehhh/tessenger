"""
    Sample code for Multi-Threaded Server
    Python 3
    Usage: python3 TCPserver3.py localhost 12000
    coding: utf-8
    
    Author: Wei Song (Tutor for COMP3331/9331)
"""
from socket import *
from threading import Thread
import sys, select
import time

##################################################
#                Setup Host and Port             #
##################################################
if len(sys.argv) != 3:
    print("\n===== Error usage, python3 TCPServer3.py SERVER_PORT ATTEMPTS_BEFORE_LOCK ======\n")
    exit(0)
serverHost = "127.0.0.1"
serverPort = int(sys.argv[1])
serverAddress = (serverHost, serverPort)

try:
    attempts_cap = int(sys.argv[2])
except ValueError:
    print("ATTEMPTS_BEFORE_LOCK must be an integer.")
    sys.exit(1)

if not 1 <= attempts_cap <= 5:
    print(f"Invalid number of allowed failed consecutive attempt: {attempts_cap}")
    sys.exit(1)

# define socket for the server side and bind address
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind(serverAddress)

##################################################
#          Setup Datastructures and Logs         #
##################################################

# load in credentials .txt into a dict
credentials = {}
failed_attempts = {}
blocked_users = {}
with open('credentials.txt') as file:
    for l in file.readlines():
        username = l.split()[0]
        password = l.split()[1]
        credentials[username] = password
        failed_attempts[username] = 0

# setup user log
active_user_no = 1
def write_user_log(username):
    # NOTE does this need to be persistent? or non-persistent?
    global active_user_no
    with open('userlog.txt', 'a') as file:
        file.write(f"{active_user_no}; {time.strftime('%d %b %Y %H:%M:%S', time.localtime())}; {username}\n")
    active_user_no += 1

# threads datastructure
threads = {}

##################################################
#                  Thread Class                  #
##################################################
class ClientThread(Thread):
    def __init__(self, clientAddress, clientSocket):
        Thread.__init__(self)
        self.clientAddress = clientAddress
        self.clientSocket = clientSocket
        self.clientAlive = False
        self.username = None
        self.password = None
        
        print("===== New connection created for: ", clientAddress)
        self.clientAlive = True
        
    def run(self):
        message = ''
        
        while self.clientAlive:
            # use recv() to receive message from the client
            data = self.clientSocket.recv(1024)
            message = data.decode()

            # if the message from client is empty, the client would be off-line then set the client as offline (alive=Flase)
            if message == '':
                self.clientAlive = False
                print("===== the user disconnected - ", clientAddress)
                break
            
            # get the type of message
            messageType = message.split()[0]
            
            # handle message from the client
            if messageType == '[loginusername]':
                # [loginusername] USERNAME
                print("[recv] New login request for username: " + message.split()[1])
                self.process_username(message.split()[1])
            elif messageType == '[loginpassword]':
                # [loginpassword] PASSWORD
                print("[recv] New password attempt for username: " + self.username)
                self.process_password(message.split()[1])
            elif messageType == '/msgto':
                # /msgto USERNAME MESSAGE_CONTENT
                
                
                
                # Error check to make sure that arguments are correct
                # find the client thread, and send a message to that client
                pass
            elif messageType == '/activeuser':
                # /activeuser
                pass
            elif messageType == '/creategroup':
                # /creategroup groupname username1 username2 ..
                pass
            elif messageType == '/joingroup':
                # /joingroup groupname
                pass
            elif messageType == '/groupmsg':
                # /groupmsg groupname message
                pass
            elif messageType == '/logout':
                # /logout
                self.clientAlive = False
                pass
            else:
                self.process_invalid_message()
                
    
    #################### CUSTOM API's ####################
    def is_user_blocked(self):
        if self.username == None or self.username not in blocked_users:
            return False
        
        if (time.time() - blocked_users.get(self.username)) < 10:
            return True
        
        return False
    
    def process_username(self, username):
        # check if the username is in the list of usernames, if not, then return user not found, else return user found. 
        if username in credentials.keys():
            self.username = username
            self.password = credentials.get(username)
            message = 'user found'
        else:
            message = 'user not found'
        
        print('[send] ' + message);
        self.clientSocket.send(message.encode())


    def process_password(self, password):
        if self.is_user_blocked(): # if the user is blocked
            self.clientAlive = False
            message = 'account on cooldown'
        elif password == self.password: # if the password is correct
            message = 'password correct'
            write_user_log(self.username)
            failed_attempts[self.username] = 0
            global threads
            threads[self.username] = self
        else: # if the password is incorrect
            message = 'password incorrect'
            failed_attempts[self.username] += 1
            if failed_attempts[self.username] == attempts_cap:
                self.clientAlive = False
                failed_attempts[self.username] = 0
                blocked_users[self.username] = time.time()
                message = 'account blocked'
        print('[send] ' + message);
        self.clientSocket.send(message.encode())

    def process_invalid_message(self):
        message = "invalid message"
        print('[send] ' + message);
        self.clientSocket.send(message.encode())

print("\n===== Server is running =====")
print("===== Waiting for connection request from clients...=====")


while True:
    #implement multithreding
    serverSocket.listen()
    clientSockt, clientAddress = serverSocket.accept()
    clientThread = ClientThread(clientAddress, clientSockt)
    clientThread.start()
