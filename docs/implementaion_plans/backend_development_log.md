# Backend Development Log

This document serves as an ongoing log of actions taken, decisions made, and the rationale behind them during the backend implementation phase.

## Phase 1: Scaffolding (Completed)
- **Action**: Scaffolded FastAPI folder structure, configuration files, and `requirements.txt`.
- **Decision**: Chose a modular monolith pattern instead of microservices.
- **Why**: Best suited for a small hackathon team. Simplifies local testing and deployment while maintaining clean code boundaries.
- **Decision**: Integrated Supabase (Postgres + PostGIS + Storage), Upstash (Redis), and Celery.
- **Why**: Meets the constraint of 100% free, no-credit-card required infrastructure, while still offloading heavy ML and OR-Tools tasks to background workers.

## Phase 2: Database Schema & Models (Completed)
- **Action**: Created SQLAlchemy models for `User`, `Farm`, and `BiomassListing`.
- **Decision**: Added `geoalchemy2` geometry column (SRID 4326) to the `Farm` model.
- **Why**: Allows us to do PostGIS-native point-in-polygon queries, which guarantees accuracy when validating farmer GPS uploads against their registered plots.
- **Action**: Wrote `alembic.ini`, `alembic/env.py`, and `alembic/script.py.mako` manually to configure database migrations. Added rules to ignore the PostGIS `spatial_ref_sys` table so Alembic doesn't accidentally drop it.

## Phase 3: Authentication (Completed)
- **Action**: Implemented JWT-based authentication using `python-jose` and `passlib[bcrypt]`.
- **Decision**: Added `SECRET_KEY`, `ALGORITHM`, and `ACCESS_TOKEN_EXPIRE_MINUTES` to `app/core/config.py`. For the hackathon MVP, the secret key is hardcoded to simplify setup across the team.
- **Action**: Created schemas, security utils, dependencies (`get_current_user`), and `/auth/register` and `/auth/login` API endpoints.
- **Why**: Allows users to securely register under different roles (FARMER, FACTORY, FLEET_MANAGER) and fetch tokens, locking down protected routes via the `get_current_user` dependency.

## Phase 4: Farmers & Farms (Completed)
- **Action**: Created schemas and endpoints for `POST /farms` and `GET /farms`.
- **Decision**: Used PostGIS built-in functions (`ST_GeomFromGeoJSON` and `ST_AsGeoJSON`) via SQLAlchemy's `func` instead of adding the `shapely` dependency.
- **Why**: Keeps the dependency tree small, lightweight, and delegates the heavy lifting of geometric conversion entirely to the PostgreSQL server. This is much faster and cleaner.

## Phase 5: Listings & File Storage (Completed)
- **Action**: Created the `POST /listings` endpoint which accepts `multipart/form-data` containing the farm ID and a CV smartphone photo.
- **Action**: Implemented `app/core/storage.py` using the official Supabase python client to upload photos to the `biomass-photos` storage bucket and generate a public URL.
- **Decision**: Triggered the Celery background task `process_cv_density` synchronously right after committing the `BiomassListing` to the database.
- **Why**: Keeps the API request extremely fast for the farmer uploading from the field on a slow connection. The heavy ML CV model is queued via Redis/Upstash to run in the background.

## Phase 6: Logistics & ML Integration (Completed)
- **Action**: Created `GET /listings/ready` to allow Fleet Managers to query mature biomass spots.
- **Action**: Created `POST /logistics/trigger` and `GET /logistics/heatmap` for routing triggers and spatial density visualization.
- **Decision**: Pushed the heavy logistics processing (OR-Tools CVRP solver) entirely to the Celery worker queue, immediately returning a `task_id` to the Fleet Manager interface.
- **Why**: Pathfinding algorithms block the main thread severely. By offloading it to Celery, the FastAPI server remains highly responsive, even if it takes the solver 30 seconds to run constraints.

---

*(All backend scaffolding, architecture decisions, and endpoints for the MVP have been successfully implemented.)*
