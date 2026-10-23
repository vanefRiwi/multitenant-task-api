import logging
import sys


def configure_logging(level: str) -> None:
    """Logs en una línea por evento, legibles en CloudWatch Logs."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    if not root.handlers:  # en Lambda ya existe un handler; en local añadimos uno
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
        root.addHandler(handler)
    # SQLAlchemy nunca debe registrar consultas en producción.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
