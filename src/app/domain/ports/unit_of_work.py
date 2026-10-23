from abc import ABC, abstractmethod


class UnitOfWork(ABC):
    """Permite a un caso de uso confirmar cambios a mitad de un flujo largo
    (p. ej. guardar el tenant en 'provisioning' ANTES de crear su base de datos)."""

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...
