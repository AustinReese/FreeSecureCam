from socket_connection import run_socket_connection
from trigger_alert import run_trigger_alert
from twilio_controller import run_twilio_controller
from threading import Thread


if __name__ == "__main__":
    socket_connection_thread = Thread(target=run_socket_connection)
    socket_connection_thread.start()

    trigger_alert_thread = Thread(target=run_trigger_alert)
    trigger_alert_thread.start()

    twilio_controller_thread = Thread(target=run_twilio_controller)
    twilio_controller_thread.start()
