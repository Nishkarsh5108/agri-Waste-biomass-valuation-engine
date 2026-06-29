from app.worker.celery_app import celery_app
import asyncio
import urllib.request
from sqlalchemy.future import select
from app.core.database import AsyncSessionLocal
from app.modules.auth.models import User
from app.modules.listings.models import BiomassListing, ListingStatus
from app.modules.farmers.models import Farm
from app.modules.ml_inference.service import analyze_biomass_image

async def _process_cv_density_async(listing_id: int):
    async with AsyncSessionLocal() as db:
        # 1. Fetch listing
        result = await db.execute(select(BiomassListing).where(BiomassListing.id == listing_id))
        listing = result.scalars().first()
        if not listing or not listing.photo_s3_url:
            return
            
        # 2. Fetch farm to get area
        result = await db.execute(select(Farm).where(Farm.id == listing.farm_id))
        farm = result.scalars().first()
        if not farm:
            return
            
        # 3. Download image bytes
        req = urllib.request.Request(listing.photo_s3_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            image_bytes = response.read()
            
        # 4. Run YOLO Inference
        analysis_results = analyze_biomass_image(image_bytes, farm.area_hectares)
        
        # 5. Update DB
        listing.cv_density_ratio = analysis_results["density_percentage"]
        listing.estimated_tonnage = analysis_results["weight_tons"]
        # Fake a quality score between 0.7 and 1.0 based on weed count
        listing.quality_score = max(0.0, 1.0 - (analysis_results["weed_count"] * 0.05))
        listing.status = ListingStatus.READY
        
        await db.commit()

@celery_app.task
def process_cv_density(listing_id: int):
    asyncio.run(_process_cv_density_async(listing_id))

@celery_app.task
def predict_harvest_dates():
    pass

from app.worker.logistics_optimizer import run_logistics_optimization_async

@celery_app.task
def run_logistics_optimization():
    asyncio.run(run_logistics_optimization_async())
