# 4. Probar que el multitenant funciona

Vamos a demostrar, paso a paso, que **dos organizaciones nunca ven los datos de la otra**.
Personajes:

- **Ana**, dueña (`owner`) de la organización **Acme**.
- **Beto**, dueño de la organización **Globex**.

Hay dos formas de hacerlo:

- **4.A. Desde el navegador con Swagger** (recomendada para empezar y para presentar): sin
  instalar nada, contra staging.
- **4.0–4.3. Desde la terminal con `curl`**: más rápida de repetir, y en local permite
  mirar dentro de PostgreSQL.

La explicación de lo que pasa por dentro y un guion para presentarlo están en
[07-explicacion-multitenant.md](07-explicacion-multitenant.md).

## 4.A. Desde el navegador con Swagger (staging)

Abre <https://tasks-api-staging.coderhivex.com/docs>. Cada endpoint se prueba igual:

1. Haz clic en el endpoint para desplegarlo.
2. Pulsa **Try it out**.
3. Rellena los parámetros o edita el JSON del *Request body*.
4. Pulsa **Execute** y mira **Server response**: el código (`201`, `404`…) y el cuerpo.

> **Truco para tener a Ana y a Beto a la vez:** abre `/docs` en una ventana normal (Ana) y
> en una ventana de incógnito (Beto). Cada ventana guarda su propio token, así no tienes
> que cambiar de usuario a cada rato.
>
> **Usa datos nuevos cada vez.** Los emails y los *slugs* son únicos en toda la API: si
> repites `ana@example.com` recibirás `409`. Añade un número, por ejemplo
> `ana1@example.com` y `acme-1`.

Lleva una nota (Bloc de notas) con: token de Ana, token de Beto, id de Acme, id de Globex
e id de la tarea de Acme. Los vas a copiar varias veces.

### A1. Registrar a Ana y a Beto

`POST /api/v1/auth/register` → *Try it out* → body:

```json
{ "email": "ana1@example.com", "password": "clave-de-ana-123" }
```

Esperado: **201** con `id`, `email`, `is_active`, `created_at`. **La contraseña no aparece**
(se guarda como hash Argon2). Repite con `beto1@example.com` / `clave-de-beto-123`.

Prueba extra: registra otra vez a Ana → **409** `user_already_exists`.

### A2. Iniciar sesión y autorizar Swagger

`POST /api/v1/auth/login` con el mismo email y contraseña → **200**:

```json
{ "access_token": "eyJhbGciOi...", "token_type": "bearer", "expires_at": "..." }
```

Copia el valor de `access_token` (sin comillas). Arriba a la derecha pulsa **Authorize**
(el candado), pega el token en *Value* **sin** escribir `Bearer ` delante, pulsa
**Authorize** y **Close**. Desde ahora Swagger envía `Authorization: Bearer <token>` en cada
petición (los candados aparecen cerrados).

Comprueba con `GET /api/v1/auth/me` → **200** con los datos de Ana.

Haz lo mismo con Beto en la ventana de incógnito.

> Si pegas el token en <https://jwt.io> verás su contenido: `sub` (id del usuario), `iat`
> (cuándo se emitió), `exp` (cuándo caduca, 60 min) e `iss` (quién lo emitió). **No lleva
> el tenant**: la organización se indica en la URL y se valida en cada petición. Usa solo
> tokens de prueba en sitios externos.
>
> Contraseña incorrecta → **401** `invalid_credentials`, con el mismo mensaje exista o no
> el email.

### A3. Cada uno crea su organización

Ventana de Ana: `POST /api/v1/tenants`:

```json
{ "name": "Acme", "slug": "acme-1" }
```

Esperado: **201** con `"status": "active"` y `"role": "owner"`. Guarda el `id` (ID_ACME).
En ese momento el sistema creó **una base de datos PostgreSQL nueva** solo para Acme, con su
propio usuario y contraseña (guardados en AWS Secrets Manager).

Ventana de Beto: lo mismo con `{ "name": "Globex", "slug": "globex-1" }` (ID_GLOBEX).

Fíjate en que la respuesta **no** incluye el nombre de la base de datos ni el secreto: esos
datos internos nunca salen por la API.

### A4. Cada uno crea tareas

Ventana de Ana: `POST /api/v1/tenants/{tenant_id}/tasks`, con `tenant_id` = ID_ACME:

```json
{ "title": "Plan secreto de Acme", "priority": "high" }
```

**201**. Guarda el `id` de la tarea (ID_TAREA_ACME). Comprueba con
`GET /api/v1/tenants/{tenant_id}/tasks` que aparece en `items`.

Ventana de Beto: crea `{ "title": "Plan de Globex" }` en ID_GLOBEX.

### A5. Verificar el aislamiento (todo en la ventana de Beto)

