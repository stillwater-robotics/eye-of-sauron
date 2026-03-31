import cv2
import numpy as np
import socket
import time
import math
import threading
import csv
import os
from datetime import datetime
from sauronlib.find_robot import find_robot
from dataclasses import dataclass

# ------ Constants ------
# Networking
UDP_IP = "192.168.0.102"
UDP_PORT = 8888
LOCAL_PORT = 9999 # Static port for the laptop to receive messages
BROADCAST_RATE = 1 # Hz

CSV_WRITE_RATE = 10 # Hz
CSV_PERIOD = 1.0 / CSV_WRITE_RATE

# Camera setup
WEBCAM_ID = 0
FRAME_WIDTH_PX = 640
FRAME_HEIGHT_PX = 480

CENTER_X_PX = FRAME_WIDTH_PX / 2
CENTER_Y_PX = FRAME_HEIGHT_PX / 2

CAM_HEIGHT_METERS = 0.7
CAM_FOV_DEG = 77
FOV_LENGTH_PX = (FRAME_WIDTH_PX / 2) / math.tan( math.radians(CAM_FOV_DEG) / 2 ) #constref

REFERENCE_CONTOUR = "contour_refs/auv_contour.png"

# ------ Global Variables ------
DEBUG = True  # Set to True to display binary images for debugging
prev_robot_px = None  # Track previous center for temporal smoothing
last_reset_time = 0  # Track when 'r' was last pressed
RESET_DURATION = 10  # Allow free movement for 10 seconds after pressing 'r'
swarm_members = []

# ------ Setup Logging ------
os.makedirs("csvs", exist_ok=True)
csv_filename = os.path.join("csvs", f"robot_pos_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

with open(csv_filename, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["Timestamp", "X_m", "Y_m"])

# ------ Setup Networking ------
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.bind(('', LOCAL_PORT)) # Bind to local port for two-way communication

def receive_messages():
    """Background thread to listen for incoming UDP packets from the Pico."""
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            msg = data.decode('utf-8')
            print(f"\n[RX from {addr[0]}:{addr[1]}] {msg}")
        except OSError:
            break

# Start the background listening thread
rx_thread = threading.Thread(target=receive_messages, daemon=True)
rx_thread.start()

# Send the startup handshake message to the Pico
startup_msg = f"STARTUP_PORT:{LOCAL_PORT}"
sock.sendto(startup_msg.encode('utf-8'), (UDP_IP, UDP_PORT))
print(f"Sent startup handshake: {startup_msg}")


capture = cv2.VideoCapture(WEBCAM_ID)
capture.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH_PX)
capture.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT_PX)    

# ------ Mock Swarm Members ------
@dataclass
class SwarmMember:
    x: float
    y: float

# Spawns or despawns a swarm member in mouse click position
def spawn_member(event,x,y,flags,param):
    if event == cv2.EVENT_LBUTTONDBLCLK:
        # check for nearby existing member
        for i, mem in enumerate(swarm_members):
            dist = math.hypot(mem.x - x, mem.y - y)
            if dist <= 10:
                # remove the member and exit
                swarm_members.pop(i)
                return

        # otherwise, add a new member
        swarm_members.append(SwarmMember(x, y))

# Broadcasts the position of a mocked swarm member to the robot over UDP
def broadcast_swarm_member(member):
    x, y = px_to_m(member.x, member.y) # px to global coord
    
    payload = f"SW_{time.time():.0f}_{x:.3f}_{y:.3f}_0_0"
    print(f"TX: {payload}")
    try:
        sock.sendto(payload.encode(), (UDP_IP, UDP_PORT))
        return payload
    except Exception as e:
        print(f"Network Error: {e}")
        return None

# ------ GPS Mock Helper Functions ------

# Broadcast mock global coordinate of physical robot to the robot over UDP
def udp_mock_gps_position(x, y):
    payload = f"GPS_{time.time():.0f}_{x:.3f}_{y:.3f}"
    print(f"TX: {payload}")
    try:
        sock.sendto(payload.encode(), (UDP_IP, UDP_PORT))
        return payload
    except Exception as e:
        print(f"Network Error: {e}")
        return None

