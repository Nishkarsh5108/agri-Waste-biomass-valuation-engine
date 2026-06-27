from ultralytics import YOLO
import os
import numpy as np

def calculate_density_valuation(image_path, model_path='models/best.pt', conf=0.25, imgsz=1024, max_yield_kg=5000, calibration_factor=10):
    """
    calculating density on the farm image and estimating the biomass valuation.
    """
    if not os.path.exists(model_path):
        print(f"❌ Error: Model file '{model_path}' nahi mili!")
        return
    
    print(f"⏳ Loading V2 AI Brain ({model_path})...")
    model = YOLO(model_path)
    
    print(f"🔍 Analyzing farm image: {image_path}")
    results = model.predict(source=image_path, conf=conf, imgsz=imgsz, save=True) 
    
    total_stubble_area = 0
    box_count = 0
    
    # 1. Total Image Area 
    img_height, img_width = results[0].orig_shape
    total_image_area = img_height * img_width
    
    # 2. Stubble Boxes Area
    for result in results:
        boxes = result.boxes
        for box in boxes:
            box_count += 1
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            area = (x2 - x1) * (y2 - y1)
            total_stubble_area += area
            
    # 3. Density and Valuation Calculation (With Calibration)
    adjusted_area = total_stubble_area * calibration_factor
    
    density_ratio = min(adjusted_area / total_image_area, 1.0)
    density_percentage = density_ratio * 100
    
    estimated_weight_kg = density_ratio * max_yield_kg
    price_per_kg = 2.0  # ₹ 2 per Kg
    total_value_inr = estimated_weight_kg * price_per_kg
    
    # 4. Final Professional Report
    print("\n" + "="*50)
    print("🌾 ADVANCED BIOMASS VALUATION REPORT 🌾")
    print("="*50)
    print(f"Total Patches Detected : {box_count}")
    print(f"Adjusted Field Density : {density_percentage:.2f} %")
    print("-" * 50)
    print(f"Estimated Biomass Weight : {estimated_weight_kg:,.2f} Kg")
    print(f"Estimated Market Value   : ₹ {total_value_inr:,.2f}")
    print("="*50)

if __name__ == "__main__":
    IMAGE_FILE = "test_farm2.jpg" 
    
    if not os.path.exists(IMAGE_FILE):
        print(f"❌ Error: '{IMAGE_FILE}' image file nahi mili! Folder check karein.")
    else:
        calculate_density_valuation(IMAGE_FILE, conf=0.25, imgsz=1024,max_yield_kg=5000, calibration_factor=10)