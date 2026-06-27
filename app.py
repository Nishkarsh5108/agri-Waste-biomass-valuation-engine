import os
import requests
from flask import Flask, render_template, request
from ultralytics import YOLO

# 1. Initialize App & Model
app = Flask(__name__)
model = YOLO('models/best.pt')

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 2. Home Route
@app.route('/')
def home():
    return render_template('index.html')

# 3. Detection, Valuation & Environmental Route
@app.route('/detect', methods=['POST'])
def detect_weeds():
    # To recieve the uploaded image from the form
    if 'crop_image' not in request.files:
        return "No file uploaded!"
    
    file = request.files['crop_image']
    if file.filename == '':
        return "No file selected!"

    # to handle farm area input, defaulting to 1.0 if not provided or invalid
    try:
        farm_area = float(request.form.get('farm_area', 1.0))
    except ValueError:
        farm_area = 1.0

    # Uploaded photo ko 'static/uploads' me save karna
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    # AI Magic (YOLOv8 Run) - UPGRADED TO HD VISION
    results = model.predict(source=filepath, save=False, conf=0.25, imgsz=1024)  # Calibration factor for gaps and sky compensation
    result = results[0]

    # Weed/Stubble Count 
    weed_count = len(result.boxes)

    # Total image area
    img_height, img_width = result.orig_shape
    total_image_area = img_height * img_width
    
    total_biomass_area = 0
    for box in result.boxes:
        width = float(box.xywh[0][2])
        height = float(box.xywh[0][3])
        total_biomass_area += (width * height)
        
    # Density Percentage (With Calibration Factor)
    calibration_factor = 10
    if total_image_area > 0:
        adjusted_area = total_biomass_area * calibration_factor
        density_ratio = min(adjusted_area / total_image_area, 1.0) # Cap at 100%
        density_percentage = density_ratio * 100
        density = round(density_percentage, 2)
    else:
        density = 0.0

    # --- ECONOMIC & ENVIRONMENTAL LOGIC ---
    # Assume 1 Hectare @ 100% density = 5000 Kg of Biomass
    max_yield_per_hectare_kg = 5000
    price_per_kg = 2.5  # ₹2.5 per Kg

    # 1. Weight Math
    actual_weight_kg = (density / 100) * max_yield_per_hectare_kg * farm_area
    actual_weight_tons = round(actual_weight_kg / 1000, 2) 
    
    # 2. Payout Math
    payout = actual_weight_kg * price_per_kg
    payout_formatted = f"₹{int(payout):,}" 
    
    # 3. Carbon Credit Math (1 Ton = 1500 Kg CO2)
    co2_saved_kg = actual_weight_tons * 1500
    co2_formatted = f"{int(co2_saved_kg):,} Kg"

    # API CALL TO FASTAPI
    # This points to the logistics module running locally.
    fastapi_url = "http://127.0.0.1:8000/logistics/dispatch" 
    
    payload_data = {
        "weight_tons": actual_weight_tons,
        "gps_location": "28.7041, 77.1025" # Dummy location
    }

    try:
        # Sending data to the FastAPI backend over the network
        response = requests.post(fastapi_url, json=payload_data, timeout=5)
        
        if response.status_code == 200:
            print(f"✅ Logistics API Triggered Successfully: {response.json()}")
        else:
            print(f"⚠️ Backend returned an error: {response.status_code} - {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"⚠️ FastAPI backend is currently offline... Error: {e}")
    
    output_filename = "result_" + file.filename
    output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
    result.save(filename=output_path)

    return render_template('result.html', 
                           original_img=file.filename, 
                           result_img=output_filename, 
                           count=weed_count, 
                           density=density,
                           weight=actual_weight_tons,
                           payout=payout_formatted,
                           co2_saved=co2_formatted)

# 4. Start Server
if __name__ == '__main__':
    app.run(debug=True)