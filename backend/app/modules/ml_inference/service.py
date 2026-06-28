import os
import io
import math
from PIL import Image
from ultralytics import YOLO

# Resolve the absolute path to the backend directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# BASE_DIR is now 'backend/'
MODEL_PATH = os.path.join(BASE_DIR, 'models', 'best.pt')

# Initialize model lazily or at startup
_model = None

def get_yolo_model():
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            raise FileNotFoundError(f"YOLO model not found at {MODEL_PATH}")
        _model = YOLO(MODEL_PATH)
    return _model

def analyze_biomass_image(image_bytes: bytes, farm_area: float = 1.0) -> dict:
    """
    Analyzes a farm image to estimate biomass weight and valuation.
    """
    # 1. Load image
    image = Image.open(io.BytesIO(image_bytes))
    
    # 2. Run Inference
    model = get_yolo_model()
    # YOLO predict can take PIL Image directly
    results = model.predict(source=image, save=False, conf=0.25, imgsz=1024)
    result = results[0]
    
    weed_count = len(result.boxes)
    
    # 3. Calculate Density
    img_height, img_width = result.orig_shape
    total_image_area = img_height * img_width
    
    total_biomass_area = 0
    for box in result.boxes:
        width = float(box.xywh[0][2])
        height = float(box.xywh[0][3])
        total_biomass_area += (width * height)
        
    calibration_factor = 10
    if total_image_area > 0:
        adjusted_area = total_biomass_area * calibration_factor
        density_ratio = min(adjusted_area / total_image_area, 1.0)
        density_percentage = density_ratio * 100
        density = round(density_percentage, 2)
    else:
        density = 0.0

    # 4. Valuation Logic
    max_yield_per_hectare_kg = 5000
    price_per_kg = 2.5
    
    actual_weight_kg = (density / 100) * max_yield_per_hectare_kg * farm_area
    actual_weight_tons = round(actual_weight_kg / 1000, 2) 
    
    payout = actual_weight_kg * price_per_kg
    co2_saved_kg = actual_weight_tons * 1500
    
    return {
        "weed_count": weed_count,
        "density_percentage": density,
        "weight_tons": actual_weight_tons,
        "weight_kg": actual_weight_kg,
        "estimated_payout_inr": payout,
        "co2_saved_kg": co2_saved_kg
    }
