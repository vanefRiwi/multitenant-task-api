"""Selección de la conexión de cada tenant, con caché limitada y con caducidad.

Por qué existe: crear un engine por petición abriría una conexión nueva cada vez y
agotaría PostgreSQL cuando Lambda escala. Aquí cada contenedor Lambda mantiene como
máximo `tenant_engine_cache_size` engines (uno por tenant), cada uno con un pool
pequeño, y los descarta tras `tenant_engine_ttl_seconds` (así también se recogen
credenciales rotadas). La caché NO guarda "el tenant actual": solo recursos de conexión
indexados por tenant, y cada petición pide explícitamente el suyo.
"""

import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Engine
from sqlmodel import Session

from app.config.settings import Settings
from app.domain.entities.tenant import Tenant
from app.domain.exceptions import ServiceUnavailableError, TenantNotActiveError
from app.infrastructure.database.credentials import DatabaseCredentials, build_url
from app.infrastructure.database.engine import create_pg_engine
from app.infrastructure.database.tenant import tenant_session
from app.infrastructure.secrets.secret_provider import SecretProvider


@dataclass(slots=True)
class _CachedEngine:
    key: tuple[str, str]
    engine: Engine
    created_at: float


class TenantDatabaseFactory:
    def __init__(
        self,
        settings: Settings,
        secrets: SecretProvider,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._settings = settings
        self._secrets = secrets
        self._clock = clock
        self._max_engines = settings.tenant_engine_cache_size
        self._ttl = settings.tenant_engine_ttl_seconds
        self._cache: OrderedDict[UUID, _CachedEngine] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def cached_tenants(self) -> list[UUID]:
        with self._lock:
            return list(self._cache)

    def session(self, tenant: Tenant) -> Iterator[Session]:
        yield from tenant_session(self.get_engine(tenant))

    def get_engine(self, tenant: Tenant) -> Engine:
        if not tenant.is_active or not tenant.secret_arn:
            raise TenantNotActiveError()
        key = (tenant.database_name, tenant.secret_arn)
        now = self._clock()

        with self._lock:
            entry = self._cache.get(tenant.id)
            if entry and entry.key == key and now - entry.created_at < self._ttl:
                self._cache.move_to_end(tenant.id)
                return entry.engine
            if entry:
                self._discard(tenant.id)

        engine = self._create_engine(tenant)  # fuera del lock: lee un secreto (red)

        with self._lock:
            existing = self._cache.get(tenant.id)
            if existing and existing.key == key:  # otro hilo se adelantó
                engine.dispose()
                return existing.engine
            if existing:
                self._discard(tenant.id)
            self._cache[tenant.id] = _CachedEngine(key=key, engine=engine, created_at=now)
            while len(self._cache) > self._max_engines:
                oldest = next(iter(self._cache))
                self._discard(oldest)
            return engine

    def dispose_all(self) -> None:
        with self._lock:
            for tenant_id in list(self._cache):
                self._discard(tenant_id)

    def _discard(self, tenant_id: UUID) -> None:
        entry = self._cache.pop(tenant_id)
        entry.engine.dispose()

    def _create_engine(self, tenant: Tenant) -> Engine:
        try:
            data = self._secrets.get_json(str(tenant.secret_arn))
        except Exception as exc:
            raise ServiceUnavailableError() from exc
        # Defensa en profundidad: el secreto debe corresponder EXACTAMENTE a este tenant.
        if data.get("dbname") != tenant.database_name or data.get("username") != (
            tenant.database_name
        ):
            raise ServiceUnavailableError()
        credentials = DatabaseCredentials(username=data["username"], password=data["password"])
        return create_pg_engine(
            self._settings,
            build_url(self._settings, credentials, tenant.database_name),
            pool_size=self._settings.tenant_pool_size,
            max_overflow=self._settings.tenant_max_overflow,
        )
