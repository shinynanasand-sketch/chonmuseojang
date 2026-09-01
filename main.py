from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from routers import kakao, operator, web

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="체험마을 AI사무장", version="0.1.0")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.state.templates = templates

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(web.router)
app.include_router(operator.router)
app.include_router(kakao.router)
