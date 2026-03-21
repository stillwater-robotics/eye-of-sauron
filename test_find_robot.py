import cv2
import os
from pathlib import Path
from sauronlib.find_robot import find_robot

# Path to test images folder
TEST_IMGS_FOLDER = "test_imgs"
REFERENCE_CONTOUR = "contour_refs/auv_contour.png"

if __name__ == "__main__":
    # Set DEBUG = True to display binary images for debugging
    DEBUG = True
    
    img_files = sorted([f for f in os.listdir(TEST_IMGS_FOLDER) 
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp'))])
    if not img_files:
        quit
    
    # Test the find_robot cv algorithm on all test images
    for img_file in img_files:
        img_path = os.path.join(TEST_IMGS_FOLDER, img_file)
        frame = cv2.imread(img_path)
        if frame is None:
            continue
        
        # Get frame parameters (for display later)
        h, w = frame.shape[:2]
        aspect_ratio = w / h
        display_height = 800
        display_width = int(display_height * aspect_ratio)
        
        # Find robot and get all contours and the robot center
        contours, center, binary = find_robot(frame, REFERENCE_CONTOUR, debug=DEBUG)
        
        # Display binary image in debug mode, otherwise show frame with contours
        display_img = frame
        # Draw all contours
        if contours is not None:
            cv2.drawContours(display_img, contours, -1, (0, 255, 0), 2)
        
        # Draw center point
        if center is not None:
            cv2.circle(display_img, center, 40, (0, 0, 255), -1)
            cv2.circle(display_img, center, 36, (0, 100, 255), -1)
            cv2.putText(display_img, f"Center: {center}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # Print result
        if center is not None:
            print(f"{img_file}: Robot found at {center}")
        else:
            print(f"{img_file}: No robot detected")
        
        cv2.namedWindow("Robot Detection", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Robot Detection", display_width, display_height)
        cv2.imshow("Robot Detection", display_img)
        cv2.waitKey(0)
    
    cv2.destroyAllWindows()