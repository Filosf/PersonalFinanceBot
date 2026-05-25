from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router
from app.core.logging import configure_logging
from app.web.routes import router as web_router

configure_logging()

app = FastAPI(title="Personal Finance Bot Dashboard")
app.state.templates = Jinja2Templates(directory="app/web/templates")
app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
app.include_router(api_router)
app.include_router(web_router)
