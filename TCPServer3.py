"""
    Sample code for Multi-Threaded Server
    Python 3
    Usage: python3 TCPServer3.py SERVER_PORT ATTEMPTS_BEFORE_LOCK
    coding: utf-8
    
    Author: Jerry Yeh (z5362570) - Adapted from Wei Song (Tutor for COMP3331/9331)
"""

from socket import *
from threading import Thread
import sys, select
import time
import json


##################################################
#                 Helper Functions               #
##################################################
# Socket and Server Constants:
SOCKET_BUFFER_SIZE = 1024

# File Paths:
CREDENTIALS_FILE = 'credentials.txt'
USER_LOG_FILE = 'userlog.txt'
MESSAGE_LOG_FILE = 'messagelog.txt'

# Status Code Constants:
SUCCESS = 200
CLIENT_ERROR = 400
UNAUTHORIZED = 401
FORBIDDEN = 403
NOT_FOUND = 404
CONFLICT = 409
INTERNAL_SERVER_ERROR = 500

##################################################
#             Global Helper Functions            #
##################################################
def generate_response(command, statusCode, clientMessage = "", data={}):
    response = {
        "command": command,
        "statusCode": statusCode,
        "clientMessage": clientMessage,
        "data": data
    }
    return json.dumps(response)

def generate_formatted_time():
    return f"{time.strftime('%d %b %Y %H:%M:%S', time.localtime())}"

def display_response(response):
    response_data = json.loads(response)
    command = response_data.get("command")
    status_code = response_data.get("statusCode")
    message = response_data.get("clientMessage")
    data = response_data.get("data")
    
    if data:
        print("[send] " + f"Response for command {command}, issued with status code [{status_code}] and message '{message}'. Additional data attached.")
    else:
        print("[send] " + f"Response for command {command}, issued with status code [{status_code}] and message '{message}'. No additional data.")
    

##################################################
#                Setup Host and Port             #
##################################################
if len(sys.argv) != 3:
    print("\n===== Error usage, python3 TCPServer3.py SERVER_PORT ATTEMPTS_BEFORE_LOCK ======\n")
    exit(0)
server_host = "127.0.0.1"
server_port = int(sys.argv[1])
server_address = (server_host, server_port)

try:
    attempts_cap = int(sys.argv[2])
except ValueError:
    print("Error: ATTEMPTS_BEFORE_LOCK must be an integer.")
    sys.exit(1)

if not 1 <= attempts_cap <= 5:
    print(f"Error: Invalid number of allowed failed consecutive attempt: {attempts_cap}")
    sys.exit(1)

# define socket for the server side and bind address
server_socket = socket(AF_INET, SOCK_STREAM)
server_socket.bind(server_address)

##################################################
#               Setup Datastructures             #
##################################################
# load in credentials .txt into a dict
credentials = {}
failed_attempts = {}
blocked_users = {}
with open(CREDENTIALS_FILE) as file:
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
    global active_user_no
    with open(USER_LOG_FILE, 'a') as file:
        file.write(f"{active_user_no}; {generate_formatted_time()}; {username}; {client_ip}; {udp_port}\n")
    active_user_no += 1

#reset user log
with open(MESSAGE_LOG_FILE, 'w') as file:
    pass

message_counter = 1
def write_message_log(username_to, timestamp, message):
    global active_user_no
    with open(MESSAGE_LOG_FILE, 'a') as file:
        file.write(f"{message_counter}; {timestamp}; {username_to}; {message}")
    active_user_no += 1

