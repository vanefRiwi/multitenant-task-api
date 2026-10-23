# 4. Probar que el multitenant funciona

Vamos a demostrar, paso a paso, que **dos organizaciones nunca ven los datos de la otra**.
Personajes:

- **Ana**, dueña (`owner`) de la organización **Acme**.
- **Beto**, dueño de la organización **Globex**.

Primero en local (donde además puedes mirar dentro de PostgreSQL) y después en AWS.

## 4.0. Preparación

Necesitas una terminal **bash** (macOS, Linux o *Git Bash* en Windows), `curl` y `jq`
(para leer JSON):

- macOS: `brew install jq` · Ubuntu: `sudo apt install jq` · Windows: `winget install jqlang.jq`

Define la URL base:

```bash
# Local (con la API arrancada como en docs/02-desarrollo-local.md)
export BASE=http://localhost:8000
# En AWS sería, por ejemplo:
# export BASE=https://api-staging.tudominio.com
API=$BASE/api/v1
```

## 4.1. La forma rápida: prueba automática

```bash
uv run python scripts/smoke_test.py --base-url $BASE --mode full
```

Hace todo lo de este documento y marca cada comprobación con `OK`. Si algo falla, termina
con `FALLO: …`. Úsala siempre, pero haz la versión manual al menos una vez para entender qué
está pasando.

## 4.2. La forma manual, paso a paso

### Paso 1. Registrar a Ana y a Beto

```bash
curl -s -X POST $API/auth/register -H 'Content-Type: application/json' \
  -d '{"email": "ana@example.com", "password": "clave-de-ana-123"}' | jq
curl -s -X POST $API/auth/register -H 'Content-Type: application/json' \
  -d '{"email": "beto@example.com", "password": "clave-de-beto-123"}' | jq
```

Esperado: `201` con `id`, `email`, `is_active`. Nunca aparece la contraseña.

### Paso 2. Iniciar sesión y guardar los tokens

```bash
ANA=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d '{"email": "ana@example.com", "password": "clave-de-ana-123"}' | jq -r .access_token)
BETO=$(curl -s -X POST $API/auth/login -H 'Content-Type: application/json' \
  -d '{"email": "beto@example.com", "password": "clave-de-beto-123"}' | jq -r .access_token)

curl -s $API/auth/me -H "Authorization: Bearer $ANA" | jq   # Ana
```

> Puedes ver qué lleva dentro un token pegándolo en <https://jwt.io> (solo con datos de
> prueba): `sub` (id del usuario), `iat`, `exp`, `iss`.

### Paso 3. Cada uno crea su organización

```bash
ACME=$(curl -s -X POST $API/tenants -H "Authorization: Bearer $ANA" \
  -H 'Content-Type: application/json' -d '{"name": "Acme", "slug": "acme"}' | tee /dev/stderr | jq -r .id)
GLOBEX=$(curl -s -X POST $API/tenants -H "Authorization: Bearer $BETO" \
  -H 'Content-Type: application/json' -d '{"name": "Globex", "slug": "globex"}' | tee /dev/stderr | jq -r .id)
```

Esperado: `"status": "active"` y `"role": "owner"`. En ese segundo el sistema creó **una base
de datos nueva** por organización.

### Paso 4. Cada uno crea tareas

```bash
TAREA_ACME=$(curl -s -X POST $API/tenants/$ACME/tasks -H "Authorization: Bearer $ANA" \
  -H 'Content-Type: application/json' \
  -d '{"title": "Plan secreto de Acme", "priority": "high"}' | jq -r .id)

curl -s -X POST $API/tenants/$GLOBEX/tasks -H "Authorization: Bearer $BETO" \
  -H 'Content-Type: application/json' -d '{"title": "Plan de Globex"}' | jq .title
```

### Paso 5. Verificar el aislamiento

Cada comando muestra solo el código HTTP (`-o /dev/null -w '%{http_code}\n'`).

