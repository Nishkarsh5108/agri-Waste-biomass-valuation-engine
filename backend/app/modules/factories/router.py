from fastapi import APIRouter

router = APIRouter(prefix="/factories", tags=["Factories"])

@router.get("/")
async def get_factories():
    return {"message": "Factories endpoint"}
