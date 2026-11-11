"""Pydantic-Schemas (Ein-/Ausgabe der API)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Geschlecht = Literal["weiblich", "männlich", "divers"]
TerminArt = Literal["Untersuchung", "Visite", "Therapie", "Entlassgespräch", "Sonstiges"]
TerminStatus = Literal["geplant", "erledigt", "abgesagt"]


class PatientIn(BaseModel):
    vorname: str = Field(min_length=1, max_length=80)
    nachname: str = Field(min_length=1, max_length=80)
    geburtsdatum: date
    geschlecht: Geschlecht = "divers"
    versicherung: str = Field(default="gesetzlich", max_length=80)

    @model_validator(mode="after")
    def _not_future(self):
        if self.geburtsdatum > date.today():
            raise ValueError("Geburtsdatum darf nicht in der Zukunft liegen")
        return self


class PatientOut(PatientIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fallnummer: str | None
    created_at: datetime | None = None


class StayIn(BaseModel):
    patient_id: int
    station: str = Field(min_length=1, max_length=40)
    zimmer: str = Field(min_length=1, max_length=10)
    aufnahme: date
    entlassung: date | None = None
    diagnose: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _order(self):
        if self.entlassung and self.entlassung < self.aufnahme:
            raise ValueError("Entlassung darf nicht vor der Aufnahme liegen")
        return self


class StayOut(StayIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class AppointmentIn(BaseModel):
    patient_id: int
    termin: datetime
    art: TerminArt = "Untersuchung"
    status: TerminStatus = "geplant"
    bemerkung: str | None = Field(default=None, max_length=2000)


class AppointmentOut(AppointmentIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    patient_name: str | None = None


class Stats(BaseModel):
    patienten: int
    aktuelle_aufenthalte: int
    termine_heute: int
    termine_offen: int
    belegung_je_station: dict[str, int]
    termine_nach_status: dict[str, int]
