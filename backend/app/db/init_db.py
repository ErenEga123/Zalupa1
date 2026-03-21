from sqlalchemy.orm import Session

from app.db.session import Base, engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def health_query(db: Session) -> int:
    return db.execute("SELECT 1").scalar_one()
