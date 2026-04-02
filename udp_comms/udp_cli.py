import socket
import threading
import csv
import os
from datetime import datetime

PICO_IP = "192.168.0.101" 
PICO_PORT = 8888
LOCAL_PORT = 9999 # Hold static port for the laptop

# === CSV MESSAGE LOGGING ===

os.makedirs("csvs", exist_ok=True)
csv_filename = os.path.join("csvs", f"udp_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

with open(csv_filename, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["Timestamp", "Direction", "IP", "Port", "Message"])

def log_message(direction, ip, port, message):
    """Helper function to log messages to the CSV."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    with open(csv_filename, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, direction, ip, port, message])

# === SOCKET BINDING ===
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(('', LOCAL_PORT)) 

def receive_messages():
    """Background thread to constantly listen for incoming UDP packets."""
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode('utf-8')
            print(f"\n[RX from {addr[0]}:{addr[1]}] {msg}\n> ", end="", flush=True)
            log_message("RX", addr[0], addr[1], msg)
        except OSError:
            break 

# Start the background listening thread
rx_thread = threading.Thread(target=receive_messages, daemon=True)
rx_thread.start()
print(f"Bound to local port {LOCAL_PORT}. Ready to talk to {PICO_IP}:{PICO_PORT}")

# Send the startup handshake message to the Pico
startup_msg = f"STARTUP_PORT:{LOCAL_PORT}"
sock.sendto(startup_msg.encode('utf-8'), (PICO_IP, PICO_PORT))
log_message("TX", PICO_IP, PICO_PORT, startup_msg)
print(f"Sent startup handshake: {startup_msg}")

print("Type a message and press Enter to send. Type 'quit' to exit.")
while True:
    message = input("\n> ")
    
    if message.lower() == 'quit':
        print("Closing connection...")
        sock.close()
        break
    
    sock.sendto(message.encode('utf-8'), (PICO_IP, PICO_PORT))
    log_message("TX", PICO_IP, PICO_PORT, message)
    print("Message sent!")