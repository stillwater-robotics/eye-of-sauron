import cv2
import numpy as np
import socket
import time
import math

# Networking
UDP_IP = "255.255.255.255"
UDP_PORT = 5005
BROADCAST_RATE = 0.1 # 10 Hz

# Camera setup
WEBCAM_ID = 0
FRAME_WIDTH_PX = 640
FRAME_HEIGHT_PX = 480

CENTER_X_PX = FRAME_WIDTH_PX / 2
CENTER_Y_PX = FRAME_HEIGHT_PX / 2

CAM_HEIGHT_METERS = 1.2192
CAM_FOV_DEG = 120
FOV_LENGTH_PX = (FRAME_WIDTH_PX / 2) / math.tan( math.radians(CAM_FOV_DEG) / 2 )

# Thresholding for robot identification
HSV_LOWER = np.array([35, int(0.3 * 255), int(0.6 * 255)], dtype=np.uint8)
HSV_UPPER = np.array([56, 255, 255], dtype=np.uint8)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

capture = cv2.VideoCapture(WEBCAM_ID)
capture.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH_PX)
capture.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT_PX)

def udp_mock_gps_position(x, y):
    payload = f"{x:.3f}, {y:.3f}"
    try:
        sock.sendto(payload.encode(), (UDP_IP, UDP_PORT))
        return payload
    except Exception as e:
        print(f"Network Error: {e}")
        return None
    
def find_uuv_px(frame): # returns in pixels
    blurred = cv2.GaussianBlur(frame, (11, 11), 0)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, HSV_LOWER, HSV_UPPER)
    
    # Clean noise
    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        c = max(contours, key=cv2.contourArea)
        M = cv2.moments(c)
        if M["m00"] > 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            return (cx, cy)
    
    return None

def px_to_m(u, v):
    x_px = u - CENTER_X_PX
    y_px = CENTER_Y_PX - v
    
    
    x_m = (x_px * CAM_HEIGHT_METERS) / FOV_LENGTH_PX
    y_m = (y_px * CAM_HEIGHT_METERS) / FOV_LENGTH_PX
    
    return x_m, y_m

last_tx = 0
while(True):
    ret, frame = capture.read()
    frame = cv2.flip(frame, 1)
    
    robot_px = find_uuv_px(frame)
    cv2.circle(frame, (FRAME_WIDTH_PX // 2, FRAME_HEIGHT_PX // 2), 5, (0, 0, 255), -1)
    cv2.arrowedLine(frame, (FRAME_WIDTH_PX // 2, FRAME_HEIGHT_PX // 2), (FRAME_WIDTH_PX // 2, FRAME_HEIGHT_PX // 2 + 20), (0, 255, 0), 3)
    cv2.arrowedLine(frame, (FRAME_WIDTH_PX // 2, FRAME_HEIGHT_PX // 2), (FRAME_WIDTH_PX // 2 + 20, FRAME_HEIGHT_PX // 2), (255, 0, 0), 3)
    
    # Draw min and max HSV threshold in top corner for reference
    hsv_lower = np.array([HSV_LOWER], dtype=np.uint8).reshape(1, 1, 3)
    hsv_upper = np.array([HSV_UPPER], dtype=np.uint8).reshape(1, 1, 3)
    rgb_lower = tuple(int(c) for c in cv2.cvtColor(hsv_lower, cv2.COLOR_HSV2BGR)[0, 0])
    rgb_upper = tuple(int(c) for c in cv2.cvtColor(hsv_upper, cv2.COLOR_HSV2BGR)[0, 0]) 
    cv2.rectangle(frame, (5, 5), (10, 10), rgb_lower, -1)
    cv2.rectangle(frame, (15, 5), (20, 10), rgb_upper, -1)
    
    if robot_px:
        robot_x_m, robot_x_y = px_to_m(robot_px[0], robot_px[1]) 
        
        # Mock GPS to the robot
        if (time.time() - last_tx) > BROADCAST_RATE:
                msg = udp_mock_gps_position(robot_x_m, robot_x_y)
                last_tx = time.time()
        
        cv2.circle(frame, robot_px, 5, (0, 0, 255), -1)
        
        text = f"X: {robot_x_m:.2f}m  Y: {robot_x_y:.2f}m"
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        
    # TODO: Enable tap on the screen to add a new swarm robot, broadcast    
        
    cv2.imshow("Overhead Tracker", frame)
    
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break