| # | Prueba | Comando | Esperado |
|---|--------|---------|----------|
| a | Beto lista sus organizaciones: solo ve Globex | `curl -s $API/tenants -H "Authorization: Bearer $BETO" \| jq '.[].name'` | `"Globex"` |
| b | Beto intenta ver Acme | `curl -s -o /dev/null -w '%{http_code}\n' $API/tenants/$ACME -H "Authorization: Bearer $BETO"` | `404` |
| c | Beto intenta listar las tareas de Acme | `curl -s -o /dev/null -w '%{http_code}\n' $API/tenants/$ACME/tasks -H "Authorization: Bearer $BETO"` | `404` |
| d | Beto intenta leer la tarea de Acme por su id | `curl -s -o /dev/null -w '%{http_code}\n' $API/tenants/$ACME/tasks/$TAREA_ACME -H "Authorization: Bearer $BETO"` | `404` |
| e | Beto usa el id de la tarea de Acme dentro de **su** organización | `curl -s -o /dev/null -w '%{http_code}\n' $API/tenants/$GLOBEX/tasks/$TAREA_ACME -H "Authorization: Bearer $BETO"` | `404` |
| f | Beto intenta borrarla | `curl -s -o /dev/null -w '%{http_code}\n' -X DELETE $API/tenants/$ACME/tasks/$TAREA_ACME -H "Authorization: Bearer $BETO"` | `404` |
| g | Sin token | `curl -s -o /dev/null -w '%{http_code}\n' $API/tenants/$ACME/tasks` | `401` |
| h | Token falso | `curl -s -o /dev/null -w '%{http_code}\n' $API/auth/me -H "Authorization: Bearer abc.def.ghi"` | `401` |
| i | Intentar elegir la base de datos al crear una organización | `curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/tenants -H "Authorization: Bearer $BETO" -H 'Content-Type: application/json' -d '{"name":"x","slug":"xx-1","database_name":"control_db"}'` | `422` |
| j | Ana sigue viendo solo lo suyo | `curl -s $API/tenants/$ACME/tasks -H "Authorization: Bearer $ANA" \| jq '.items[].title'` | `"Plan secreto de Acme"` |

¿Por qué **404** y no 403? Para que un intruso ni siquiera sepa si la organización existe.

### Paso 6. Membresías: dar y quitar acceso

```bash
# Ana invita a Beto a Acme como "member"
curl -s -X POST $API/tenants/$ACME/members -H "Authorization: Bearer $ANA" \
  -H 'Content-Type: application/json' -d '{"email": "beto@example.com"}' | jq

# Ahora Beto sí ve Acme (200) y puede crear tareas
curl -s -o /dev/null -w '%{http_code}\n' $API/tenants/$ACME/tasks -H "Authorization: Bearer $BETO"

# Beto (member) NO puede invitar a nadie: 403
curl -s -o /dev/null -w '%{http_code}\n' -X POST $API/tenants/$ACME/members \
  -H "Authorization: Bearer $BETO" -H 'Content-Type: application/json' -d '{"email": "ana@example.com"}'

# Ana revoca a Beto
BETO_ID=$(curl -s $API/auth/me -H "Authorization: Bearer $BETO" | jq -r .id)
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE $API/tenants/$ACME/members/$BETO_ID \
  -H "Authorization: Bearer $ANA"      # 204

# Con el MISMO token (aún válido), Beto ya no entra: 404
curl -s -o /dev/null -w '%{http_code}\n' $API/tenants/$ACME/tasks -H "Authorization: Bearer $BETO"
```

La membresía se comprueba en **cada** petición, por eso la revocación es inmediata.

### Paso 7 (solo local). Mirar dentro de PostgreSQL

Aquí se ve que el aislamiento es **físico**: bases de datos distintas.

```bash
docker compose exec db psql -U postgres
```

```sql
-- Bases de datos: control_db y una tenant_<id> por organización
\l
-- Qué sabe la base central de cada organización (sin contraseñas, solo la referencia)
\c control_db
SELECT name, slug, database_name, status, secret_arn FROM tenants;
SELECT u.email, t.slug, m.role FROM memberships m
  JOIN users u ON u.id = m.user_id JOIN tenants t ON t.id = m.tenant_id;
-- Entra en la base de Acme (copia su database_name de la consulta anterior)
\c tenant_xxxxxxxx
SELECT title FROM tasks;          -- solo "Plan secreto de Acme"
\q
```

