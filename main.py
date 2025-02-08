import os
import json
import uuid
from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, join_room, leave_room, send
from datetime import datetime

USERS_FILE = 'database/users.json'
CHATS_FILE = 'database/chats.json'
MESSAGES_FILE = 'database/messages.json'

app = Flask(__name__, template_folder="site")
app.secret_key = 'key'

LOGS_FILE = "database/logs.json"

def init_logs():
    if not os.path.exists(LOGS_FILE):
        with open(LOGS_FILE, 'w') as f:
            json.dump([], f)

init_logs()

def log_user_activity():
    user_ip = request.remote_addr
    user_agent = request.headers.get('User-Agent', 'Unknown')  
    username = session.get('username', 'Anonymous')  

    log_entry = {
        "username": username,
        "ip_address": user_ip,
        "user_agent": user_agent,
        "path": request.path,  
        "method": request.method,
        "timestamp": datetime.utcnow().isoformat()  
    }

    logs = load_data(LOGS_FILE)
    logs.append(log_entry)
    save_data(LOGS_FILE, logs)


def load_data(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

def save_data(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def init_db():
    if not os.path.exists('database/users.json'):
        save_data('database/users.json', [])
    if not os.path.exists('database/chats.json'):
        save_data('database/chats.json', [])
    if not os.path.exists('database/messages.json'):
        save_data('database/messages.json', [])

init_db()

def load_users():
    return load_data('database/users.json')

def save_users(users):
    save_data('database/users.json', users)

def load_chats():
    return load_data('database/chats.json')

def save_chats(chats):
    save_data('database/chats.json', chats)

def load_messages():
    return load_data('database/messages.json')

def save_messages(messages):
    save_data('database/messages.json', messages)

socketio = SocketIO(app)

@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    chats = load_chats()
    return render_template('index.html', username=session['username'], chats=chats)

@app.route('/admin', methods=['GET'])
def admin_panel():
    if (session["username"] == "dzrx"):

        users = load_data(USERS_FILE)
        chats = load_data(CHATS_FILE)

        logs = load_data(LOGS_FILE)

        return render_template('admin.html', users=users, chats=chats, logs=logs)
    else:
        return redirect(url_for("home"))

@app.route('/ban_user/<username>', methods=['POST'])
def ban_user(username):
    users = load_users()
    users = [user for user in users if user['username'] != username]
    save_users(users)
    return redirect(url_for('admin_panel'))

@app.route('/ban_chat/<chat_id>', methods=['POST'])
def ban_chat(chat_id):
    chats = load_chats()
    chats = [chat for chat in chats if chat['chat_id'] != chat_id]
    save_chats(chats)

    messages = load_messages()
    messages = [msg for msg in messages if msg['chat_id'] != chat_id]
    save_messages(messages)

    return redirect(url_for('admin_panel'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        users = load_users()
        if any(user['username'] == username for user in users):
            return "Пользователь уже существует!"

        users.append({"username": username, "password": password, "chats": []})
        save_users(users)

        session['username'] = username
        log_user_activity()
        return redirect(url_for('home'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        users = load_users()
        user = next((user for user in users if user['username'] == username and user['password'] == password), None)

        if user:
            session['username'] = username
            return redirect(url_for('home'))

        return "Неверное имя пользователя или пароль!"

    return render_template('login.html')

@app.route('/create_chat', methods=['POST'])
def create_chat():
    if 'username' not in session:
        return redirect(url_for('login'))

    chat_name = request.form['chat_name']
    chats = load_chats()
    chat_id = str(uuid.uuid4())
    chat = {
        "chat_id": chat_id,
        "name": chat_name,
        "users": [session['username']]
    }
    chats.append(chat)
    save_chats(chats)

    users = load_users()
    user = next((user for user in users if user['username'] == session['username']), None)
    if user:
        user['chats'].append(chat_id)
    save_users(users)

    return redirect(url_for('chat', chat_id=chat_id))


@app.route('/chat/<chat_id>')
def chat(chat_id):
    global users_verifed

    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    users_verifed = [
        {'username': 'dzrx', 'is_special': True}
    ]

    chats = load_chats()
    chat = next((chat for chat in chats if chat['chat_id'] == chat_id), None)

    if not chat:
        return "Чат не найден!"

    messages = load_messages()
    chat_messages = [msg for msg in messages if msg['chat_id'] == chat_id]

    chatbot_responses = {
        "/help": "/room - просмотр ID комнаты\n/api - перенаправление на страницу с описанием API\n",
        "/room": f"ID вашей комнаты: {chat_id}",
        "/api": "zalupa nigger"
    }

    @socketio.on('message')
    def chatbot_response(data):
        username = data['username']
        chat_id = data['chat_id']
        content = data['msg'].lower()

        messages = load_messages()
        new_message = {"content": data['msg'], "user": username, "chat_id": chat_id, "timestamp": datetime.utcnow().isoformat()}
        messages.append(new_message)
        save_messages(messages)

        send({'username': username, 'msg': data['msg']}, to=chat_id)

        if content in chatbot_responses:
            bot_reply = chatbot_responses[content]
            bot_message = {"content": bot_reply, "user": "Чатбот", "chat_id": chat_id, "timestamp": datetime.utcnow().isoformat()}
            messages.append(bot_message)
            save_messages(messages)
            send({'username': "Чатбот", 'msg': bot_reply}, to=chat_id)

    return render_template('chat.html', chat=chat, messages=chat_messages, username=username)

@app.route('/profile/<username>')
def profile(username):
    if 'username' not in session:
        return redirect(url_for('login'))

    if username != session['username']:
        return "Вы не можете просматривать чужой профиль."

    users = load_users()
    user = next((user for user in users if user['username'] == username), None)
    if not user:
        return "Пользователь не найден."

    chats = load_chats()
    user_chats = [chat for chat in chats if username in chat['users']]

    return render_template('profile.html', user=user, chats=user_chats)


@socketio.on('join')
def handle_join(data):
    username = data.get('username')
    chat_id = data.get('chat_id')

    if not username or not chat_id:
        print(f"Error in 'join': Missing data. Username: {username}, Chat ID: {chat_id}")
        return

    join_room(chat_id)
    print(f"User {username} joined chat {chat_id}")
    send({'username': "Системное сообщение: ", 'msg': f'{username} присоединился к чату.'}, to=chat_id)


@socketio.on('message')
def handle_message(data):
    username = data['username']
    chat_id = data['chat_id']
    content = data['msg']

    if not chat_id:
        return

    messages = load_messages()
    new_message = {
        "content": content, 
        "user": username, 
        "chat_id": chat_id, 
        "timestamp": datetime.utcnow().isoformat()
    }
    messages.append(new_message)
    save_messages(messages)

    send({
        'username': username, 
        'msg': content, 
        'chat_id': chat_id,
        'timestamp': new_message['timestamp']
    }, to=chat_id)


socketio.run(app, host="0.0.0.0", port=80)
