"""Prueba de humo contra una API desplegada (local, staging o producción).

    # Solo salud (seguro para producción):
    uv run python scripts/smoke_test.py --base-url https://api.tudominio.com --mode health

    # Recorrido completo multitenant: 2 usuarios, 2 organizaciones, aislamiento.
    uv run python scripts/smoke_test.py --base-url https://api.tudominio.com --mode full

El modo `full` crea datos reales (usuarios y 2 bases de datos de tenant): úsalo en local
o staging, no en producción.
"""

import argparse
import secrets
import sys
from typing import Any

import httpx


class SmokeTestError(Exception):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeTestError(message)
    print(f"  OK  {message}")


class Api:
    def __init__(self, base_url: str) -> None:
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=30)

    def call(
        self, method: str, path: str, token: str | None = None, **kwargs: Any
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.request(method, f"/api/v1{path}", headers=headers, **kwargs)

    def register_and_login(self, email: str, password: str) -> str:
        response = self.call("POST", "/auth/register", json={"email": email, "password": password})
        check(response.status_code == 201, f"registro de {email} -> 201")
        response = self.call("POST", "/auth/login", json={"email": email, "password": password})
        check(response.status_code == 200, f"login de {email} -> 200")
        return str(response.json()["access_token"])


def health(api: Api) -> None:
    print("Salud")
    check(api.client.get("/health").json() == {"status": "ok"}, "/health responde ok")
    response = api.client.get("/health/ready")
    check(response.status_code == 200, "/health/ready: la API llega a la base de datos")


def full(api: Api) -> None:
    run = secrets.token_hex(4)
    password = secrets.token_urlsafe(16)
    print(f"Recorrido multitenant (id de ejecución: {run})")

    ana = api.register_and_login(f"ana-{run}@example.com", password)
    beto = api.register_and_login(f"beto-{run}@example.com", password)
    me = api.call("GET", "/auth/me", ana)
    check(me.status_code == 200 and me.json()["email"] == f"ana-{run}@example.com", "/auth/me")

    acme = api.call("POST", "/tenants", ana, json={"name": "Acme", "slug": f"acme-{run}"})
    check(acme.status_code == 201, "Ana crea la organización Acme -> 201")
    check(acme.json()["role"] == "owner" and acme.json()["status"] == "active", "Ana es owner")
    globex = api.call("POST", "/tenants", beto, json={"name": "Globex", "slug": f"globex-{run}"})
    check(globex.status_code == 201, "Beto crea la organización Globex -> 201")
    acme_id, globex_id = acme.json()["id"], globex.json()["id"]

    task = api.call("POST", f"/tenants/{acme_id}/tasks", ana, json={"title": "Plan secreto Acme"})
    check(task.status_code == 201, "Ana crea una tarea en Acme")
    api.call("POST", f"/tenants/{globex_id}/tasks", beto, json={"title": "Plan de Globex"})
    task_id = task.json()["id"]

    print("Aislamiento")
    listed = api.call("GET", "/tenants", beto).json()
    check([t["id"] for t in listed] == [globex_id], "Beto solo ve su organización")
    for method, path in [
        ("GET", f"/tenants/{acme_id}"),
        ("GET", f"/tenants/{acme_id}/tasks"),
        ("GET", f"/tenants/{acme_id}/tasks/{task_id}"),
        ("DELETE", f"/tenants/{acme_id}/tasks/{task_id}"),
    ]:
        check(api.call(method, path, beto).status_code == 404, f"Beto {method} {path} -> 404")
    response = api.call("GET", f"/tenants/{globex_id}/tasks/{task_id}", beto)
    check(response.status_code == 404, "La tarea de Acme no existe en la base de Globex")
    titles = [t["title"] for t in api.call("GET", f"/tenants/{acme_id}/tasks", ana).json()["items"]]
    check(titles == ["Plan secreto Acme"], "Acme solo contiene sus tareas")
    check(api.call("GET", "/tenants", None).status_code == 401, "Sin token -> 401")

    print("Membresías")
    added = api.call(
        "POST", f"/tenants/{acme_id}/members", ana, json={"email": f"beto-{run}@example.com"}
    )
    check(added.status_code == 201, "Ana añade a Beto a Acme como member")
    check(api.call("GET", f"/tenants/{acme_id}/tasks", beto).status_code == 200, "Beto ya ve Acme")
    beto_id = api.call("GET", "/auth/me", beto).json()["id"]
    removed = api.call("DELETE", f"/tenants/{acme_id}/members/{beto_id}", ana)
    check(removed.status_code == 204, "Ana revoca a Beto")
    check(
        api.call("GET", f"/tenants/{acme_id}/tasks", beto).status_code == 404,
        "Beto pierde el acceso al instante",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--mode", choices=["health", "full"], default="health")
    args = parser.parse_args()

    api = Api(args.base_url)
    try:
        health(api)
        if args.mode == "full":
            full(api)
    except (SmokeTestError, httpx.HTTPError) as exc:
        print(f"FALLO: {exc}", file=sys.stderr)
        return 1
    print("Todo correcto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
