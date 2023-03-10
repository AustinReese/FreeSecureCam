# ----------------------------- Imports -----------------------------

import psycopg2
import threading
import pika
import logging
from flask import Flask, Response, render_template
from flask_bootstrap import Bootstrap
from time import sleep
from os import getenv
from helpers import get_db_host, get_rabbitmq_host

# ----------------------------- Globals -----------------------------

app = Flask(__name__)
Bootstrap(app)

DBHost = get_db_host()

Conn = psycopg2.connect(host=DBHost, port=5432, database=getenv('DB_NAME'),  user=getenv('POSTGRES_USER'), password=getenv('POSTGRES_PASSWORD'))
Cur = Conn.cursor()
DBLock = threading.Lock()

AppLogger = None
AppLoggerLock = threading.Lock()

CurrentImage = ""
ImageLock = threading.Lock()

# ----------------------------- Routes -----------------------------

@app.route('/api/watchfuleye_is_active')
def watchfuleye_is_active():
    global Cur, Conn, DBHost
    with DBLock:
        try:
            Cur.execute("SELECT value FROM configuration WHERE name = 'watchfuleye_is_active'")
        except Exception as e:
            with AppLoggerLock:
                AppLogger.info(f"Error in app.watchfuleye_is_active: {e}")
            Conn.close()
            Conn = psycopg2.connect(host=DBHost, port=5432, database=getenv('DB_NAME'), user=getenv('POSTGRES_USER'),
                                    password=getenv('POSTGRES_PASSWORD'))
            Cur = Conn.cursor()

    return Cur.fetchall()[0][0]

@app.route('/')
def index():
    return render_template('video_livestream.html')

@app.route('/video_feed')
def video_feed():
    return Response(get_current_image(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ----------------------------- Classes -----------------------------

class ImageUpdateThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        credentials = pika.PlainCredentials("rabbitmq_user", getenv("RABBITMQ_DEFAULT_PASS"))
        rabbitmq_host = get_rabbitmq_host()
        connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host, 5672, '/', credentials))
        channel = connection.channel()
        channel.basic_consume(queue='livestream_images',
                              auto_ack=True,
                              on_message_callback=self.update_current_image)
        channel.start_consuming()

    def update_current_image(self, ch, method, properties, body):
        global CurrentImage, ImageLock
        if body != b"keep_alive":
            with ImageLock:
                CurrentImage = body

# ----------------------------- Functions -----------------------------

def get_current_image():
    global CurrentImage, ImageLock

    while True:
        with ImageLock:
            yield_image = CurrentImage

        if len(yield_image) == 0:
            with open("images/err.png", "rb") as f:
                yield_image = f.read()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + yield_image + b'\r\n')

        # Share ImageLock time with ImageUpdateThread.update_current_image
        sleep(.01)

def initialize_AppLogger():
    global Cur, AppLogger, AppLoggerLock
    Cur.execute("SELECT value FROM configuration WHERE name = 'log_path'")
    log_path = Cur.fetchall()[0][0]
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(filename=f'{log_path}trigger_alert.log',
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')
    with AppLoggerLock:
        AppLogger = logging.getLogger(__name__)
        AppLogger.setLevel(logging.INFO)

if __name__ == "__main__":
    initialize_AppLogger()
    image_update_thread = ImageUpdateThread()
    image_update_thread.start()
    app.run(host='0.0.0.0', port=80)

