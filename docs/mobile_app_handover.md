# Mobile App Handover (Farmer App)

Hey! The backend API is live on Render, and our Database (Supabase) and Message Queue (Upstash Redis) are fully configured.

Here is exactly what you need to know to build the **Farmer Mobile App**, how to test the AI, and what endpoints to use.

---

## 1. The API Contract (What is actually working?)

The API is fully functional for the Farmer persona. You can view the Swagger UI and test everything here:
 **[https://agri-waste-biomass-valuation-engine.onrender.com/docs](https://agri-waste-biomass-valuation-engine.onrender.com/docs)**

### Fully Working Endpoints for the Mobile App:

1. **`POST /auth/register`**: Creates a new user. (Send `role: "FARMER"`).
2. **`POST /auth/login`**: Returns a JWT Access Token. *(Pass this token in the `Authorization: Bearer <token>` header for all following requests).*
3. **`GET /auth/me`**: Returns the current logged-in user's profile.
4. **`POST /farms/`**: Registers a new farm. You must send the farm boundary as a valid GeoJSON Polygon.
5. **`GET /farms/`**: Returns a list of all farms owned by the logged-in farmer.
6. **`POST /listings/`**: The core ML endpoint. You send a `farm_id` and upload a `photo`.
   - *Note:* This returns `201 Created` with a `status: PROCESSING` immediately. The ML runs in the background.
7. **`GET /listings/my`**: Returns all listings for the farmer. Poll this endpoint. Once the AI finishes, the status will change to `READY` and fields like `cv_density_ratio`, `estimated_tonnage`, and `quality_score` will be populated!

### Placeholders (Not needed for the Farmer App):

- `/logistics/heatmap`: Placeholder. (For the Admin/Factory Dashboard).
- `/logistics/trigger`: Placeholder. (For the Admin routing algorithm).
- `predict_harvest_dates`: The ML prediction task is currently a placeholder (though the database has seeded mock data for 2025).

---

## 2. How to run the ML AI Worker on your Laptop

To keep cloud costs at $0, the FastAPI server on Render delegates the heavy YOLO AI inference to a background queue. To actually process the images uploaded from your mobile app, you need to run the **Celery Worker** locally on your laptop.

Since your laptop will connect to the exact same Cloud DB and Queue as the Render API, it will process the mobile app's photos seamlessly!

### Setup Instructions:

1. **Clone the repository** and navigate to the `backend` folder.
2. **Create a virtual environment** and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. **Set up your `.env` file**:
   Ask for the `.env` file contents. It must contain the `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY`, and specifically this secure Upstash Redis URL:
   ```env
   REDIS_URL="rediss://default:gQAAAAAAAlThAAIgcDI4NDg4YjQyMTg2YTI0MzU2YWZhZjlkMGY0ZGExNmJjMg@giving-leopard-152801.upstash.io:6379?ssl_cert_reqs=CERT_NONE"
   ```
4. **Run the AI Worker**:
   Open a terminal in the `backend` folder and run:
   ```bash
   celery -A app.worker.celery_app worker -Q main-queue --loglevel=info -P solo
   ```
5. **Leave it running!** Whenever you upload a photo from the mobile app, you will see this terminal instantly download it, run the YOLO model, and update the Cloud database.

---

## 3. Mobile App Functionalities (What you need to build)

Based on the API, the Farmer app should have the following screens/flows:

1. **Auth Screens**: Login / Signup screens (using phone number).
2. **Dashboard / My Farms**: A screen listing the farmer's registered farms.
3. **Add a Farm (Map Integration)**: A screen with a map (like Google Maps) where the farmer can draw a polygon around their field. You'll convert this drawing into a GeoJSON Polygon to send to `POST /farms/`.
4. **Request Biomass Pickup**: A camera flow where the farmer selects a farm, takes a picture of the agricultural waste, and hits upload (`POST /listings/`).
5. **Valuation Results**: A screen showing their uploaded listings (`GET /listings/my`). If the status is `READY`, display the AI's `estimated_tonnage` and estimated payout to the farmer!
