# 7. Cómo funciona el multitenant (para explicarlo)

Este documento resume, en lenguaje sencillo, qué pasa por dentro cuando pruebas la API
([04-probar-multitenant.md](04-probar-multitenant.md)) y termina con un guion para
presentarlo. El detalle técnico completo está en [01-arquitectura.md](01-arquitectura.md).

## 7.1. La idea en una analogía

Piensa en un edificio de oficinas:

- **`control_db` es la recepción.** Tiene la lista de personas (`users`), de empresas
  (`tenants`) y de quién trabaja en qué empresa y con qué rol (`memberships`). No guarda
  ninguna tarea.
- **Cada organización tiene su propia oficina con llave propia**: una base de datos
  PostgreSQL `tenant_<id>` con su propio usuario y contraseña. Ahí, y solo ahí, están sus
  tareas.
- **El JWT es el carné de identidad**: dice *quién eres*, pero no a qué oficina puedes
  entrar.
- **La recepción comprueba en cada visita** que tu nombre está en la lista de esa empresa
  antes de darte la llave. Si te quitan de la lista, la siguiente vez ya no entras, aunque tu
  carné siga vigente.

## 7.2. Qué ocurre en cada paso de la prueba

| Lo que haces en Swagger | Lo que pasa por dentro |
|-------------------------|------------------------|
| `POST /auth/register` | Se guarda el usuario en `control_db.users`. La contraseña se transforma con **Argon2** (hash lento y con sal); nunca se guarda ni se devuelve en claro. |
| `POST /auth/login` | Se compara la contraseña con el hash y se emite un **JWT** firmado (HS256) con `sub` (id del usuario), `iat`, `exp` (60 min) e `iss`. |
| **Authorize** | Swagger añade `Authorization: Bearer <token>` a cada petición. |
| `POST /tenants` | 1) Se registra la organización en `control_db.tenants` como `provisioning` y al creador como `owner`. 2) Con un usuario de PostgreSQL especial (`tenant_provisioner`, que no es superusuario) se crea un **rol** y una **base de datos** nuevos para esa organización, cerrada a todos los demás. 3) La contraseña de ese rol se guarda en **Secrets Manager**. 4) Se aplican las migraciones (la tabla `tasks`). 5) Estado `active` → **201**. |
| `POST /tenants/{id}/tasks` | Ver el recorrido de 7.3. La tarea se guarda en la base de esa organización, en una tabla `tasks` que **no tiene columna `tenant_id`**: no la necesita, porque la base entera es de una sola organización. |
| Beto pide algo de Acme | El paso de membresía falla y responde **404** antes de tocar la base de Acme. |
| Ana quita a Beto | Se borra la fila de `memberships`. La próxima petición de Beto ya falla, aunque su token no haya caducado. |

## 7.3. El recorrido de una petición

`GET /api/v1/tenants/{tenant_id}/tasks` con un token:

1. **¿Quién eres?** Se verifica el JWT: firma, caducidad, emisor y que el usuario exista y
   esté activo. Si falla → **401**.
2. **¿Puedes entrar aquí?** Con el `tenant_id` de la URL se busca en `control_db` la
   organización y la membresía del usuario. No existe la organización, o no eres miembro →
   **404** (la misma respuesta en los dos casos). Existe pero no está activa → **409**.
3. **¿Con qué llave?** El nombre de la base y el secreto se sacan **del registro de
   `control_db`**, nunca de lo que envía el cliente. Se lee el secreto, se comprueba que es
   de esa organización y se abre una sesión **solo** contra esa base.
4. **El caso de uso** (por ejemplo `ListTasks`) trabaja con esa sesión. No recibe ni
   filtra por `tenant_id`: es imposible que lea tareas de otra base.
5. **Se cierra la sesión** al terminar (commit, o rollback si hubo error). No queda guardado
   "el tenant actual" en ninguna variable global, así que dos peticiones seguidas en la misma
   Lambda no se mezclan.

El código de estos pasos: `presentation/http/dependencies.py` (`get_current_user`,
`get_tenant_access`, `get_tenant_session`), `application/tenants/resolve_tenant.py` e
`infrastructure/tenancy/tenant_database_factory.py`.

## 7.4. Los códigos de respuesta y por qué

| Código | Cuándo | Por qué así |
|--------|--------|-------------|
| **401** | Sin token, token inventado, manipulado o caducado; login incorrecto | No sabemos quién eres. El login fallido da el mismo mensaje exista o no el email, para no revelar qué emails están registrados. |
| **404** | Organización ajena **o** inexistente | Mismo error en ambos casos: un intruso no puede descubrir qué organizaciones existen probando ids. |
| **403** | Eres miembro, pero tu rol no alcanza (un `member` intenta gestionar miembros) | Aquí ya sabes que la organización existe, así que no hay nada que ocultar. |
| **409** | Email o slug repetido; organización no activa | Conflicto con el estado actual. |
| **422** | Datos mal formados o campos no permitidos (`database_name`) | Los schemas rechazan campos extra (`extra="forbid"`): nadie puede colar datos internos. |
| **503** | Falló la creación de la base de una organización | Queda en `failed` y se puede reintentar; no se pierde. |

Todos los errores tienen la misma forma: `{"error": {"code", "message", "request_id"}}`,
sin trazas, SQL ni nombres de bases. El `request_id` permite encontrar la petición en
CloudWatch.

