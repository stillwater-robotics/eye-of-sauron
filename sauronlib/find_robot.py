import cv2
import numpy as np

MAX_SCORE = 0.2 # upper thresh foor match score to qualify as robot

def get_reference_contour(ref_image_path, debug=False):
    
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

def find_robot(original_img, ref_image_path="robot_reference.png", debug=False, prev_center=None, allow_reset=False):

    # Preprocess the passed image
    gray = cv2.cvtColor(original_img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blurred, 185, 255, cv2.THRESH_BINARY)
    
    # Morphological open, for noise
    kernel_clean = np.ones((3,3), np.uint8)
    #binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_clean, iterations=1)

    # Morphological close
    kernel_fill = np.ones((5,5), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_fill, iterations=3)

    # Collect reference contour and image contours
    ref_contour = get_reference_contour(ref_image_path, debug=debug)    
    if ref_contour is None:
        return None, None, binary

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Search for the best match using hybrid scoring (shape match + size)
    best_match_cnt = None
    lowest_score = float('inf')
    contour_scores = []  # Store scores for debug visualization
    max_area = 0

    # First pass: find max area for normalization
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area >= 2000:
            max_area = max(max_area, area)

    # Second pass: calculate hybrid scores
    for cnt in contours:
        # Ignore small contours
        area = cv2.contourArea(cnt)
        if area < 2000:
            continue

        # Get ref match score (lower is better, 0 is perfect match)
        shape_score = cv2.matchShapes(ref_contour, cnt, cv2.CONTOURS_MATCH_I1, 0)
        
        # Get size score (normalized, lower is worse - invert to make larger better)
        size_score = 1.0 - (area / max_area) if max_area > 0 else 1.0
        
        # Hybrid score: 70% shape matching, 30% size preference
        combined_score = (shape_score * 0.7) + (size_score * 0.3)
        
        contour_scores.append((cnt, combined_score, shape_score, size_score))
        if combined_score < lowest_score:
            lowest_score = combined_score
            best_match_cnt = cnt
    
    # Show debug image with all contours, thickness proportional to combined score
    if debug:
        debug_binary = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        for cnt, combined_score, shape_score, size_score in contour_scores:
            # Invert score so lower scores (better matches) have thicker lines
            # Map score 0 to MAX_SCORE -> thickness 15 to 1
            thickness = max(1, int(15 * (1 - combined_score / MAX_SCORE)))
            cv2.drawContours(debug_binary, [cnt], -1, (0, 255, 0), thickness)
        cv2.namedWindow("Binary Image (Debug)", cv2.WINDOW_NORMAL)
        cv2.imshow("Binary Image (Debug)", debug_binary)
            
    if best_match_cnt is not None and lowest_score < MAX_SCORE:
        # Calculate the center of the detected contour
        (center_x, center_y), _, _ = cv2.minAreaRect(best_match_cnt)
        new_center = (int(center_x), int(center_y))
        
        # Apply temporal constraint if previous center exists and reset is not allowed
        # if prev_center is not None and not allow_reset:
        #     max_delta = 50  # Maximum distance (in pixels) from previous center
        #     dx = new_center[0] - prev_center[0]
        #     dy = new_center[1] - prev_center[1]
        #     distance = (dx**2 + dy**2)**0.5
            
        #     # If new center is too far from previous, use previous center
        #     if distance > max_delta:
        #         new_center = prev_center
        #     else:
        #         # Apply smoothing: pull the new center slightly back toward the previous center
        #         # 20% pull toward previous position, 80% new detection
        #         smoothing_factor = 0.2
        #         new_center = (
        #             int(new_center[0] * (1 - smoothing_factor) + prev_center[0] * smoothing_factor),
        #             int(new_center[1] * (1 - smoothing_factor) + prev_center[1] * smoothing_factor)
        #         )
        
        return contours, new_center, binary

    else:
        return None, None, binary