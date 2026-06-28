from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks
from typing import Annotated
from app.modules.ml_inference.service import analyze_biomass_image
from app.modules.ml_inference.patchtst_seeder import seed_2025_data

router = APIRouter(prefix="/ml_inference", tags=["ML Inference"])

@router.post("/predict_biomass")
async def predict_biomass(
    crop_image: UploadFile = File(...),
    farm_area: Annotated[float, Form()] = 1.0
):
    """
    Run YOLOv8 inference to calculate biomass density and valuation.
    This also conceptually replaces the /logistics/dispatch webhook by
    enabling the creation of a READY biomass listing directly in the DB
    (which the CVRP optimizer can then pick up).
    """
    if not crop_image.filename:
        raise HTTPException(status_code=400, detail="No file selected")
    
    try:
        # Read the uploaded image bytes
        image_bytes = await crop_image.read()
        
        # Analyze using YOLOv8 service
        result = analyze_biomass_image(image_bytes, farm_area)
        
        # TODO: Here you would typically insert a new biomass listing into the DB
        # e.g. listing = create_listing(weight=result['weight_tons'], status='READY')
        # And let the existing `run_logistics_optimization` celery task pick it up!

        return {
            "status": "success",
            "message": "Biomass evaluated successfully.",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/seed_2025_farms")
async def seed_2025_farms_endpoint(background_tasks: BackgroundTasks):
    """
    Reads the 2025 dataset, runs PatchTST to get harvest dates,
    and seeds the database with Users, Farms, and BiomassListings.
    """
    # Using background task to avoid blocking the API request for long inference
    background_tasks.add_task(seed_2025_data)
    return {"message": "2025 data seeding triggered in the background. Check server logs."}
