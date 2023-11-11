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
#                 Helper Functions               #
##################################################
def generate_response(command, statusCode, clientMessage = ""):
    # Status Codes
        # Success (200): Indicates successful execution of a command.
        # Client Error (400): General client-side error, such as malformed request or missing arguments.
        # Unauthorized (401): For invalid login attempts or unauthorized access attempts.
        # Forbidden (403): For blocked users or access to unauthorized commands.
        # Not Found (404): User or resource (e.g., group chat) not found.
        # Conflict (409): For conflicts, like trying to create an already existing group chat.
        # Internal Server Error (500): General server-side error.
    return f"{command};{statusCode};{clientMessage}"

def generate_formatted_time():
    return f"{time.strftime('%d %b %Y %H:%M:%S', time.localtime())}"

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
        file.write(f"{active_user_no}; {generate_formatted_time()}; {username}\n")
    active_user_no += 1

message_counter = 1
def write_message_log(username_to, timestamp, message):
    global active_user_no
    with open('messagelog.txt', 'a') as file:
        file.write(f"{message_counter}; {timestamp}; {username_to}; {message}\n")
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
        request = ''
        
        while self.clientAlive:
            # use recv() to receive message from the client
            data = self.clientSocket.recv(1024)
            request = data.decode()

            # if the message from client is empty, the client would be off-line then set the client as offline (alive=Flase)
            if request == '':
                self.clientAlive = False
                print("===== the user disconnected - ", clientAddress)
                break
            
            # get the type of message
            requestCommand = request.split()[0]
            
            # handle message from the client
            if requestCommand == '[loginusername]':
                print("[recv] New login request for username: " + request.split()[1])
                self.process_username(request.split()[1])
                
            elif requestCommand == '[loginpassword]':
                print("[recv] New password attempt for username: " + self.username)
                self.process_password(request.split()[1])       
                         
            elif requestCommand == '/msgto':
                print("[recv] New message send attempt by username: " + self.username)
                self.process_msgto(request)
                
            elif requestCommand == '/activeuser':
                # /activeuser
                pass
            elif requestCommand == '/creategroup':
                # /creategroup groupname username1 username2 ..
                pass
            elif requestCommand == '/joingroup':
                # /joingroup groupname
                pass
            elif requestCommand == '/groupmsg':
                # /groupmsg groupname message
                pass
            elif requestCommand == '/logout':
                # /logout
                self.clientAlive = False
                pass
            else:
                self.process_invalid_command()
                
    
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
            response = generate_response("loginusername", "200", "") 
        else:
            response = generate_response("loginusername", "404", "Invalid Username, please try again.") 
        
        print('[send] ' + response);
        self.clientSocket.send(response.encode())


    def process_password(self, password):
        if self.is_user_blocked(): # if the user is blocked
            self.clientAlive = False
            response = generate_response("loginpassword", "403", "Your account is blocked due to multiple login failures. Please try again later")
            
        elif password == self.password: # if the password is correct
            response = generate_response("loginpassword", "200", "") 
            write_user_log(self.username)
            failed_attempts[self.username] = 0
            global threads
            threads[self.username] = self
            
        else: # if the password is incorrect
            response = generate_response("loginpassword", "401", "")
            failed_attempts[self.username] += 1
            
            if failed_attempts[self.username] == attempts_cap:
                self.clientAlive = False
                failed_attempts[self.username] = 0
                blocked_users[self.username] = time.time()
                response = generate_response("loginpassword", "403", "Invalid Password. Your account has been blocked. Please try again later")
                
        print('[send] ' + response);
        self.clientSocket.send(response.encode())

    def process_msgto(self, request):
        parts = request.split(' ', 2)
        
        # check if there are enough arguments
        if len(parts) < 3:
            self.clientSocket.send(generate_response("msgto", "400", "Invalid command format. Usage: /msgto USERNAME MESSAGE_CONTENT").encode())
            return
        
        # collect arguments 
        username_from = self.username
        username_to = parts[1]
        content = parts[2]
        
        # NOTE check if the content is all whitespace - will implement later
        
        # find the client thread, send a message to that client
        if username_to not in threads:
            self.clientSocket.send(generate_response("msgto", "404", "Recipient Not Found!").encode())
            return
        else:
            timestamp = generate_formatted_time()
            recipient_thread = threads[username_to]
            recipient_thread.clientSocket.send(generate_response("incomingmessage", "200", f"{timestamp}, {username_from}: {content}").encode()) # send the message to the recipient
            write_message_log(username_to, timestamp, content)
        
        self.clientSocket.send(generate_response("msgto", "200", f"message sent at {generate_formatted_time()}.").encode())
    
    def process_invalid_command(self):
        self.clientSocket.send(generate_response("unknown", "404", "Error: Invalid command!").encode())
    
print("\n===== Server is running =====")
print("===== Waiting for connection request from clients...=====")


while True:
    #implement multithreding
    serverSocket.listen()
    clientSockt, clientAddress = serverSocket.accept()
    clientThread = ClientThread(clientAddress, clientSockt)
    clientThread.start()