| # | Prueba | Endpoint y datos | Esperado |
|---|--------|------------------|----------|
| a | Beto lista sus organizaciones | `GET /tenants` | **200**, solo Globex |
| b | Beto intenta ver Acme | `GET /tenants/{tenant_id}` con ID_ACME | **404** `tenant_not_found` |
| c | Beto intenta listar las tareas de Acme | `GET /tenants/{tenant_id}/tasks` con ID_ACME | **404** `tenant_not_found` |
| d | Beto intenta leer la tarea de Acme | `GET /tenants/{tenant_id}/tasks/{task_id}` con ID_ACME e ID_TAREA_ACME | **404** `tenant_not_found` |
| e | Beto intenta modificarla | `PATCH /tenants/{tenant_id}/tasks/{task_id}` con ID_ACME, body `{"title": "hackeado"}` | **404** `tenant_not_found` |
| f | Beto intenta borrarla | `DELETE /tenants/{tenant_id}/tasks/{task_id}` con ID_ACME | **404** `tenant_not_found` |
| g | Beto usa el id de la tarea de Acme dentro de **su** organización | `GET /tenants/{tenant_id}/tasks/{task_id}` con ID_GLOBEX e ID_TAREA_ACME | **404** `task_not_found` |
| h | Organización que no existe | `GET /tenants/{tenant_id}/tasks` con `00000000-0000-0000-0000-000000000000` | **404** `tenant_not_found` (igual que b) |
| i | Id con formato inválido | `GET /tenants/{tenant_id}/tasks` con `hola` | **422** `validation_error` |
| j | Intentar elegir la base de datos | `POST /tenants` con `{"name": "x", "slug": "x-1", "database_name": "control_db"}` | **422** `extra_forbidden` |
| k | Slug repetido | `POST /tenants` con el slug de Acme | **409** `tenant_slug_already_exists` |

Para **h** y **j** fíjate: la API no distingue "no existe" de "existe pero no es tuya".
Ese es el motivo de responder **404 y no 403**: un intruso no puede ni averiguar qué
organizaciones existen. El **403** se reserva para quien **sí** es miembro pero no tiene el
rol necesario (lo verás en A7).

La prueba **g** es la más interesante: la tarea existe, pero en **otra base de datos**.
Dentro de la base de Globex ese id simplemente no está.

Ventana de Ana: `GET /tenants/{tenant_id}/tasks` con ID_ACME → sigue viendo solo
"Plan secreto de Acme", intacta.

### A6. Sin token y con token inválido

1. En la ventana de Beto pulsa **Authorize → Logout** y ejecuta
   `GET /tenants/{tenant_id}/tasks` → **401** `not_authenticated`.
2. *Authorize* con un token inventado, por ejemplo `abc.def.ghi` → `GET /auth/me` →
   **401** "Token inválido".
3. Token manipulado: toma el token de Beto y cambia una sola letra del final (la firma) →
   **401**. Cualquier cambio en el contenido o la firma invalida el token.
4. Un token caduca a los 60 minutos: pasado ese tiempo también da **401** y hay que volver a
   hacer login.

Vuelve a autorizar a Beto con su token correcto para seguir.

### A7. Membresías: dar y quitar acceso

1. **Ana** invita a Beto: `POST /tenants/{tenant_id}/members` con ID_ACME y
   `{"email": "beto1@example.com"}` → **201**, `"role": "member"`.
2. **Beto** repite la prueba c (`GET` tareas de ID_ACME) → ahora **200**. Su `GET /tenants`
   muestra Acme (como `member`) y Globex (como `owner`).
3. **Beto** intenta invitar a alguien a Acme → **403** `permission_denied` ("Solo un owner
   puede añadir miembros"). Aquí sí es 403: Beto es miembro, pero no tiene permiso.
4. **Ana** busca el `user_id` de Beto con `GET /tenants/{tenant_id}/members` y lo quita:
   `DELETE /tenants/{tenant_id}/members/{user_id}` → **204**.
5. **Beto**, con **el mismo token** (que sigue siendo válido), vuelve a pedir las tareas de
   Acme → **404**. La membresía se comprueba en **cada** petición, así que la revocación es
   inmediata: no hace falta esperar a que caduque el token.

> Nota de diseño: un `member` puede crear, editar y borrar tareas de la organización; solo
> el `owner` gestiona miembros. Si quisieras que un `member` no pudiera borrar, sería una
> regla más en el caso de uso `DeleteTask`.

### A8. Dónde verlo en AWS (consola web)

- **Secrets Manager** (región us-east-1): un secreto por organización,
  `multitenant-task-api/staging/tenants/tenant_<id>`. *Retrieve secret value* muestra que su
  `dbname` y `username` son los de esa organización y de ninguna otra.
- **CloudWatch → Log groups** → el de `ApiFunction`: verás líneas como
  `GET /api/v1/tenants/<id>/tasks -> 404 (9.0 ms) request_id=...`, y ninguna contraseña ni
  token. El `request_id` es el mismo que devuelve la API en los errores, así puedes buscar
  una petición concreta.

---

Lo que sigue es la misma prueba desde la terminal.

## 4.0. Preparación

Necesitas una terminal **bash** (macOS, Linux o *Git Bash* en Windows), `curl` y `jq`
(para leer JSON):

- macOS: `brew install jq` · Ubuntu: `sudo apt install jq` · Windows: `winget install jqlang.jq`

Define la URL base:

```bash
# Local (con la API arrancada como en docs/02-desarrollo-local.md)
export BASE=http://localhost:8000
# En staging:
# export BASE=https://tasks-api-staging.coderhivex.com
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

1. `export BASE=https://tasks-api-staging.coderhivex.com` (o la `ApiUrl` del stack) y repite
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
