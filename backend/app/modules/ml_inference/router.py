from fastapi import APIRouter

router = APIRouter(prefix="/ml_inference", tags=["ML Inference"])

@router.post("/run_predictions")
async def run_predictions():
    return {"message": "ML Inference trigger"}
