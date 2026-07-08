from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from datetime import datetime, timezone
import uuid

from app.core.database import get_db
from app.modules.auth.models import User, UserRole
from app.core.dependencies import get_current_user
from app.modules.listings.models import BiomassListing, ListingStatus
from app.modules.farmers.models import Farm
from app.modules.listings.schemas import ListingOut
from app.core.storage import upload_image
from app.worker.tasks import _process_cv_density_async

router = APIRouter(prefix="/listings", tags=["Listings"])

@router.post("/", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
async def create_listing(
    background_tasks: BackgroundTasks,
    farm_id: int = Form(...),
    photo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=403, detail="Only farmers can create listings.")

    # Validate that the farm belongs to the user
    result = await db.execute(select(Farm).where(Farm.id == farm_id, Farm.user_id == current_user.id))
    farm = result.scalars().first()
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found or not owned by you.")

    # Upload photo to Supabase
    file_bytes = await photo.read()
    filename = f"{farm_id}_{uuid.uuid4().hex}_{photo.filename}"
    try:
        public_url = upload_image(file_bytes, filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image upload failed: {str(e)}")

    # Create listing in database
    new_listing = BiomassListing(
        farm_id=farm_id,
        status=ListingStatus.PROCESSING,
        photo_s3_url=public_url,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(new_listing)
    await db.commit()
    await db.refresh(new_listing)

    # Trigger async background task to run ML CV model via FastAPI
    background_tasks.add_task(_process_cv_density_async, new_listing.id)

    return new_listing

@router.get("/ready", response_model=list[ListingOut])
async def get_ready_listings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [UserRole.FACTORY, UserRole.FLEET_MANAGER]:
        raise HTTPException(status_code=403, detail="Only factories or fleet managers can view ready listings.")

    query = select(BiomassListing).where(BiomassListing.status == ListingStatus.READY)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/my", response_model=list[ListingOut])
async def get_my_listings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=403, detail="Only farmers can view their listings.")

    # Fetch listings for all farms owned by the user
    query = (
        select(BiomassListing)
        .join(Farm, BiomassListing.farm_id == Farm.id)
        .where(Farm.user_id == current_user.id)
        .order_by(BiomassListing.created_at.desc())
    )
    result = await db.execute(query)
    return result.scalars().all()

@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(
    listing_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != UserRole.FARMER:
        raise HTTPException(status_code=403, detail="Only farmers can delete listings.")

    # Fetch the listing and ensure the farm belongs to the user
    query = (
        select(BiomassListing)
        .join(Farm, BiomassListing.farm_id == Farm.id)
        .where(BiomassListing.id == listing_id, Farm.user_id == current_user.id)
    )
    result = await db.execute(query)
    listing = result.scalars().first()

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found or not owned by you.")

    await db.execute(delete(BiomassListing).where(BiomassListing.id == listing_id))
    await db.commit()
    return None
