import cv2
import numpy as np
import socket
import time
import math
from sauronlib.find_robot import find_robot
from dataclasses import dataclass

# ------ Constants ------
# Networking
UDP_IP = "255.255.255.255"
UDP_PORT = 5005
BROADCAST_RATE = 1 # 1 Hz

# Camera setup
WEBCAM_ID = 0
FRAME_WIDTH_PX = 640
FRAME_HEIGHT_PX = 480

CENTER_X_PX = FRAME_WIDTH_PX / 2
CENTER_Y_PX = FRAME_HEIGHT_PX / 2

CAM_HEIGHT_METERS = 1.2192
CAM_FOV_DEG = 120
FOV_LENGTH_PX = (FRAME_WIDTH_PX / 2) / math.tan( math.radians(CAM_FOV_DEG) / 2 )

REFERENCE_CONTOUR = "contour_refs/uuv_contour.png"

# ------ Global Variables ------
swarm_members = []

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

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
    print(f"SW_{time.time():.0f}_{x:.3f}_{y:.3f}_0_0")
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
    print(f"GPS_{time.time():.0f}_{x:.3f}_{y:.3f}")
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

    cv2.namedWindow('Overhead Tracker')
    cv2.setMouseCallback('Overhead Tracker', spawn_member)
    
    while(True):

        # Stream from webcam
        ret, frame = capture.read()
        frame = cv2.flip(frame, 1)

        # Show x,y
        cv2.circle(frame, (FRAME_WIDTH_PX // 2, FRAME_HEIGHT_PX // 2), 5, (0, 0, 255), -1)
        cv2.arrowedLine(frame, (FRAME_WIDTH_PX // 2, FRAME_HEIGHT_PX // 2), (FRAME_WIDTH_PX // 2, FRAME_HEIGHT_PX // 2 + 20), (0, 255, 0), 3)
        cv2.arrowedLine(frame, (FRAME_WIDTH_PX // 2, FRAME_HEIGHT_PX // 2), (FRAME_WIDTH_PX // 2 + 20, FRAME_HEIGHT_PX // 2), (255, 0, 0), 3)

        for member in swarm_members:
            # Draw member
            cv2.circle(frame, (member.x, member.y), 14, (0, 255, 0), -1)
            cv2.circle(frame, (member.x, member.y), 12, (55, 200, 0), -1)
            
            # Broadcast
            if (time.time() - last_member_tx) > BROADCAST_RATE: 
                broadcast_swarm_member(member)
                last_member_tx = time.time()
                
            # Draw arrow to physical (tracked) robot
            if robot_px:
                cv2.arrowedLine(frame, (member.x, member.y), robot_px, (55, 200, 0), 2)
            
        contours, robot_px = find_robot(frame, REFERENCE_CONTOUR)
        if robot_px:
            robot_x_m, robot_x_y = px_to_m(robot_px[0], robot_px[1]) 
            # Mock GPS to the robot
            if (time.time() - last_gps_tx) > BROADCAST_RATE:
                    msg = udp_mock_gps_position(robot_x_m, robot_x_y)
                    last_gps_tx = time.time()

            cv2.circle(frame, robot_px, 14, (0, 0, 255), -1)
            cv2.circle(frame, robot_px, 12, (0, 100, 255), -1)
            cv2.drawContours(frame, contours, -1, (0, 165, 255), 2)
            
            text = f"X: {robot_x_m:.2f}m  Y: {robot_x_y:.2f}m"
            cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            
        cv2.imshow("Overhead Tracker", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break