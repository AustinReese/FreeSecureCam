import socket
import pika
import cv2
import numpy as np
import pytz
import threading
import logging
import psycopg2
from datetime import datetime
from select import select
from timeit import default_timer as timer
from time import sleep
from os import getenv
from helpers import get_rabbitmq_host, get_db_host, get_ip_to_bind

ImageSeperator = b"newblock"
Channel = None
ActiveConnection = False
PublishLock = threading.Lock()
SocketLogger = None
SocketLoggerLock = threading.Lock()

class KeepAliveThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        try:
            global ActiveConnection
            global PublishLock
            global Channel
            while True:
                if ActiveConnection == False:
                    with PublishLock:
                        Channel.basic_publish(exchange='',
                                              routing_key='livestream_images',
                                              body='keep_alive')
                        Channel.basic_publish(exchange='',
                                              routing_key='motion_processing_images',
                                              body='keep_alive')
                sleep(30)
        except Exception as e:
            with SocketLoggerLock:
                SocketLogger.info(f"socket_connection: Error in KeepAliveThread.run: {e}")

def initialize_SocketLogger():
    global SocketLogger
    db_host = get_db_host()

    conn = psycopg2.connect(host=db_host, port=5432, database=getenv('DB_NAME'),  user=getenv('POSTGRES_USER'),
                            password=getenv('POSTGRES_PASSWORD'))
    curs = conn.cursor()
    curs.execute("SELECT value FROM configuration WHERE name = 'log_path'")
    log_path = curs.fetchall()[0][0]
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(f'{log_path}/socket_connection.log'),
            logging.StreamHandler()
        ]
    )

    with SocketLoggerLock:
        SocketLogger = logging.getLogger(__name__)
        SocketLogger.setLevel(logging.INFO)
        #SocketLogger.addHandler(logging.StreamHandler(sys.stdout))

def await_connection(serv):
    global SocketLogger
    try:
        with SocketLoggerLock:
            SocketLogger.info(f"socket_connection: Awaiting connection on {serv.getsockname()[0]}:{serv.getsockname()[1]}")
        conn, addr = serv.accept()
        connected_device = f"{addr[0]}:{addr[1]}"
        with SocketLoggerLock:
            SocketLogger.info(f"socket_connection: {connected_device} Connected")
        return conn, addr, connected_device
    except Exception as e:
        with SocketLoggerLock:
            SocketLogger.info(f"socket_connection: Error in await_connection: {e}")

def fetch_data():
    global ActiveConnection
    global ImageSeperator
    global PublishLock
    global Channel
    image_count = 0

    while True:
        try:
            ip_to_bind = get_ip_to_bind(socket)
            serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            serv.bind((ip_to_bind, int(getenv("PORT_BIND"))))
            serv.listen(1)
            conn, addr, connected_device = await_connection(serv)
            conn.setblocking(0)

            buffer = b""

            active_connection = True

            while active_connection == True:
                loop_start = timer()
                data_is_ready = select([conn], [], [], 10)
                if data_is_ready[0]:
                    buffer += conn.recv(16384)
                    images_in_buffer = buffer.count(ImageSeperator)
                    for i in range(images_in_buffer - 1):
                        image_bytes = buffer[:buffer.find(ImageSeperator)]
                        if image_bytes[:4] == b'temp':
                            SocketLogger.info(f"Camera CPU temperature: {image_bytes[4:image_bytes.find(b'$')].decode()} F")
                            image_bytes = image_bytes[image_bytes.find(b'$') + 1:]
                        nparr = np.frombuffer(image_bytes, np.uint8)
                        cv2_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        cv2_image_bytes = cv2.imencode('.jpg', cv2_image)[1].tobytes()
                        timestamp_cv2_image = cv2.putText(cv2_image, str(datetime.now(pytz.timezone(getenv('TIMEZONE'))).strftime("%Y-%m-%d %H:%M:%S")), (10, cv2_image.shape[0] - 10), 2, 0.4, (255, 255, 2))
                        timestamp_image_bytes = cv2.imencode('.jpg', timestamp_cv2_image)[1].tobytes()

                        with PublishLock:
                            Channel.basic_publish(exchange='',
                                                  routing_key='livestream_images',
                                                  body=timestamp_image_bytes)
                            Channel.basic_publish(exchange='',
                                                  routing_key='motion_processing_images',
                                                  body=cv2_image_bytes)
                        buffer = buffer[buffer.find(ImageSeperator) + len(ImageSeperator):]
                        image_count += 1
                elif timer() - loop_start >= 10:
                    with SocketLoggerLock:
                        SocketLogger.info(f"socket_connection: Lost connection to {connected_device}")
                    active_connection = False
                    conn.close()
                    serv.close()
                    continue

        except Exception as e:
            with SocketLoggerLock:
                SocketLogger.info(f"socket_connection: Error in fetch_data: {e}")
            conn.close()
            serv.close()
            sleep(5)


def run_socket_connection():
    global Channel
    initialize_SocketLogger()

    while True:
        try:
            credentials = pika.PlainCredentials("rabbitmq_user", getenv("RABBITMQ_DEFAULT_PASS"))

            rabbitmq_host = get_rabbitmq_host()

            connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host, 5672, '/', credentials))
            with PublishLock:
                Channel = connection.channel()

            keep_alive_thread = KeepAliveThread()
            keep_alive_thread.start()

            fetch_data()

        except Exception as e:
            with SocketLoggerLock:
                SocketLogger.info(f"socket_connection: Error in main: {e}")
            sleep(5)
