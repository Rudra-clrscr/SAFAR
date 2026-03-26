/*************************************************************
  SAFAR - IoT Hardware Tracker (ESP8266/ESP32)

  This sketch connects a physical GPS module (Neo-6M) and an 
  SOS push button to the SAFAR Python backend via Blynk IoT.
  
  Hardware Connections (NodeMCU V3 / ESP8266):
   - GPS TX  -> Pin D1 (GPIO 5)
   - GPS RX  -> Pin D2 (GPIO 4)
   - SOS Btn -> Pin D3 (GPIO 0) -> Connect to GND when pressed.
 *************************************************************/

// Blynk Template Configuration (Provided by User)
#define BLYNK_TEMPLATE_ID "TMPL3hTcazqhO"
#define BLYNK_TEMPLATE_NAME "GPS"
#define BLYNK_AUTH_TOKEN "2jkZ6xI1TFwbKW0q6BZsxBLe9PHz3kmV"

#define BLYNK_PRINT Serial

#include <ESP8266WiFi.h>
#include <BlynkSimpleEsp8266.h>
#include <TinyGPS++.h>
#include <SoftwareSerial.h>

// Your WiFi credentials.
char ssid[] = "YOUR_WIFI_SSID";
char pass[] = "YOUR_WIFI_PASSWORD";

// Hardware Pins
#define SOS_BUTTON_PIN D3
static const int RXPin = D1, TXPin = D2;
static const uint32_t GPSBaud = 9600;

// Objects
TinyGPSPlus gps;
SoftwareSerial ss(RXPin, TXPin);
BlynkTimer timer;

// Virtual Pins (Must match SAFAR Backend)
// V1 = Latitude (Double)
// V2 = Longitude (Double)
// V3 = SOS Button (Integer/Boolean: 0 or 1)

void checkGPS() {
  while (ss.available() > 0) {
    if (gps.encode(ss.read())) {
      if (gps.location.isValid()) {
        double lat = gps.location.lat();
        double lon = gps.location.lng();
        
        Serial.print("GPS: ");
        Serial.print(lat, 6);
        Serial.print(", ");
        Serial.println(lon, 6);
        
        // Send to Blynk (SAFAR backend polls these pins)
        Blynk.virtualWrite(V1, lat);
        Blynk.virtualWrite(V2, lon);
      }
    }
  }
}

unsigned long lastSOSPress = 0;

void checkSOS() {
  // Read physical button state (Active Low)
  int buttonState = digitalRead(SOS_BUTTON_PIN);
  
  if (buttonState == LOW) { // Button is physically held down
    Serial.println("SOS BUTTON PRESSED! Sending alert to SAFAR...");
    lastSOSPress = millis(); // Refresh the latch timer
  }
  
  // Asynchronous Hardware Latch: Keep the alert active for 4 full seconds 
  // after the button is released, so the Python backend's 2-second polling 
  // loop is guaranteed to catch the '1' before it resets.
  if (millis() - lastSOSPress < 4000) {
    Blynk.virtualWrite(V3, 1);
  } else {
    // Backend gets the all-clear
    Blynk.virtualWrite(V3, 0); 
  }
}

void setup() {
  Serial.begin(115200);
  ss.begin(GPSBaud);
  
  pinMode(SOS_BUTTON_PIN, INPUT_PULLUP);

  Serial.println("Initializing SAFAR IoT Tracker...");
  Blynk.begin(BLYNK_AUTH_TOKEN, ssid, pass);
  
  // Timer to check GPS every 3 seconds
  timer.setInterval(3000L, checkGPS);
  
  // Timer to check SOS button every 200 ms
  timer.setInterval(200L, checkSOS);
}

void loop() {
  Blynk.run();
  timer.run();
}
