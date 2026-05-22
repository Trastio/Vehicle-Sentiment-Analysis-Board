import os
import uvicorn


def ensure_dirs():
    for d in ["data", "data/cookies", "logs"]:
        os.makedirs(d, exist_ok=True)


if __name__ == "__main__":
    ensure_dirs()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("DEV", "").strip() == "1"
    uvicorn.run("api.main:app", host=host, port=port, reload=reload)
