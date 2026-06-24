from app.worker.celery_app import celery_app

@celery_app.task
def process_cv_density(listing_id: int):
    # TODO: Fetch image from Supabase Storage
    # TODO: Run U-Net/MobileNet model
    # TODO: Update DB with density ratio
    pass

@celery_app.task
def predict_harvest_dates():
    # TODO: Run PatchTST inference for all active farms
    pass

@celery_app.task
def run_logistics_optimization():
    # TODO: Fetch READY listings > 3 days old
    # TODO: Run OR-Tools CVRP
    # TODO: Save route manifest
    pass
