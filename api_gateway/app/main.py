from contextlib import asynccontextmanager
from fastapi import FastAPI
from .api.v1.endpoints import videos
from .database import engine, Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown (if needed)


app = FastAPI(title="Video Processing API Gateway", lifespan=lifespan)


app.include_router(videos.router, prefix="/api/v1/videos", tags=["videos"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
