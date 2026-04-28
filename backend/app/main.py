from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.shipments import router as shipments_router
from app.controllers.api.v1 import api_v1_router
from app.core.config import settings
from app.core.logging import RequestContextMiddleware, configure_logging
from app.db.database import Base, engine

Base.metadata.create_all(bind=engine)
configure_logging()

app = FastAPI(title=settings.app_name, version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(shipments_router)
app.include_router(api_v1_router)
app.add_middleware(RequestContextMiddleware)


@app.get("/health")
def health():
    return {"status": "ok"}
