#include <WiFi.h>
#include <WiFiUdp.h>

const char* ssid = "eye_of_sauron";
const char* password = "stillwifi";
unsigned int localPort = 8888; 
char packetBuffer[255]; 

WiFiUDP udp;

void setup() {
  Serial.begin(115200);
  
  while (!Serial) {
    delay(10);
  }

  Serial.print("Connecting to Wi-Fi network: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWi-Fi connected successfully!");
  Serial.print("Pico W IP Address: ");
  Serial.println(WiFi.localIP());

  udp.begin(localPort);
  Serial.print("Listening for UDP packets on port ");
  Serial.println(localPort);
}

void loop() {
  int packetSize = udp.parsePacket();
  
  if (packetSize) {
    Serial.print("\nReceived packet of size ");
    Serial.println(packetSize);
    Serial.print("From IP: ");
    Serial.print(udp.remoteIP());
    Serial.print(", Port: ");
    Serial.println(udp.remotePort());

    int len = udp.read(packetBuffer, 255);
    if (len > 0) {
      packetBuffer[len] = 0;
    }
    
    Serial.print("Message: ");
    Serial.println(packetBuffer);
  }
}