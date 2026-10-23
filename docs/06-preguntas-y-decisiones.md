# 6. Preguntas frecuentes y decisiones técnicas

## ¿Tengo que hacer unit testing obligatoriamente?

**No para este MVP.** El enunciado lo deja explícitamente fuera del alcance ("Incorporar
pruebas de integración, API y seguridad, sin incluir unit testing"). Lo que **sí** es
obligatorio, y ya está hecho, son:

- **Pruebas de integración** (`tests/integration/`): repositorios, sesiones, migraciones y
  provisión contra un PostgreSQL real.
- **Pruebas de API** (`tests/api/`): cada endpoint, validaciones y códigos HTTP.
- **Pruebas de seguridad** (`tests/security/`): tokens, aislamiento entre tenants, permisos
  de PostgreSQL y ausencia de información sensible.

¿Por qué tiene sentido? En una API multitenant, los fallos peligrosos están en las uniones
(sesión equivocada, permisos de PostgreSQL, membresía no comprobada), y eso solo lo detectan
pruebas que usan la base real. Las unitarias (casos de uso con repositorios en memoria, como
en el proyecto ecommerce) son baratas de añadir después porque la arquitectura ya lo permite:
los casos de uso reciben sus repositorios por constructor. Buen candidato para el **MVP 2**.

## ¿Por qué una base de datos por tenant y no una columna `tenant_id`?

Lo pide el enunciado y da el aislamiento más fuerte: un `WHERE` olvidado no puede filtrar
datos, cada tenant tiene su propio usuario de PostgreSQL y se pueden hacer copias o borrados
por organización. El coste: más bases que migrar (por eso existe `migrate_tenants`) y más
conexiones (de ahí la caché limitada).

## RDS Proxy

**Evaluado; no se incluye en el MVP.**

- Qué resuelve: agrupa conexiones de muchas Lambdas en pocas conexiones a PostgreSQL.
- Por qué no ahora:
  - Con una base por tenant, el proxy necesita las credenciales de cada rol de tenant
    registradas en el proxy (o autenticación IAM), lo que complica la provisión automática.
  - Coste fijo adicional (se cobra por vCPU de la instancia; en una `db.t4g.micro` supone
    una parte importante de la factura).
  - El tráfico del MVP no lo justifica: con pool de 1–2 conexiones por contenedor, caché de
    20 tenants y `CONNECTION LIMIT` por rol, se controla el número de conexiones.
- Cuándo activarlo: si la métrica `DatabaseConnections` de RDS se acerca a
  `max_connections` (≈ 80–100 en una `t4g.micro`), o si aparecen errores
  `too many connections`. Antes de eso, sube `LambdaReservedConcurrency` o el tamaño de la
  instancia.

## ¿Por qué HTTP API y no REST API en API Gateway?

Es más barata y rápida, soporta dominio personalizado, certificado ACM y throttling, que es
todo lo que pide el MVP. REST API solo haría falta para funciones como API keys con planes de
uso o WAF directo.

## ¿Por qué no hay NAT Gateway?

Un NAT cuesta ~32 USD/mes por zona. Las Lambdas solo necesitan hablar con RDS (misma VPC) y
con Secrets Manager (a través de un endpoint privado, ~7,5 USD/mes). Si en el futuro la API
necesitara llamar a Internet (p. ej. OAuth con Google), habría que añadir un NAT o endpoints
adicionales.

## ¿Por qué la creación de una organización devuelve 201 y no 202?

La provisión tarda alrededor de un segundo, así que se completa dentro de la petición y la
respuesta ya trae el tenant `active`. Si falla, el tenant queda `failed` y la API responde 503.
Si la provisión se volviera lenta (por ejemplo, con RDS por tenant), se movería a una cola
(SQS) y la respuesta sería **202** con estado `provisioning`.

## ¿Cómo se rotan las contraseñas?

- `app_central` y `tenant_provisioner`: cambia el valor del secreto en Secrets Manager y
  ejecuta la acción `bootstrap` (aplica la nueva contraseña al rol). Las Lambdas la leen en el
  siguiente arranque en frío (o al redesplegar).
- Roles de tenant: la provisión es idempotente; un reintento genera contraseña nueva y
  actualiza el secreto. Los engines en caché caducan solos (`TENANT_ENGINE_TTL_SECONDS`).

## Limitaciones conocidas del MVP

- La provisión es síncrona (ver arriba).
- Sin recuperación de contraseña por email (los correos están fuera de alcance).
- Sin limitación de intentos de login por usuario (API Gateway limita por tasa global).
  Recomendado para el siguiente MVP.
- El pipeline usa un rol con permisos amplios sobre EC2 y RDS (AWS no permite acotarlos bien
  por nombre). Para producción real, lo ideal es una **cuenta de AWS separada** por ambiente.
- El smoke test de staging crea dos organizaciones por despliegue. Puedes limpiarlas desde la
  Lambda de operaciones o recreando el stack de staging.

## Variables de configuración

Todas están en `src/app/config/settings.py` (nombre en mayúsculas como variable de entorno).

| Variable | Por defecto | Para qué |
|----------|-------------|----------|
| `DB_HOST`, `DB_PORT` | `localhost`, `5432` | Servidor PostgreSQL |
| `CONTROL_DB_NAME` | `control_db` | Base central |
| `CENTRAL_DB_USER` / `_PASSWORD` / `_SECRET_ARN` | `app_central` | Usuario de la API para `control_db` |
| `PROVISIONER_DB_USER` / `_PASSWORD` / `_SECRET_ARN` | `tenant_provisioner` | Usuario de provisión |
| `ADMIN_DB_USER` / `_PASSWORD` / `_SECRET_ARN` | `postgres` | Solo bootstrap |
| `SECRET_PROVIDER` | `local` | `local` (archivos) o `aws` (Secrets Manager) |
| `TENANT_SECRET_PREFIX` | `multitenant-task-api/local` | Prefijo de los secretos de tenants |
| `TENANT_DB_PREFIX` | `tenant_` | Prefijo de las bases de tenants |
| `TENANT_DB_CONNECTION_LIMIT` | `5` | Conexiones máximas por rol de tenant |
| `TENANT_ENGINE_CACHE_SIZE` / `_TTL_SECONDS` | `20` / `300` | Caché de conexiones por tenant |
| `JWT_SECRET` / `JWT_SECRET_ARN` | — | Clave de firma (mín. 32 caracteres) |
| `JWT_ISSUER`, `JWT_EXPIRES_MINUTES` | `multitenant-task-api`, `60` | Claims del token |
| `PAGINATION_DEFAULT_LIMIT` / `_MAX_LIMIT` | `20` / `100` | Paginación |
| `EXPOSE_DOCS` | `true` | Publicar `/docs` y `/openapi.json` |
