from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.routes.vehicle import router as vehicle_router
from api.routes.collection import router as collection_router
from api.routes.analysis import router as analysis_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from models.database import init_db
    await init_db()
    yield


app = FastAPI(title="Vehicle Sentiment Agent", lifespan=lifespan)

app.include_router(vehicle_router)
app.include_router(collection_router)
app.include_router(analysis_router)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/")
async def index():
    return FileResponse("frontend/index.html")