## 7.5. Buenas prácticas aplicadas

**Aislamiento**

- **Una base de datos por organización** (aislamiento físico): un `WHERE` olvidado no puede
  filtrar datos de otra empresa, y se puede respaldar o borrar una organización entera.
- **Un usuario de PostgreSQL por organización**, con acceso solo a su base
  (`REVOKE ALL … FROM PUBLIC`). Aunque alguien robara la contraseña de Acme, no abriría Globex
  ni `control_db`.
- **Mínimo privilegio**: ese usuario solo puede leer y escribir filas; no puede crear ni
  borrar tablas. La API usa para `control_db` otro usuario limitado (`app_central`), y crear
  bases lo hace un tercero (`tenant_provisioner`) que tampoco es superusuario.
- **El tenant se valida en cada petición** contra `control_db`; no se confía en el cliente
  ni en datos guardados en el token.

**Autenticación y secretos**

- Contraseñas con **Argon2**, nunca en claro ni en respuestas o logs.
- **JWT** con caducidad corta, emisor obligatorio y algoritmo fijo (rechaza `alg: none`).
- Las contraseñas de las bases viven en **AWS Secrets Manager**, no en el código ni en
  variables de entorno. La base de datos (RDS) está en una red privada sin acceso desde
  internet.

**Arquitectura y operación**

- **Clean Architecture**: dominio y casos de uso no dependen de FastAPI ni de PostgreSQL;
  eso permite probarlos y cambiar piezas sin reescribir la lógica.
- **Conexiones controladas**: caché limitada de conexiones por organización, con caducidad,
  para no agotar PostgreSQL cuando Lambda escala.
- **Migraciones versionadas** (Alembic) separadas para `control_db` y para las bases de
  tenant; un comando las aplica a todas.
- **Provisión idempotente**: si falla, la organización queda en `failed` y reintentar
  completa lo que faltaba.
- **Pruebas automáticas** contra PostgreSQL real, incluidas las de seguridad
  (`tests/security/`), en cada pull request; despliegue con GitHub Actions usando **OIDC**
  (sin claves de AWS guardadas en GitHub), con staging antes que producción.

## 7.6. Guion para presentarlo (5–7 minutos)

1. **El problema (30 s).** "Construí una API de tareas para varias empresas. El requisito
   principal es que ninguna empresa pueda ver los datos de otra, ni por error ni a
   propósito."
2. **La decisión (1 min).** "Elegí una base de datos por empresa, más una base central,
   `control_db`, que solo sabe quién es miembro de qué. Es la opción más aislada: aunque
   hubiera un fallo en el código, las tareas de una empresa están físicamente en otra base,
   con otro usuario y otra contraseña."
3. **Demo: alta (1–2 min).** En Swagger: registro a Ana y a Beto, hago login, autorizo con
   el token. Cada uno crea su organización. "En este momento se acaba de crear una base de
   datos nueva para Acme, con su propia contraseña guardada en Secrets Manager." Ana crea una
   tarea.
4. **Demo: el ataque (1–2 min).** Con el token de Beto intento leer, modificar y borrar la
   tarea de Acme → 404. Uso el id de esa tarea dentro de Globex → 404, porque esa tarea no
   existe en la base de Globex. Pruebo un id inventado → la misma respuesta: "no le doy a
   Beto ninguna pista de si Acme existe". Sin token o con un token falso → 401.
5. **Demo: membresías (1 min).** Ana invita a Beto → Beto entra. Beto intenta invitar a
   alguien → 403, porque es `member`, no `owner`. Ana lo quita → con el mismo token Beto ya
   no entra: "la membresía se comprueba en cada petición".
6. **Por dentro (1 min).** Las tres preguntas de cada petición: ¿quién eres? (JWT), ¿puedes
   entrar? (membresía en `control_db`), ¿con qué llave? (la base y el secreto salen de
   `control_db`, nunca del cliente).
7. **Buenas prácticas y cierre (30 s).** Mínimo privilegio en PostgreSQL, Argon2, secretos
   en Secrets Manager, red privada, Clean Architecture, pruebas de seguridad automáticas y
   despliegue con GitHub Actions y OIDC. "Como siguiente paso: login con Google/GitHub y
   límite de intentos de login."

## 7.7. Preguntas que te pueden hacer

- **¿Por qué no una columna `tenant_id` en una sola base?** Es más simple y escala a más
  clientes, pero un solo `WHERE` olvidado expone datos de otra empresa. Con una base por
  empresa el aislamiento no depende de que el código sea perfecto. El coste: más bases que
  migrar y más conexiones, que se resuelve con el comando de migración masiva y la caché
  limitada de conexiones.
- **¿Por qué el token no lleva la organización?** Porque un usuario puede pertenecer a varias
  y sus permisos pueden cambiar en cualquier momento. Si el token dijera "eres de Acme",
  quitarle el acceso no tendría efecto hasta que caducara.
- **¿Por qué 404 y no 403?** Para no confirmar a un extraño que una organización existe.
- **¿Qué pasa si falla la creación de la base?** La organización queda en `failed`, la API
  responde 503 y se puede reintentar sin perder nada.
- **¿Cuántas organizaciones aguanta?** PostgreSQL maneja bien cientos o pocos miles de bases
  en un servidor. Para más, se repartirían en varios servidores (el registro en `control_db`
  ya guarda a qué base apunta cada una).
