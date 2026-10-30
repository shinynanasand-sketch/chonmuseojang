from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import Response as StarletteResponse

from config import PRESENTATION_MODE
from routers import kakao, operator, web
from services import kakao_client
from services.kakao_client import skill_http_response

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="체험마을 AI사무장", version="0.1.0")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["presentation_mode"] = PRESENTATION_MODE
app.state.templates = templates

class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> StarletteResponse:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=86400, stale-while-revalidate=604800"
            response.headers["Vercel-CDN-Cache-Control"] = (
                "public, s-maxage=86400, stale-while-revalidate=604800"
            )
        return response


app.mount("/static", CachedStaticFiles(directory=str(BASE_DIR / "static")), name="static")

app.include_router(web.router)
app.include_router(operator.router)
app.include_router(kakao.router)


def _is_kakao_path(request: Request) -> bool:
    return request.url.path.startswith("/kakao")


@app.exception_handler(RequestValidationError)
async def kakao_validation_handler(request: Request, exc: RequestValidationError):
    if _is_kakao_path(request):
        return skill_http_response(
            kakao_client.build_error_skill_response(
                "요청을 이해하지 못했습니다. 다시 입력해 주세요."
            )
        )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def kakao_unhandled_handler(request: Request, exc: Exception):
    if _is_kakao_path(request):
        return skill_http_response(
            kakao_client.build_error_skill_response("잠시 후 다시 시도해 주세요.")
        )
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