# Convert a px coordinate into a global frame coordinate (mock GPS position)
def px_to_m(u, v): 
    x_px = u - CENTER_X_PX
    y_px = CENTER_Y_PX - v
    
    x_m = (x_px * CAM_HEIGHT_METERS) / FOV_LENGTH_PX
    y_m = (y_px * CAM_HEIGHT_METERS) / FOV_LENGTH_PX
    
    return x_m, y_m

# ------ Main ------
if __name__ == "__main__":
    last_gps_tx = 0
    last_member_tx = 0
    last_csv_write = 0
    prev_robot_px = None
    last_reset_time = 0

    cv2.namedWindow('Overhead Tracker')
    cv2.setMouseCallback('Overhead Tracker', spawn_member)
    
    while(True):

        # Stream from webcam
        ret, frame = capture.read()
        #frame = cv2.flip(frame, 1)

        # Show x,y
        cv2.circle(frame, (int(FRAME_WIDTH_PX // 2), int(FRAME_HEIGHT_PX // 2)), 5, (0, 0, 255), -1)
        cv2.arrowedLine(frame, (int(FRAME_WIDTH_PX // 2), int(FRAME_HEIGHT_PX // 2)), (int(FRAME_WIDTH_PX // 2), int(FRAME_HEIGHT_PX // 2) + 20), (0, 255, 0), 3)
        cv2.arrowedLine(frame, (int(FRAME_WIDTH_PX // 2), int(FRAME_HEIGHT_PX // 2)), (int(FRAME_WIDTH_PX // 2) + 20, int(FRAME_HEIGHT_PX // 2)), (255, 0, 0), 3)

        for member in swarm_members:
            # Draw member
            cv2.circle(frame, (int(member.x), int(member.y)), 14, (0, 255, 0), -1)
            cv2.circle(frame, (int(member.x), int(member.y)), 12, (55, 200, 0), -1)
            
            # Broadcast
            if (time.time() - last_member_tx) > BROADCAST_RATE: 
                broadcast_swarm_member(member)
                last_member_tx = time.time()
                
            # Draw arrow to physical (tracked) robot
            if prev_robot_px:
                cv2.arrowedLine(frame, (int(member.x), int(member.y)), prev_robot_px, (55, 200, 0), 2)
        
        # Check if reset is still active (within 10 seconds)
        allow_reset = (time.time() - last_reset_time) < RESET_DURATION
        
        contours, robot_px, binary = find_robot(frame, REFERENCE_CONTOUR, debug=DEBUG, prev_center=prev_robot_px, allow_reset=allow_reset)
        
        # Update previous center
        if robot_px:
            prev_robot_px = robot_px
        
        # Display binary image in debug mode, otherwise show frame with overlay
        display_frame = frame
        if robot_px:
            robot_x_m, robot_x_y = px_to_m(robot_px[0], robot_px[1]) 
            
            # Mock GPS to the robot (1 Hz based on your original BROADCAST_RATE)
            current_time = time.time()
            if (current_time - last_gps_tx) > BROADCAST_RATE:
                msg = udp_mock_gps_position(robot_x_m, robot_x_y)
                last_gps_tx = current_time

            # Log to CSV at 10 Hz
            if (current_time - last_csv_write) >= CSV_PERIOD:
                timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                with open(csv_filename, mode='a', newline='') as file:
                    writer = csv.writer(file)
                    writer.writerow([timestamp_str, f"{robot_x_m:.3f}", f"{robot_x_y:.3f}"])
                last_csv_write = current_time

            cv2.circle(display_frame, robot_px, 14, (0, 0, 255), -1)
            cv2.circle(display_frame, robot_px, 12, (0, 100, 255), -1)
            
            text = f"X: {robot_x_m:.2f}m  Y: {robot_x_y:.2f}m"
            cv2.putText(display_frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
        cv2.imshow("Overhead Tracker", display_frame)
        
        # Handle key press
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('r'):
            last_reset_time = time.time()
            print("Reset tracking - allowing free movement for 10 seconds")

    # Clean up
    capture.release()
    cv2.destroyAllWindows()
    sock.close()