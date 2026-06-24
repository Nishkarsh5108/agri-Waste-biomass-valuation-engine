from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modules.auth.router import router as auth_router
from app.modules.farmers.router import router as farmers_router
from app.modules.factories.router import router as factories_router
from app.modules.listings.router import router as listings_router
from app.modules.logistics.router import router as logistics_router
from app.modules.ml_inference.router import router as ml_inference_router

app = FastAPI(
    title="AVBE Backend",
    description="Agri-Waste Biomass Valuation Engine - Backend API",
    version="1.0.0"
)

# CORS configuration for the Hackathon Demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(farmers_router)
app.include_router(factories_router)
app.include_router(listings_router)
app.include_router(logistics_router)
app.include_router(ml_inference_router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "AVBE API is running"}
