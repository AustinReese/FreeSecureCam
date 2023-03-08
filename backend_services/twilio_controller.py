import psycopg2
import threading
import pika
import logging
from twilio.rest import Client
from time import sleep
from datetime import datetime
from os import getenv
from helpers import get_db_host, get_rabbitmq_host

TwilioAccountSID = getenv('TWILIO_ACCOUNT_SID')
TwilioAuthToken = getenv('TWILIO_AUTH_TOKEN')
TwilioPhoneNumber = getenv('TWILIO_PHONE_NUMBER')
UsersPhoneNumber = getenv("USERS_PHONE_NUMBER")

TwilioClientLock = threading.Lock()
IsActive = None
Logger = None
LoggerLock = threading.Lock()

class TwilioAlertThread(threading.Thread):
    def __init__(self, twilio_client):
        threading.Thread.__init__(self)
        self.daemon = True
        self.twilio_client = twilio_client
        # Default to Epoch
        self.last_alert_datetime = datetime(1970, 1, 1)

    def run(self):
        try:
            credentials = pika.PlainCredentials("rabbitmq_user", getenv("RABBITMQ_DEFAULT_PASS"))
            rabbitmq_host = get_rabbitmq_host()
            connection = pika.BlockingConnection(pika.ConnectionParameters(rabbitmq_host, 5672, '/', credentials))
            channel = connection.channel()
            channel.basic_consume(queue='alert_messages',
                                  auto_ack=True,
                                  on_message_callback=self.send_alert_sms)
            channel.start_consuming()
        except Exception as e:
            with LoggerLock:
                Logger.info(f"twilio_controller: Error in TwilioAlertThread.run: {e}")

    def send_alert_sms(self, ch, method, properties, body):
        global IsActive
        global TwilioClientLock
        global TwilioPhoneNumber
        global UsersPhoneNumber

        try:
            # Heartbeat message to prevent channel from closing
            if body != b"keep_alive":
                with TwilioClientLock:
                    if IsActive is True and (datetime.now() - self.last_alert_datetime).total_seconds() >= 30:
                        self.twilio_client.messages.create(
                            body='Liftoff',
                            from_=TwilioPhoneNumber,
                            to=UsersPhoneNumber)
                        self.last_alert_datetime = datetime.now()
                        with LoggerLock:
                            Logger.info("twilio_controller: Sent motion notification")
        except Exception as e:
            with LoggerLock:
                Logger.info(f"twilio_controller: Error in TwilioAlertThread.send_alert_sms: {e}")

def initialize_logger(curs):
    global Logger
    curs.execute("SELECT value FROM configuration WHERE name = 'log_path'")
    log_path = curs.fetchall()[0][0]

    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(f'{log_path}/twilio_controller.log'),
            logging.StreamHandler()
        ]
    )
    with LoggerLock:
        Logger = logging.getLogger(__name__)
        Logger.setLevel(logging.INFO)

def check_incoming_messages(twilio_client, last_replied_to_message_sid, curs, conn):
    global IsActive
    global TwilioClientLock
    global TwilioPhoneNumber
    global UsersPhoneNumber
    try:
        with TwilioClientLock:
            message = twilio_client.messages.list(to=TwilioPhoneNumber, limit=1)[0]
            #First run
            if last_replied_to_message_sid is None:
                last_replied_to_message_sid = message.sid

            if last_replied_to_message_sid != message.sid:
                if message.from_ != UsersPhoneNumber:
                    Logger.info(f"twilio_controller: Unknown sender {message.from_} sent {message.body}")
                    return message.sid
                if message.body.strip().lower() == "pause":
                    IsActive = False
                    update_sql = "UPDATE Configuration SET value = %s WHERE name = 'watchfuleye_is_active'"
                    curs.execute(update_sql, ('False',))
                    conn.commit()
                    twilio_client.messages.create(
                        body='Paused WatchfulEye',
                        from_=TwilioPhoneNumber,
                        to=UsersPhoneNumber)
                    with LoggerLock:
                        Logger.info("twilio_controller: Paused WatchfulEye")
                elif message.body.strip().lower() == "resume":
                    IsActive = True
                    update_sql = "UPDATE Configuration SET value = %s WHERE name = 'watchfuleye_is_active'"
                    curs.execute(update_sql, ('True',))
                    conn.commit()
                    twilio_client.messages.create(
                        body='Resumed WatchfulEye',
                        from_=TwilioPhoneNumber,
                        to=UsersPhoneNumber)
                    with LoggerLock:
                        Logger.info("twilio_controller: Resumed WatchfulEye")
                else:
                    twilio_client.messages.create(
                        body=f'Unknown command {message.body}, valid commands are pause and resume',
                        from_=TwilioPhoneNumber,
                        to=UsersPhoneNumber)
                    with LoggerLock:
                        Logger.info(f"twilio_controller: Received invalid command {message.body}")

                return message.sid

        return last_replied_to_message_sid

    except Exception as e:
        with LoggerLock:
            Logger.info(f"twilio_controller: Error in check_incoming_messages: {e}")

def set_is_active(curs):
    global IsActive
    try:
        curs.execute("SELECT value FROM configuration WHERE name = 'watchfuleye_is_active'")
        is_active_string = curs.fetchall()[0][0]
        if is_active_string == "True":
            with TwilioClientLock:
                IsActive = True
        else:
            with TwilioClientLock:
                IsActive = False

    except Exception as e:
        with LoggerLock:
            Logger.info(f"twilio_controller: Error in set_is_active: {e}")

def run_twilio_controller():
    global Logger
    db_host = get_db_host()

    conn = psycopg2.connect(host=db_host, port=5432, database=getenv('DB_NAME'),  user=getenv('POSTGRES_USER'), password=getenv('POSTGRES_PASSWORD'))
    curs = conn.cursor()
    initialize_logger(curs)

    if TwilioAccountSID != "":
        twilio_client = Client(TwilioAccountSID, TwilioAuthToken)
    else:
        Logger.info("twilio_controller: Twilio integration disabled, exiting")
        return
    try:
        set_is_active(curs)

        twilio_alert_thread = TwilioAlertThread(twilio_client)
        twilio_alert_thread.start()
        last_replied_to_message_sid = None

        while True:
            last_replied_to_message_sid = check_incoming_messages(twilio_client, last_replied_to_message_sid, curs, conn)
            sleep(5)

    except Exception as e:
        conn.close()
        Logger.info(f"twilio_controller: Error in main: {e}")

