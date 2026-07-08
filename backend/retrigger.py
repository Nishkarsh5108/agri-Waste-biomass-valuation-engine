import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy.future import select
from app.modules.listings.models import BiomassListing, ListingStatus
from app.worker.tasks import process_cv_density

async def retrigger():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(BiomassListing).where(BiomassListing.status == ListingStatus.PROCESSING))
        listings = res.scalars().all()
        for l in listings:
            process_cv_density.delay(l.id)
        print(f'Retriggered {len(listings)} listings')

if __name__ == '__main__':
    asyncio.run(retrigger())
