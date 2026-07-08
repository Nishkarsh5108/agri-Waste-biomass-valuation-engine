import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.modules.listings.models import BiomassListing

async def test():
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(BiomassListing))
        l = res.scalars().first()
        if l:
            await db.delete(l)
            try:
                await db.commit()
                print("Deleted listing successfully")
            except Exception as e:
                print("Error:", e)
        else:
            print("No listings found")

if __name__ == "__main__":
    asyncio.run(test())
