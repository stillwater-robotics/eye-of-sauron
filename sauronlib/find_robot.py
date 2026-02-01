import cv2
import numpy as np

MAX_SCORE = 0.2 # upper thresh foor match score to qualify as robot

def get_reference_contour(ref_image_path):
    
    # Preprocess the reference image and get contour
    img = cv2.imread(ref_image_path)
    
    if img is None:
        return None
        
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Show the reference contour
    best_cnt = max(contours, key=cv2.contourArea)
    debug_template = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    cv2.drawContours(debug_template, [best_cnt], -1, (0, 0, 255), 2)
    
    cv2.namedWindow("Reference Template", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Reference Template", 400, 400)
    cv2.imshow("Reference Template", debug_template)

    return best_cnt

def find_robot(original_img, ref_image_path="robot_reference.png"):

    # Preprocess the passed image
    gray = cv2.cvtColor(original_img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)
    
    # Morphological open, for noise
    kernel_clean = np.ones((3,3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_clean, iterations=4)

    # Morphological close
    kernel_fill = np.ones((5,5), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_fill, iterations=2)

    # Collect reference contour and image contours
    ref_contour = get_reference_contour(ref_image_path)    
    if ref_contour is None:
        return None, None

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Search for the best match
    best_match_cnt = None
    lowest_score = 1.0 # 0.0 is a perfect match

    for cnt in contours:
        # Ignore small contours
        area = cv2.contourArea(cnt)
        if area < 10000: 
            continue

        # Get ref match score, where lower score corresponds to a better match of the refernce image
        score = cv2.matchShapes(ref_contour, cnt, cv2.CONTOURS_MATCH_I1, 0)
        if score < lowest_score:
            lowest_score = score
            best_match_cnt = cnt
            
    if best_match_cnt is not None and lowest_score < MAX_SCORE:
        # Return all contours (for debugging) and the center of the robot
        (center_x, center_y), _, _ = cv2.minAreaRect(best_match_cnt)
        return contours, (int(center_x), int(center_y))

    else:
        return None, None