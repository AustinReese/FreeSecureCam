# Freesecure

A simple webcam interface for ESP-32 CAM. Built using Docker, Flask, and Python scripts. It features a video feed and 
motion-triggered text messaging.

## Required Hardware

[ESP-32 CAM](https://www.amazon.com/ESP32-CAM-MB-Aideepen-ESP32-CAM-Bluetooth-Arduino/dp/B0948ZFTQZ/ref=sr_1_3?crid=33YA4R8O62ZHS&keywords=esp32%2Bcam&qid=1677810837&sprefix=esp32%2Bcam%2Caps%2C116&sr=8-3&th=1)
(you can buy these anywhere, I got mine from the link and they work well)

A server, raspberry pi's work well but you can use anything

## Required Software

[Docker](https://docs.docker.com/get-docker/)

[Arduino IDE](https://support.arduino.cc/hc/en-us/articles/360019833020-Download-and-install-Arduino-IDE)

## Server setup

```commandline
git clone git@github.com:AustinReese/FreeSecure.git
cd FreeSecure
```

Edit the values in .env, I recommend changing the default passwords. Twilio credentials are optional, you can sign up 
for twilio [here](https://www.twilio.com/try-twilio). They offer a free trial.

```commandline
cd FreeSecure
docker compose build
docker compose up
```

## ESP32-CAM setup

1) In your Arduino IDE, go to File> Preferences
2) Add https://dl.espressif.com/dl/package_esp32_index.json to additional board manager URLs and click ok
3) Go to Tools > Board > Boards Manager
4) Search for esp32 and install the package by Espressif Systems
5) In Tools > Board > ESP32 Arduino > AI Thinker ESP32-CAM
6) Open FreeSecure/arduino/connect_to_server/connect_to_server.ino in Arduino IDE
7) Replace <YOUR_NETWORK_SSID>, <YOUR_NETWORK_PASSWORD>, and <HOST_SERVER_IP> with the proper values
8) Upload the sketch to your ESP32-CAM, the serial monitor should indicate a successful connection. The video stream can
be found at http://localhost

## Debugging
Backend service logs are automatically saved to /tmp/*.log, they will also appear in the Docker console