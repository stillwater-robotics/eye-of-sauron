import socket

PICO_IP = "192.168.0.101" 
PORT = 8888

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print(f"Ready to send UDP messages to {PICO_IP}:{PORT}")
print("Type a message and press Enter to send. Type 'quit' to exit.")

while True:
    message = input("\n> ")
    
    if message.lower() == 'quit':
        print("Closing connection.")
        break
    
    sock.sendto(message.encode('utf-8'), (PICO_IP, PORT))
    print("Message sent!")

sock.close()