# Backend Implementation Checklist

- `[x]` 1. **Phase 1: Project Scaffolding**

  - Folder structure, config, database connector, routers, celery app.
- `[x]` 2. **Phase 2: Database Schema & Migrations**

  - `[ ]` Setup Base model in SQLAlchemy.
  - `[ ]` Define `User` model (id, role, phone, hash) in `auth`.
  - `[ ]` Define `Farm` model (id, user_id, geom, area) in `farmers`.
  - `[ ]` Define `BiomassListing` model (farm_id, status, cv_density, dates) in `listings`.
  - `[ ]` Configure `alembic` to autogenerate migration scripts.
  - `[ ]` Apply migrations to the Supabase Postgres instance.
- `[x]` 3. **Phase 3: Authentication Module**

  - `[ ]` Implement JWT token generation & password hashing.
  - `[ ]` Build `/auth/register` and `/auth/login` endpoints.
  - `[ ]` Create `get_current_user` FastAPI dependency for protected routes.
- `[ ]` 4. **Phase 4: Farmers & Farms Module**

  - `[ ]` Build endpoint: `POST /farms` to register a farm (accepts GeoJSON polygon).
  - `[ ]` Build endpoint: `GET /farms` to fetch farms owned by the logged-in farmer.
- `[ ]` 5. **Phase 5: Listings & File Storage**

  - `[ ]` Implement Supabase Storage utility for file uploads.
  - `[ ]` Build endpoint: `POST /listings` to create a listing + upload image.
  - `[ ]` Wire Celery task `process_cv_density` to trigger after upload.
- `[ ]` 6. **Phase 6: Logistics & ML Integration**

  - `[ ]` Build endpoint: `GET /listings/ready` to fetch active listings.
  - `[ ]` Build endpoint: `POST /logistics/trigger` to run OR-Tools CVRP.
  - `[ ]` Build endpoint: `GET /logistics/heatmap` to expose routing data.
  - `[ ]` Wire up `predict_harvest_dates` scheduled task for PatchTST.
