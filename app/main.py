import logging

from fastapi import FastAPI

from routers import audio, youtube

app = FastAPI()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

app.include_router(audio.router)
app.include_router(youtube.router)

# Using FastAPI instance
@app.get("/url-list")
def get_all_urls():
    url_list = [{"path": route.path, "name": route.name} for route in app.routes]
    return url_list