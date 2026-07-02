import os
import sys
import asyncio
from dotenv import load_dotenv
import glob

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from supabase import create_client, Client
from app.core.database import AsyncSessionLocal
from app.modules.farmers.models import Farm
from app.modules.listings.models import BiomassListing, ListingStatus
from app.worker.tasks import process_cv_density
from sqlalchemy.future import select

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

async def run_seeder():
    print("Starting Demo Seeder...")
    
    # 1. Get images from data/Stubble
    image_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "Stubble"))
    images = glob.glob(os.path.join(image_dir, "*.jpg")) + glob.glob(os.path.join(image_dir, "*.jpeg")) + glob.glob(os.path.join(image_dir, "*.png"))
    
    if not images:
        print(f"No images found in {image_dir}")
        return
        
    print(f"Found {len(images)} images.")
    
    async with AsyncSessionLocal() as db:
        # 2. Get a cluster of farms (let's pick the first N farms to match our image count, or up to 50)
        num_farms_to_seed = min(50, len(images))
        result = await db.execute(select(Farm).limit(num_farms_to_seed))
        farms = result.scalars().all()
        
        if not farms:
            print("No farms found in the database.")
            return
            
        print(f"Seeding {len(farms)} farms.")
        
        for i, farm in enumerate(farms):
            image_path = images[i]
            file_name = os.path.basename(image_path)
            
            print(f"[{i+1}/{len(farms)}] Uploading {file_name} for Farm ID {farm.id}...")
            
            # 3. Upload to Supabase Storage
            # Read file as bytes
            with open(image_path, "rb") as f:
                file_bytes = f.read()
                
            storage_path = f"demo_seed/{farm.id}_{file_name}"
            
            try:
                # Upsert is true to overwrite if it exists
                supabase.storage.from_("biomass-photos").upload(
                    file=file_bytes,
                    path=storage_path,
                    file_options={"content-type": "image/jpeg", "upsert": "true"}
                )
            except Exception as e:
                print(f"Upload failed: {e}")
                # It might already exist, get public URL anyway
                
            # 4. Get public URL
            public_url = supabase.storage.from_("biomass-photos").get_public_url(storage_path)
            
            # 5. Create Biomass Listing
            listing = BiomassListing(
                farm_id=farm.id,
                photo_s3_url=public_url,
                status=ListingStatus.PROCESSING
            )
            db.add(listing)
            await db.commit()
            await db.refresh(listing)
            
            # 6. Trigger Celery Task
            process_cv_density.delay(listing.id)
            print(f" -> Listing {listing.id} created and Celery task dispatched.")

    print("Demo seeding complete! Ensure your Celery worker is running to process the ML models.")

if __name__ == "__main__":
    asyncio.run(run_seeder())
