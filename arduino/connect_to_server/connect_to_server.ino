#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>

#define CAMERA_MODEL_AI_THINKER

#include "camera_pins.h"

WiFiClient client;
HTTPClient http;

const char* ssid = <YOUR_NETWORK_SSID>;
const char* password = <YOUR_NETWORK_PASSWORD>;
const uint16_t apiPort = 80;
const uint16_t socketPort = 8090;

const char * host = <YOUR_SERVERS_IP_ADDRESS>;

const bool printReceivedData = true;
bool connectedToServer = false;
const char *imageSeperator = "newblock";
bool isActive;
int loopsSinceActiveCheck = 0;
int loopsSinceTemperatureReading = 0;
String apiPath = String("http://") + String(host) + String(':') + String(apiPort) + String("/api/watchfuleye_is_active");

#ifdef __cplusplus
extern "C" {
#endif
uint8_t temprature_sens_read();
#ifdef __cplusplus
}
#endif
uint8_t temprature_sens_read();

bool checkIsActive(){
  
    http.begin(apiPath.c_str());
    int httpResponseCode = http.GET();

    if (httpResponseCode == 200) {
      String payload = http.getString();
      if (payload == "True"){
        return true;
      }
    }
    else {
      Serial.print("Connection to API failed with code: ");
      Serial.println(httpResponseCode);
    }
    // Free resources
    http.end();
    return false;
}

void setup() {
  Serial.begin(115200);
  Serial.setDebugOutput(true);
  Serial.println();

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // if PSRAM IC present, init with UXGA resolution and higher JPEG quality
  //                      for larger pre-allocated frame buffer.
  if(psramFound()){
    config.frame_size = FRAMESIZE_UXGA;
    config.jpeg_quality = 10;
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
  }

#if defined(CAMERA_MODEL_ESP_EYE)
  pinMode(13, INPUT_PULLUP);
  pinMode(14, INPUT_PULLUP);
#endif

  // camera init
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  // initial sensors are flipped vertically and colors are a bit saturated
  if (s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1); // flip it back
    s->set_brightness(s, 1); // up the brightness just a bit
    s->set_saturation(s, -2); // lower the saturation
  }
  // drop down frame size for higher initial frame rate
  s->set_framesize(s, FRAMESIZE_QVGA);

#if defined(CAMERA_MODEL_M5STACK_WIDE) || defined(CAMERA_MODEL_M5STACK_ESP32CAM)
  s->set_vflip(s, 1);
  s->set_hmirror(s, 1);
#endif

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("");
  Serial.println("Connected to WiFi");

  isActive = checkIsActive();
  while (isActive == false){
    isActive = checkIsActive();
    Serial.println("WatchfulEye is disabled");
    delay(5000);
  }
  Serial.println("Connected to API at " + String(host) + String(':') + String(apiPort));

  while (!client.connect(host, socketPort)) {
    Serial.println("Connection to host failed");
    delay(5000);
  }
  Serial.println("Connected to host at " + String(host) + String(':') + String(socketPort));
}

void loop() {
  if (loopsSinceActiveCheck == 100){
    isActive = checkIsActive();
    //API down or WatchfulEye has been disabled
    if (isActive == false){
      //First wait for it to be reenabled
      while (isActive == false){
        Serial.println("WatchfulEye is disabled");
        delay(5000);
        isActive = checkIsActive();
      }
      //Then reestablish connection with host
      while (!client.connect(host, socketPort)) {
        Serial.println("Connection to host failed");
        delay(5000);
      }
    }
    loopsSinceActiveCheck = 0;
  }
  
  if (client.connected() == 0){
    while (!client.connect(host, socketPort)) {
      Serial.println("Connection to host failed");
      delay(5000);
    }
  }

  
  if (loopsSinceTemperatureReading == 1000){
    int temperature = temprature_sens_read();
    Serial.println("CPU Temperature: " + String(temperature) + " F");
    String temperature_message_string = String("temp") + String(temperature) + String('$');
    const char* temperature_message_chars = temperature_message_string.c_str();
    client.write(temperature_message_chars);
    loopsSinceTemperatureReading = 0;
  }

  camera_fb_t *fb = esp_camera_fb_get();
  if(!fb) {
      Serial.println("Camera capture failed");
      esp_camera_fb_return(fb);
      return;
  }
  
  byte buffer[8] = { NULL };
  const char *data = (const char *)fb->buf;
  client.write(data, fb->len);
  client.write(imageSeperator);
  esp_camera_fb_return(fb);
  loopsSinceActiveCheck++;
  loopsSinceTemperatureReading++;
  
  delay(50);
}
