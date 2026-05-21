from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    from models.database import init_db
    await init_db()
    yield


app = FastAPI(title="Vehicle Sentiment Agent", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/")
async def index():
    return FileResponse("frontend/index.html")
