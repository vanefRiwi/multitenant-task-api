from sqlmodel import Session

from app.domain.ports.unit_of_work import UnitOfWork


class SqlModelUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:
        self._session = session

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
