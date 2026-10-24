import cv2
import os
import json

# --- SETUP ---
IMAGE_PATH = "Images/images (12).jfif" 
SAVE_FILE = "annotations.json"

if not os.path.exists(IMAGE_PATH):
    print(f"ERROR: Could not find {IMAGE_PATH}. Please check the filename.")
    exit()

CLASSES = {0: "Mask", 1: "Goggles", 2: "Gloves", 3: "Gown"}
current_class = 0

# Global variables
drawing = False
ix, iy = -1, -1
img = cv2.imread(IMAGE_PATH)
clone = img.copy()

# This will hold all our annotations
# Structure: { "image_name": [ {"class": "Mask", "bbox": [x1, y1, x2, y2]}, ... ] }
if os.path.exists(SAVE_FILE):
    with open(SAVE_FILE, 'r') as f:
        all_data = json.load(f)
else:
    all_data = {}

# Ensure the entry for this image exists
image_key = os.path.basename(IMAGE_PATH)
if image_key not in all_data:
    all_data[image_key] = []

def draw_bbox(event, x, y, flags, param):
    global ix, iy, drawing, img, clone, current_class, all_data

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y

    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            img = clone.copy()
            cv2.rectangle(img, (ix, iy), (x, y), (0, 255, 0), 2)
            cv2.putText(img, f"Labeling: {CLASSES[current_class]}", (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        cv2.rectangle(img, (ix, iy), (x, y), (0, 255, 0), 2)
        clone = img.copy() 
        
        # Create annotation object
        anno = {
            "class_id": current_class,
            "class_name": CLASSES[current_class],
            "bbox": [ix, iy, x, y]
        }
        
        # Add to our dictionary
        all_data[image_key].append(anno)
        
        # Save entire dictionary to JSON file
        with open(SAVE_FILE, "w") as f:
            json.dump(all_data, f, indent=4)
            
        print(f"SAVED to JSON: {CLASSES[current_class]} at [{ix}, {iy}, {x}, {y}]")

# Initialize ONE window
cv2.namedWindow("PPE_Annotator")
cv2.setMouseCallback("PPE_Annotator", draw_bbox)

print("INSTRUCTIONS:")
print("1. Click and drag to draw boxes.")
print("2. Press 0, 1, 2, or 3 to change labels.")
print("3. Press 'r' to reset, 'q' to quit.")

while True:
    cv2.imshow("PPE_Annotator", img)
    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break
    elif key == ord("r"):
        img = cv2.imread(IMAGE_PATH)
        clone = img.copy()
        all_data[image_key] = [] # Clear annotations for this image on reset
        print("Image Reset & Annotations Cleared for this image")
    elif key in [ord('0'), ord('1'), ord('2'), ord('3')]:
        current_class = int(chr(key))
        print(f"Current Class: {CLASSES[current_class]}")

cv2.destroyAllWindows()
for i in range(1, 5):
    cv2.waitKey(1)