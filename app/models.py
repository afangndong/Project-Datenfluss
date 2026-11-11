"""Datenmodell: Patient 1–n Aufenthalt, Patient 1–n Termin."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    fallnummer: Mapped[str | None] = mapped_column(String(16), unique=True, index=True)
    vorname: Mapped[str] = mapped_column(String(80))
    nachname: Mapped[str] = mapped_column(String(80), index=True)
    geburtsdatum: Mapped[date] = mapped_column(Date)
    geschlecht: Mapped[str] = mapped_column(String(10), default="divers")
    versicherung: Mapped[str] = mapped_column(String(80), default="gesetzlich")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    stays: Mapped[list["Stay"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class Stay(Base):
    """Stationärer Aufenthalt. entlassung = NULL bedeutet: aktuell auf Station."""

    __tablename__ = "stays"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    station: Mapped[str] = mapped_column(String(40))
    zimmer: Mapped[str] = mapped_column(String(10))
    aufnahme: Mapped[date] = mapped_column(Date)
    entlassung: Mapped[date | None] = mapped_column(Date, nullable=True)
    diagnose: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped[Patient] = relationship(back_populates="stays")


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), index=True)
    termin: Mapped[datetime] = mapped_column(DateTime, index=True)
    art: Mapped[str] = mapped_column(String(40), default="Untersuchung")
    status: Mapped[str] = mapped_column(String(20), default="geplant")
    bemerkung: Mapped[str | None] = mapped_column(Text, nullable=True)

    patient: Mapped[Patient] = relationship(back_populates="appointments")
