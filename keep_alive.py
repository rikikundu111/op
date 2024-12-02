from flask import Flask, render_template
from threading import Thread
import os
import time
import schedule

app = Flask(__name__)
@app.route('/')
def index():
    return "Alive"

def run():
    app.run(host='0.0.0.0',port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
    os.system("echo 'Keep-alive script running...'")

schedule.every(1500).seconds.do(keep_alive)