def update_user_log(username_to_remove):
    global active_user_no
    lines = []

    # Read the current user log file
    with open(USER_LOG_FILE, 'r') as file:
        lines = file.readlines()

    # Rewrite the file without the removed user and adjust sequence numbers
    with open(USER_LOG_FILE, 'w') as file:
        new_user_no = 1
        for line in lines:
            parts = line.strip().split('; ')
            if len(parts) < 4 or parts[2] != username_to_remove:
                file.write(f"{new_user_no}; {parts[1]}; {parts[2]}; {parts[3]}; {parts[4]}\n")
                new_user_no += 1

    # Update the global active_user_no
    active_user_no = new_user_no

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
        for username, joined in self.users_joined.items(): # for every user invited
            if joined and username in active_users and username != sender: # if user is joined, and user is active, and is not equal to sender
                recipient_thread = threads.get(username)
                response = generate_response("incominggroupmsg", SUCCESS, f"{sender} issued a message in group chat {self.name}:\n{timestamp}; {sender}; {message}").encode()
                recipient_thread.client_socket.send(response)# send the message to the recipient
    
    def log_message(self, timestamp, sender, message):
        log_line = f"{self.message_number}; {timestamp}; {sender}; {message}"
        with open(self.log_file_name, 'a') as log_file:
            log_file.write(log_line)
            
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
    def __init__(self, client_address, client_socket):
        Thread.__init__(self)
        self.client_address = client_address
        self.client_socket = client_socket
        self.client_alive = False
        self.username = None
        self.password = None
        
        print("===== New connection created for: ", client_address)
        self.client_alive = True
        
    def run(self):
        request = ''
        
        while self.client_alive:
            # use recv() to receive message from the client
            data = self.client_socket.recv(SOCKET_BUFFER_SIZE)
            request = data.decode()

            # if the message from client is empty, the client would be off-line then set the client as offline (alive=Flase)
            if request == '\n' or request == '':
                self.end_client_session()
                break
            
            # get the type of message
            requestCommand = request.split()[0]
            
            # handle message from the client
            if requestCommand == '[loginusername]':
                print("[recv] New login request for user: " + request.split()[1])
                response = self.process_username(request.split()[1])
                
            elif requestCommand == '[loginpassword]':
                print("[recv] New password attempt for user: " + self.username)
                response = self.process_password(request)
                         
            elif requestCommand == '/msgto':
                print("[recv] New message send attempt by user: " + self.username)
                response = self.process_msgto(request)
                
            elif requestCommand == '/activeuser':
                print("[recv] New active user request by user: " + self.username)
                response = self.process_activeuser()
                
            elif requestCommand == '/creategroup':
                print("[recv] New create group user request by user: " + self.username)
                response = self.process_creategroup(request)
                
            elif requestCommand == '/joingroup':
                print("[recv] New create group join request by user: " + self.username)
                response = self.process_joingroup(request)
                
            elif requestCommand == '/groupmsg':
                print("[recv] New create group message request by user: " + self.username)
                response = self.process_groupmsg(request)
                
            elif requestCommand == '/logout':
                print("[recv] New logout request by user: " + self.username)
                response = self.end_client_session()
                
            else:
                response = self.process_invalid_command()
            
            display_response(response)
            self.client_socket.send(response.encode())
    
    #################### HELPER FUNCTIONS ####################
    def end_client_session(self):
        print("===== the user disconnected - ", client_address)
        self.client_alive = False

        global active_users
        active_users.pop(self.username, None)
        
        global threads
        threads.pop(self.username, None)

        update_user_log(self.username)

        # response = generate_response("logout", SUCCESS, "Logout successful. Goodbye!")
        # self.client_socket.send(response.encode())
        return generate_response("logout", SUCCESS, "Logout successful. Goodbye!")

    def is_user_blocked(self):
        if self.username == None or self.username not in blocked_users:
            return False
        
        if (time.time() - blocked_users.get(self.username)) < 10:
            return True
        
        return False
    
    #################### CUSTOM API's ####################
    def process_username(self, username):
        # check if the username is in the list of usernames, if not, then return user not found, else return user found. 
        if username in credentials.keys():
            self.username = username
            self.password = credentials.get(username)
            response = generate_response("loginusername", SUCCESS, "")
        else:
            response = generate_response("loginusername", NOT_FOUND, "Invalid Username, please try again.") 
        
        return response
        # print('[send] ' + response);
        # self.client_socket.send(response.encode())


    def process_password(self, request):
        parts = request.split()
        
        if len(request.split()) != 4:
            print(f"Bad password request {request}")
            return generate_response("loginpassword", INTERNAL_SERVER_ERROR, "Server Error: Malformed password request")
        
        password = parts[1]
        client_ip = parts[2]
        udp_port = parts[3]
        
        if self.is_user_blocked(): # if the user is blocked
            self.client_alive = False
            response = generate_response("loginpassword", FORBIDDEN, "Your account is blocked due to multiple login failures. Please try again later")
            
        elif password == self.password: # if the password is correct
            response = generate_response("loginpassword", SUCCESS, "") 
            write_user_log(self.username, client_ip, udp_port)
            failed_attempts[self.username] = 0
            global threads
            threads[self.username] = self
            active_users[self.username] = generate_formatted_time()
            
        else: # if the password is incorrect
            response = generate_response("loginpassword", UNAUTHORIZED, "Invalid Password.")
            failed_attempts[self.username] += 1
            
            if failed_attempts[self.username] == attempts_cap:
                self.client_alive = False
                failed_attempts[self.username] = 0
                blocked_users[self.username] = time.time()
                response = generate_response("loginpassword", FORBIDDEN, "Invalid Password. Your account has been blocked. Please try again later")

        return response
        # print('[send] ' + response);
        # self.client_socket.send(response.encode())

    def process_msgto(self, request):
        parts = request.split(' ', 2)
        
        # check if there are enough arguments
        if len(parts) < 3:
            # self.client_socket.send(generate_response("msgto", CLIENT_ERROR, "Error: Invalid command format. Usage: /msgto USERNAME MESSAGE_CONTENT").encode())
            return generate_response("msgto", CLIENT_ERROR, "Error: Invalid command format. Usage: /msgto USERNAME MESSAGE_CONTENT")
        
        # collect arguments 
        username_from = self.username
        username_to = parts[1]
        content = parts[2]
        
        # check if the recipient exists
        if username_to not in threads.keys():
            # self.client_socket.send(generate_response("msgto", NOT_FOUND, "Error: Recipient Not Found!").encode())
            return generate_response("msgto", NOT_FOUND, "Error: Recipient Not Found!")
    
        # find the client thread, send a message to that client
        timestamp = generate_formatted_time()
        recipient_thread = threads[username_to]
        recipient_thread.client_socket.send(generate_response("incomingmessage", SUCCESS, f"{timestamp}, {username_from}: {content}").encode()) # send the message to the recipient
        write_message_log(username_to, timestamp, content)
    
        # self.client_socket.send(generate_response("msgto", SUCCESS, f"message sent at {generate_formatted_time()}.").encode())
        return generate_response("msgto", SUCCESS, f"message sent at {generate_formatted_time()}.")
    
    def process_activeuser(self):
        #assuming log file is kept correctly
        client_ips = {}
        udp_ports = {}
        messages = []
        with open("userlog.txt", "r") as file:
            for line in file:
                parts = line.strip().split('; ')
                if len(parts) < 5:  # Ensuring that each line has enough parts
                    print("Server Error: bad userlog line")
                    continue
                user, timestamp, ip, port = parts[2], parts[1], parts[3], parts[4].strip()

                if user != self.username:
                    messages.append(f"{user}, active since {timestamp}. Client IP is {ip} with UDP recieving port: {port}")
                    client_ips[user] = ip
                    udp_ports[user] = port
        
        if len(messages) == 0:
            # self.client_socket.send(generate_response("activeuser", SUCCESS, "no other active user").encode())
            return generate_response("activeuser", SUCCESS, "no other active user")
        else:
            data = {"client_ips": client_ips, "udp_ports": udp_ports}
            # self.client_socket.send(generate_response("activeuser", SUCCESS, '\n'.join(messages), data).encode())
            return generate_response("activeuser", SUCCESS, '\n'.join(messages), data)
        
    def process_creategroup(self, request):
        global groups
        print(request)
        parts = request.split()
        
        if len(parts) < 3:
            # self.client_socket.send(generate_response("creategroup", CLIENT_ERROR, "Error: Not enough arguments for /creategroup.").encode())
            return generate_response("creategroup", CLIENT_ERROR, "Error: Not enough arguments for /creategroup.")
        
        chat_name = parts[1]
        recipients = parts[2:]
        owner = self.username
        
        # check if any of the recipients are not in active users
        global active_users
        for r in recipients:
            if r not in active_users.keys():
                # self.client_socket.send(generate_response("creategroup", NOT_FOUND, f"Error: {r} is offline, or an invalid username.").encode())
                return generate_response("creategroup", NOT_FOUND, f"Error: {r} is offline, or an invalid username.")

        # check if the groupname already exists
        if chat_name in groups.keys():
            # self.client_socket.send(generate_response("creategroup", CONFLICT, f"Error: a group chat (Name: {chat_name}) already exist.").encode())
            return generate_response("creategroup", CONFLICT, f"Error: a group chat (Name: {chat_name}) already exist.")
        
        # if the groupname is invalid (contains letters otuside of a-z, A-Z and digit 0-9)
        if not chat_name.isalnum():
            # self.client_socket.send(generate_response("creategroup", CLIENT_ERROR, "Error: Group name is invalid. Use only letters and digits.").encode())
            return generate_response("creategroup", CLIENT_ERROR, "Error: Group name is invalid. Use only letters and digits.")
        
        # initialise a group object
        group = GroupChat(chat_name, owner, recipients)
        groups[chat_name] = group
        
        # Send response for success
        recipients_with_owner = [owner] + recipients
        # self.client_socket.send(generate_response("creategroup", SUCCESS, f"Group chat room has been created, room name: {chat_name}, users in this room: {' '.join(recipients_with_owner)}").encode())
        return generate_response("creategroup", SUCCESS, f"Group chat room has been created, room name: {chat_name}, users in this room: {' '.join(recipients_with_owner)}")
    
    def process_joingroup(self, request):
        # Split the request to get the group name
        parts = request.split() 
        
        # Check if the request is correctly formatted
        if len(parts) != 2:
            # self.client_socket.send(generate_response("joingroup", CLIENT_ERROR, "Error: Invalid command format. Usage: /joingroup groupname").encode())
            return generate_response("joingroup", CLIENT_ERROR, "Error: Invalid command format. Usage: /joingroup groupname")

        group_name = parts[1]
        username = self.username

        # Check if the group name exists
        global groups
        if group_name not in groups:
            # self.client_socket.send(generate_response("joingroup", NOT_FOUND, "Error: Group chat does not exist.").encode())
            return generate_response("joingroup", NOT_FOUND, "Error: Group chat does not exist.")

        group = groups[group_name]

        # Check if the user is invited to the group
        if username not in group.users_joined:
            # self.client_socket.send(generate_response("joingroup", UNAUTHORIZED, "Error: You are not invited to this group chat.").encode())
            return generate_response("joingroup", UNAUTHORIZED, "Error: You are not invited to this group chat.")

        # Check if the user has already joined the group
        if group.has_user_joined(username):
            # self.client_socket.send(generate_response("joingroup", CONFLICT, "Error: You are already in this group chat.").encode())
            return generate_response("joingroup", CONFLICT, "Error: You are already in this group chat.")

        # Add the user to the group and send appropriate message to client
        group.accept_invite(username)
        # self.client_socket.send(generate_response("joingroup", SUCCESS, f"You have successfully joined the group chat '{group_name}'.").encode())
        return generate_response("joingroup", SUCCESS, f"You have successfully joined the group chat '{group_name}'.")

    def process_groupmsg(self, request):
        parts = request.split(' ', 2)
        
        if len(parts) < 3:
            # self.client_socket.send(generate_response("groupmsg", CLIENT_ERROR, "Error: Invalid command format. Usage: /groupmsg groupname message").encode())
            return generate_response("groupmsg", CLIENT_ERROR, "Error: Invalid command format. Usage: /groupmsg groupname message")
        
        group_name = parts[1]
        message = parts[2]
        
        # check if group chat exists - else reply "Error: The group chat [name] does not exist"
        global groups
        if group_name not in groups:
            # self.client_socket.send(generate_response("groupmsg", NOT_FOUND, f"Error: The group chat {group_name} does not exist.").encode())
            return generate_response("groupmsg", NOT_FOUND, f"Error: The group chat {group_name} does not exist.")
        
        group = groups[group_name]
        
        # check if the user is invited - else reply "Error: You are not in this group chat."
        if not group.is_user_invited(self.username):
            # self.client_socket.send(generate_response("groupmsg", UNAUTHORIZED, "Error: You are not in this group chat.").encode())
            return generate_response("groupmsg", UNAUTHORIZED, "Error: You are not in this group chat.")

        # check if user has joined - else reply "Error: you are invited but have not yet joined the group chat."
        if not group.has_user_joined(self.username):
            # self.client_socket.send(generate_response("groupmsg", UNAUTHORIZED, "Error: Please join the group before sending messages.").encode())
            return generate_response("groupmsg", UNAUTHORIZED, "Error: Please join the group before sending messages.")
        
        timestamp = generate_formatted_time()
        
        global threads
        for user in group.users_joined: # for all the users invited
            if group.has_user_joined(user): # if the user has joined
                if user == self.username or user not in threads.keys(): # skip if self, or if they are not online
                    continue
                recipient_thread = threads[user]
                recipient_thread.client_socket.send(generate_response("incominggroupmsg", SUCCESS, f"{timestamp}, {group_name}, {self.username}: {message}").encode()) # send the message to the recipient
        
        group.log_message(timestamp, self.username, message)
        # self.client_socket.send(generate_response("groupmsg", SUCCESS, "Group chat message sent.").encode())
        return generate_response("groupmsg", SUCCESS, "Group chat message sent.")
    
    def process_invalid_command(self):
        # self.client_socket.send(generate_response("unknown", NOT_FOUND, "Error: Invalid command!").encode())
        return generate_response("unknown", NOT_FOUND, "Error: Invalid command!")
    
print("\n===== Server is running =====")
print("===== Waiting for connection request from clients...=====")


while True:
    server_socket.listen()
    clientSockt, client_address = server_socket.accept()
    clientThread = ClientThread(client_address, clientSockt)
    clientThread.start()
