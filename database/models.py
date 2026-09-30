from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer

class Base(DeclarativeBase):
    pass

class Usuario(Base):
    __tablename__ = 'usuarios'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[str] = mapped_column(String(50), unique=True)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    pepitas: Mapped[int] = mapped_column(Integer, default=0)