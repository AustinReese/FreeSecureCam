import cv2
import numpy as np
import pika
import threading
import logging
import psycopg2
from time import sleep
from os import getenv
from helpers import get_db_host, get_rabbitmq_host

ImageArray = []
TwilioClientLock = threading.Lock()
Logger = None
LoggerLock = threading.Lock()

class ImageUpdateThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.channel = None

    def run(self):
        try:
            credentials = pika.PlainCredentials("rabbitmq_user", getenv("RABBITMQ_DEFAULT_PASS"))
            rabbitmq_host = get_rabbitmq_host()
            connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host, 5672, '/', credentials))
            self.channel = connection.channel()
            self.channel.basic_consume(queue='motion_processing_images',
                                  auto_ack=True,
                                  on_message_callback=self.update_current_image)
            self.channel.start_consuming()

        except Exception as e:
            with LoggerLock:
                Logger.info(f"trigger_alert: Error in ImageUpdateThread.run: {e}")

    def update_current_image(self, ch, method, properties, body):
        global ImageArray
        try:
            if body != b"keep_alive":
                with TwilioClientLock:
                    ImageArray.append(body)
            else:
                with TwilioClientLock:
                    self.channel.basic_publish(exchange='',
                                          routing_key='alert_messages',
                                          body="keep_alive")

        except Exception as e:
            with LoggerLock:
                Logger.info(f"trigger_alert: Error in ImageUpdateThread.update_current_image: {e}")

def initialize_logger():
    global Logger
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
            logging.FileHandler(f'{log_path}/trigger_alert.log'),
            logging.StreamHandler()
        ]
    )
    with LoggerLock:
        Logger = logging.getLogger(__name__)
        Logger.setLevel(logging.INFO)


def create_image_from_bytes(image_bytes):
    nparr = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

def check_images_for_motion(connection, channel):
    try:
        global ImageArray
        with TwilioClientLock:
            if len(ImageArray) >= 50:
                total_changed_pixels = 0
                max_changed_pixels = 0
                max_changed_pixels_image_bytes = ImageArray[0]
                previous_image_grayscale = cv2.cvtColor(src=create_image_from_bytes(ImageArray[0]),
                                                        code=cv2.COLOR_BGR2GRAY)
                previous_image_blurred = cv2.GaussianBlur(src=previous_image_grayscale, ksize=(21, 21), sigmaX=0)
                for image_bytes in ImageArray:
                    image = create_image_from_bytes(image_bytes)
                    image_grayscale = cv2.cvtColor(src=image, code=cv2.COLOR_BGR2GRAY)
                    image_blurred = cv2.GaussianBlur(src=image_grayscale, ksize=(21, 21), sigmaX=0)
                    difference_image = cv2.absdiff(src1=image_blurred, src2=previous_image_blurred)

                    difference_prepared = cv2.threshold(src=difference_image, thresh=25, maxval=255,
                                                        type=cv2.THRESH_BINARY)[1]
                    total_changed_pixels += np.count_nonzero(difference_prepared)

                    if max_changed_pixels > np.count_nonzero(difference_prepared):
                        max_changed_pixels = np.count_nonzero(difference_prepared)
                        max_changed_pixels_image_bytes = image_bytes

                    previous_image_blurred = image_blurred
                ImageArray = []

                # This value should be 0, 1000 is somewhat arbitrary but brief motion will change at least 10,000 pixels
                if total_changed_pixels > 1000:
                    channel.basic_publish(exchange='',
                                          routing_key='alert_messages',
                                          body=max_changed_pixels_image_bytes)
                    with LoggerLock:
                        Logger.info("trigger_alert: Motion detected, sending alert message")
                else:
                    channel.basic_publish(exchange='',
                                          routing_key='alert_messages',
                                          body="keep_alive")
            else:
                channel.basic_publish(exchange='',
                                      routing_key='alert_messages',
                                      body="keep_alive")

    except Exception as e:
        with LoggerLock:
            Logger.info(f"trigger_alert: Error in check_images_for_motion: {e}")


def run_trigger_alert():
    initialize_logger()
    try:
        image_update_thread = ImageUpdateThread()
        image_update_thread.start()

        credentials = pika.PlainCredentials("rabbitmq_user", getenv("RABBITMQ_DEFAULT_PASS"))
        rabbitmq_host = get_rabbitmq_host()
        connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host, 5672, '/', credentials))
        channel = connection.channel()
        while True:
            check_images_for_motion(connection, channel)
            sleep(.5)

    except Exception as e:
        with LoggerLock:
            Logger.info(f"trigger_alert: Error in main: {e}")
