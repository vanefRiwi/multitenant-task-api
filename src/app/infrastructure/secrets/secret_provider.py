"""Acceso a secretos (credenciales de bases de datos y clave JWT).

- AwsSecretsManagerProvider: AWS Secrets Manager (staging/producción).
- LocalFileSecretProvider: archivos JSON en una carpeta local ignorada por git
  (desarrollo y pruebas). Imita el mismo contrato para que el resto del código no cambie.
"""

import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

LOCAL_PREFIX = "local:"
_SAFE_NAME = re.compile(r"^[A-Za-z0-9/_+=.@-]{1,512}$")


class SecretNotFoundError(Exception):
    pass


class SecretProvider(ABC):
    @abstractmethod
    def get_string(self, ref: str) -> str: ...

    @abstractmethod
    def put_json(self, name: str, value: dict[str, Any], description: str = "") -> str:
        """Crea o actualiza el secreto `name`. Devuelve su referencia (ARN)."""

    @abstractmethod
    def delete(self, ref: str) -> None: ...

    def get_json(self, ref: str) -> dict[str, Any]:
        data = json.loads(self.get_string(ref))
        if not isinstance(data, dict):
            raise ValueError("El secreto no contiene un objeto JSON")
        return data


class AwsSecretsManagerProvider(SecretProvider):
    def __init__(self, region: str | None = None) -> None:
        import boto3  # import tardío: en local no hace falta boto3 configurado

        self._client = boto3.client("secretsmanager", region_name=region)

    def get_string(self, ref: str) -> str:
        try:
            response = self._client.get_secret_value(SecretId=ref)
        except self._client.exceptions.ResourceNotFoundException as exc:
            raise SecretNotFoundError(ref) from exc
        return str(response["SecretString"])

    def put_json(self, name: str, value: dict[str, Any], description: str = "") -> str:
        payload = json.dumps(value)
        response: Any
        try:
            response = self._client.create_secret(
                Name=name,
                Description=description,
                SecretString=payload,
                Tags=[{"Key": "app", "Value": "multitenant-task-api"}],
            )
        except self._client.exceptions.ResourceExistsException:
            response = self._client.put_secret_value(SecretId=name, SecretString=payload)
        return str(response["ARN"])

    def delete(self, ref: str) -> None:
        self._client.delete_secret(SecretId=ref, ForceDeleteWithoutRecovery=True)


class LocalFileSecretProvider(SecretProvider):
    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)

    def _path(self, name: str) -> Path:
        if not _SAFE_NAME.fullmatch(name) or ".." in name:
            raise ValueError("Nombre de secreto inválido")
        return self._directory / (name.replace("/", "__") + ".json")

    @staticmethod
    def _name_from_ref(ref: str) -> str:
        if not ref.startswith(LOCAL_PREFIX):
            raise SecretNotFoundError(ref)
        return ref.removeprefix(LOCAL_PREFIX)

    def get_string(self, ref: str) -> str:
        path = self._path(self._name_from_ref(ref))
        if not path.exists():
            raise SecretNotFoundError(ref)
        return path.read_text(encoding="utf-8")

    def put_json(self, name: str, value: dict[str, Any], description: str = "") -> str:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._path(name)
        path.write_text(json.dumps(value), encoding="utf-8")
        os.chmod(path, 0o600)
        return f"{LOCAL_PREFIX}{name}"

    def delete(self, ref: str) -> None:
        self._path(self._name_from_ref(ref)).unlink(missing_ok=True)
