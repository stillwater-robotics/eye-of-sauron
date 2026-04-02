#include <WiFi.h>
#include <WiFiUdp.h>

const char* ssid = "eye_of_sauron";
const char* password = "stillwifi";
unsigned int localPort = 8888; 
char packetBuffer[255]; 

WiFiUDP udp;

// Laptop connection details
IPAddress laptopIP;
unsigned int laptopPort = 0;
bool laptopConnected = false;

void setup() {
  Serial.begin(9600);
  
  // while (!Serial) {
  //   delay(10);
  // }

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

  // --- Serial Command Handling ---
    if (Serial.available() > 0) {
        char incomingByte = Serial.read();
        if (incomingByte == 'w') {
            if (WiFi.status() == WL_CONNECTED) {
                // Convert IP to string and print to Serial
                String ip = WiFi.localIP().toString();
                Serial.print("Pico W IP Address: ");
                Serial.println(ip);
            } else {
                Serial.println("Not connected");
            }
        }
    }

  int packetSize = udp.parsePacket();
  
  if (packetSize) {
    // Grab the sender's IP and Port from the UDP header
    laptopIP = udp.remoteIP();
    laptopPort = udp.remotePort(); 

    int len = udp.read(packetBuffer, 255);
    if (len > 0) {
      packetBuffer[len] = 0;
    }
    
    String msg = String(packetBuffer);
    Serial.print("\nReceived Message: ");
    Serial.println(msg);

    // Designated startuo
    if (msg.startsWith("STARTUP_PORT:")) {
      laptopConnected = true;
      Serial.print("Handshake received! Laptop registered at ");
      Serial.print(laptopIP);
      Serial.print(":");
      Serial.println(laptopPort);
      
      udp.beginPacket(laptopIP, laptopPort);
      udp.print("Pico says: Handshake successful. I am ready.");
      udp.endPacket();
      
    } else if (laptopConnected) {
      udp.beginPacket(laptopIP, laptopPort);
      udp.print("Pico received: ");
      udp.print(msg);
      udp.endPacket();
    }
  }

  delay(500);
}