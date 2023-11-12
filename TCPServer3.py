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
def generate_response(command, statusCode, clientMessage = "", data={}):
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
#               Setup Datastructures             #
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

# threads datastructure - maps username to thread object
threads = {}

# maps username to timestamp since active
active_users = {}

# maps groupname to group
groups = {}

##################################################
#                LOGGING FUNCTIONS               #
##################################################
#reset user log
with open('userlog.txt', 'w') as file:
    pass

active_user_no = 1
def write_user_log(username, client_ip, udp_port):
    # NOTE does this need to be persistent? or non-persistent?
    global active_user_no
    with open('userlog.txt', 'a') as file:
        file.write(f"{active_user_no}; {generate_formatted_time()}; {username}; {client_ip}; {udp_port}\n")
    active_user_no += 1

message_counter = 1
def write_message_log(username_to, timestamp, message):
    global active_user_no
    with open('messagelog.txt', 'a') as file:
        file.write(f"{message_counter}; {timestamp}; {username_to}; {message}\n")
    active_user_no += 1

##################################################
#                   Group Class                  #
##################################################
class GroupChat():
    def __init__(self, name, owner, users):
        # Initialise Variables
        self.name = name
        self.users_joined = {}
        self.users_joined[owner] = True
        self.message_number = 1
        for user in users:
            self.users_joined[user] = False
        
        self.log_file_name = f"{self.name}_messagelog.txt"
        with open(self.log_file_name, 'w') as log_file:
            pass
    
    def send_message(self, sender, message, timestamp):
        # send to everyone but the sender
        global threads
        global active_users
        for username, joined in self.users_joined.items():
            if joined and username in active_users and username != sender: # if user is joined, and user is active # NOTE check this shit im too tired to know what might be wrong
                recipient_thread = threads.get(username)
                response = generate_response("incominggroupmsg", "200", f"{sender} issued a message in group chat {self.name}:\n{timestamp}; {sender}; {message}").encode()
                recipient_thread.clientSocket.send(response)# send the message to the recipient
    
    def log_message(self, timestamp, sender, message):
        log_line = f"{self.message_number}; {timestamp}; {sender}; {message}"
        with open(self.log_file_name, 'a') as log_file:
            log_file.write(log_line + "\n")
            
        self.message_number += 1

    def accept_invite(self, user):
        self.users_joined[user] = True
        
    def has_user_joined(self, user):
        return self.users_joined.get(user, False)
    
    def is_user_invited(self, user):
        return True if user in self.users_joined.keys() else False

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
            if request == '\n' or request == '':
                global active_users
                self.clientAlive = False
                active_users.pop(self.username, None)
                # NOTE Remove the line from active users
                print("===== the user disconnected - ", clientAddress)
                break
            
            # get the type of message
            requestCommand = request.split()[0]
            
            # handle message from the client
            if requestCommand == '[loginusername]':
                print("[recv] New login request for user: " + request.split()[1])
                self.process_username(request.split()[1])
                
            elif requestCommand == '[loginpassword]':
                print("[recv] New password attempt for user: " + self.username)
                parts = request.split()
                
                if len(request.split()) != 4:
                    print(f"Bad password request {request}")
                    generate_response("loginpassword", "500", "Server Error: Bad password request")
                    continue
                
                password = parts[1]
                client_ip = parts[2]
                udp_port = parts[3]
                
                self.process_password(password, client_ip, udp_port)       
                         
            elif requestCommand == '/msgto':
                print("[recv] New message send attempt by user: " + self.username)
                self.process_msgto(request)
                
            elif requestCommand == '/activeuser':
                print("[recv] New active user request by user: " + self.username)
                self.process_activeuser()
                
            elif requestCommand == '/creategroup':
                print("[recv] New create group user request by user: " + self.username)
                self.process_creategroup(request)
                
            elif requestCommand == '/joingroup':
                print("[recv] New create group join request by user: " + self.username)
                self.process_joingroup(request)
                
            elif requestCommand == '/groupmsg':
                print("[recv] New create group message request by user: " + self.username)
                self.process_groupmsg(request)
                
            elif requestCommand == '/logout':
                print("[recv] New logout request by user: " + self.username)
                # NOTE: Implement logout
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


    def process_password(self, password, client_ip, udp_port):
        if self.is_user_blocked(): # if the user is blocked
            self.clientAlive = False
            response = generate_response("loginpassword", "403", "Your account is blocked due to multiple login failures. Please try again later")
            
        elif password == self.password: # if the password is correct
            response = generate_response("loginpassword", "200", "") 
            write_user_log(self.username, client_ip, udp_port)
            failed_attempts[self.username] = 0
            global threads
            threads[self.username] = self
            active_users[self.username] = generate_formatted_time()
            
        else: # if the password is incorrect
            response = generate_response("loginpassword", "401", "Invalid Password.")
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
        
        # check if the recipient exists
        # NOTE does the recipient need to be active? - probably
        if username_to not in threads:
            self.clientSocket.send(generate_response("msgto", "404", "Recipient Not Found!").encode())
            return
    
        # find the client thread, send a message to that client
        timestamp = generate_formatted_time()
        recipient_thread = threads[username_to]
        recipient_thread.clientSocket.send(generate_response("incomingmessage", "200", f"{timestamp}, {username_from}: {content}").encode()) # send the message to the recipient
        write_message_log(username_to, timestamp, content)
    
        self.clientSocket.send(generate_response("msgto", "200", f"message sent at {generate_formatted_time()}.").encode())
    
    def process_activeuser(self):
        #assuming log file is kept correctly
        active_users = []
        with open("userlog.txt", "r") as file:
            active_users = file.readlines()
        
        # NOTE If we change sending messages to json - we can structure the other data nicely instead of having to do post processing later (i.e. splitting in )
        messages = []
        for line in active_users:
            parts = line.split('; ')
            timestamp = parts[1]
            user = parts[2]
            ip = parts[3]
            port = parts[4]
        
            if user != self.username:
                messages.append(f"{user}, active since {timestamp}.; {ip}; {port}") # NOTE need to fix this - and change it to JSON???

            
        if len(messages) == 0:
            self.clientSocket.send(generate_response("activeuser", "200", "no other active user"))
        else:
            self.clientSocket.send(generate_response("activeuser", "200", '\n'.join(messages)).encode())
    
    def process_creategroup(self, request):
        # NOTE: OVERALL, check if all the status codes are correct
        parts = request.split()
        
        if len(parts) < 3:
            self.clientSocket.send(generate_response("creategroup", "400", "Error: Not enough arguments for /creategroup."))
        
        chat_name = parts[1]
        recipients = parts[2:]
        owner = self.username
        
        # check if any of the recipients are not in active users
        global active_users
        for r in recipients:
            if r not in active_users.keys():
                self.clientSocket.send(generate_response("creategroup", "404", f"Error: {r} is offline, or an invalid username."))

        # check if the groupname already exists
        if chat_name in groups.keys():
            self.clientSocket.send(generate_response("creategroup", "409", f"a group chat (Name: {chat_name}) already exist."))
        
        # if the groupname is invalid (contains letters otuside of a-z, A-Z and digit 0-9)
        if not chat_name.isalnum():
            self.clientSocket.send(generate_response("creategroup", "400", "Error: Group name is invalid. Use only letters and digits."))
            return
        
        # initialise a group object
        group = GroupChat(chat_name, owner, recipients)
        global groups
        groups[chat_name] = group
        
        # Send response for success
        recipients_with_owner = [owner] + recipients
        self.clientSocket.send(generate_response("creategroup", "200", f"Group chat room has been created, room name: {chat_name}, users in this room: {' '.join(recipients_with_owner)}")) # NOTE: check if the owner should be in the room
    
    def process_joingroup(self, request):
        # Split the request to get the group name
        parts = request.split() 
        
        # Check if the request is correctly formatted
        if len(parts) != 2:
            self.clientSocket.send(generate_response("joingroup", "400", "Error: Invalid command format. Usage: /joingroup groupname"))
            return

        group_name = parts[1]
        username = self.username

        # Check if the group name exists
        global groups
        if group_name not in groups:
            self.clientSocket.send(generate_response("joingroup", "404", "Error: Group chat does not exist."))
            return

        group = groups[group_name]

        # Check if the user is invited to the group
        if username not in group.users_joined:
            self.clientSocket.send(generate_response("joingroup", "403", "Error: You are not invited to this group chat."))
            return

        # Check if the user has already joined the group
        if group.has_user_joined(username):
            self.clientSocket.send(generate_response("joingroup", "409", "Error: You are already in this group chat."))
            return

        # Add the user to the group and send appropriate message to client
        group.accept_invite(username)
        self.clientSocket.send(generate_response("joingroup", "200", f"You have successfully joined the group chat '{group_name}'."))

    def process_groupmsg(self, request):
        parts = request.split(' ', 2)
        
        if len(parts) < 3:
            self.clientSocket.send(generate_response("groupmsg", "400", "Error: Invalid command format. Usage: /groupmsg groupname message"))
            return
        
        group_name = parts[1]
        message = parts[2]
        
        # check if group chat exists - else reply "Error: The group chat [name] does not exist"
        global groups
        if group_name not in groups:
            self.clientSocket.send(generate_response("groupmsg", "404", f"Error: The group chat {group_name} does not exist."))
            return
        
        group = groups[group_name]
        
        # check if the user is invited - else reply "Error: You are not in this group chat."
        if not group.is_user_invited(self.username):
            self.clientSocket.send(generate_response("groupmsg", "403", "Error: You are not in this group chat."))
            return

        # check if user has joined - else reply "Error: you are invited but have not yet joined the group chat."
        if not group.has_user_joined(self.username):
            self.clientSocket.send(generate_response("groupmsg", "403", "Error: You are invited but have not yet joined the group chat."))
            return
        
        timestamp = generate_formatted_time()
        group.log_message(timestamp, self.username, message)
        self.clientSocket.send(generate_response("groupmsg", "200", "Group chat message sent."))
    
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
