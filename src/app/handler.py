"""Punto de entrada de AWS Lambda para la API (API Gateway -> Lambda -> FastAPI)."""

from mangum import Mangum

from app.main import app

handler = Mangum(app, lifespan="off")