### Paso 8 (solo local). Las credenciales de un tenant no abren otro

Cada organización tiene su propio usuario de PostgreSQL. En local sus secretos están en
`.local-secrets/`:

```bash
ls .local-secrets/
cat .local-secrets/multitenant-task-api__local__tenants__tenant_<id_de_acme>.json
```

Con el usuario y la contraseña de **Acme**, intenta entrar en la base de **Globex**:

```bash
docker compose exec -e PGPASSWORD='<password de acme>' db \
  psql -h localhost -U tenant_<id_de_acme> -d tenant_<id_de_globex>
# FATAL:  permission denied for database "tenant_<id_de_globex>"
```

Y tampoco puede crear tablas en la suya:

```bash
docker compose exec -e PGPASSWORD='<password de acme>' db \
  psql -h localhost -U tenant_<id_de_acme> -d tenant_<id_de_acme> -c 'CREATE TABLE x (id int);'
# ERROR:  permission denied for schema public
```

### Paso 9 (solo local). Una organización no activa queda bloqueada

```bash
docker compose exec db psql -U postgres -d control_db \
  -c "UPDATE tenants SET status = 'suspended' WHERE slug = 'acme';"
curl -s $API/tenants/$ACME/tasks -H "Authorization: Bearer $ANA" | jq .error.code
# "tenant_not_active"  (HTTP 409)
docker compose exec db psql -U postgres -d control_db \
  -c "UPDATE tenants SET status = 'active' WHERE slug = 'acme';"
```

## 4.3. En AWS

1. `export BASE=https://api-staging.tudominio.com` (o la `ApiUrl` del stack) y repite
   **4.1** y los pasos **1 a 6**. Los resultados deben ser idénticos.
   - Usa emails y slugs nuevos si ya los usaste (o los del smoke test, que son aleatorios).
2. **Secrets Manager** (consola, región us-east-1): verás un secreto por organización,
   `multitenant-task-api/staging/tenants/tenant_<id>`. Ábrelo → *Retrieve secret value*: su
   `dbname` y `username` son los de esa organización y de ninguna otra.
3. **CloudWatch Logs** → grupo de `ApiFunction`: verás las peticiones de Beto con `-> 404` y
   ninguna contraseña ni token en los mensajes.
4. **Organización fallida** (opcional): si alguna queda en `failed`, reintenta la provisión:

   ```bash
   scripts/invoke_ops.sh "$OPS" '{"action": "provision_tenant", "tenant_id": "<id>"}'
   ```

La base de datos de RDS es privada, así que en AWS no se ejecutan los pasos 7–9 a mano:
esas mismas comprobaciones las hacen las pruebas automáticas (`tests/security/`) en cada
pull request, contra un PostgreSQL real.

## 4.4. Qué cubre cada prueba automática

| Escenario del enunciado | Prueba |
|--------------------------|--------|
| Registro e inicio de sesión correctos | `tests/api/test_auth.py` |
| Rechazo de tokens inválidos o expirados | `tests/security/test_authentication.py` |
| Crear organización y rol `owner` | `tests/api/test_tenants.py` |
| CRUD completo de tareas (+ paginación) | `tests/api/test_tasks.py` |
| Rechazo de accesos a organizaciones ajenas | `tests/security/test_tenant_isolation.py` |
| Bloqueo de tenants no activos | `test_tenant_isolation.py::test_inactive_tenant_is_blocked` |
| Revocación de membresía | `test_tenant_isolation.py::test_revoked_membership_loses_access_immediately` |
| Migraciones aplicadas | `tests/integration/test_migrations.py` |
| Recuperación ante errores de conexión y provisión | `tests/integration/test_provisioning_recovery.py`, `tests/security/test_error_handling.py` |
| Sesiones que no se mezclan entre tenants, caché limitada | `tests/integration/test_tenant_connections.py` |
| Permisos mínimos de PostgreSQL | `tests/security/test_database_permissions.py` |
| Sin información sensible en respuestas y logs | `tests/security/test_error_handling.py` |
