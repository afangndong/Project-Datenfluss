"""Erzeugt FIKTIVE Demo-Daten (keine echten Personen). Aufruf: python -m app.seed [Anzahl]"""

import random
import sys
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from .db import Base, SessionLocal, engine
from .models import Appointment, Patient, Stay

VORNAMEN = [
    "Anna",
    "Ben",
    "Clara",
    "David",
    "Emma",
    "Felix",
    "Greta",
    "Hans",
    "Ida",
    "Jonas",
    "Klara",
    "Lukas",
    "Mia",
    "Noah",
    "Olga",
    "Paul",
    "Rita",
    "Sven",
    "Tina",
    "Uwe",
]
NACHNAMEN = [
    "Müller",
    "Schmidt",
    "Schneider",
    "Fischer",
    "Weber",
    "Meyer",
    "Wagner",
    "Becker",
    "Schulz",
    "Hoffmann",
    "Koch",
    "Richter",
    "Klein",
    "Wolf",
    "Neumann",
    "Braun",
]
STATIONEN = ["Innere A", "Innere B", "Chirurgie", "Orthopädie", "Reha", "Geriatrie"]
DIAGNOSEN = [
    "Kontrolle nach Eingriff",
    "Reha nach Hüft-TEP",
    "Herzinsuffizienz, Einstellung",
    "Pneumonie, Antibiose",
    "Diabetes mellitus, Neueinstellung",
    "Rückenschmerzen, Therapie",
]
ARTEN = ["Untersuchung", "Visite", "Therapie", "Entlassgespräch"]
VERSICHERUNG = ["gesetzlich", "gesetzlich", "gesetzlich", "privat"]


def seed(n: int = 25, seed_value: int = 42) -> int:
    rnd = random.Random(seed_value)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if (db.scalar(select(func.count(Patient.id))) or 0) > 0:
            return 0
        heute = date.today()
        for _ in range(n):
            p = Patient(
                vorname=rnd.choice(VORNAMEN),
                nachname=rnd.choice(NACHNAMEN),
                geburtsdatum=heute - timedelta(days=rnd.randint(18 * 365, 90 * 365)),
                geschlecht=rnd.choice(["weiblich", "männlich", "divers"]),
                versicherung=rnd.choice(VERSICHERUNG),
            )
            db.add(p)
            db.flush()
            p.fallnummer = f"F{p.id:06d}"
            aufnahme = heute - timedelta(days=rnd.randint(0, 20))
            aktiv = rnd.random() < 0.6
            db.add(
                Stay(
                    patient_id=p.id,
                    station=rnd.choice(STATIONEN),
                    zimmer=str(rnd.randint(101, 420)),
                    aufnahme=aufnahme,
                    entlassung=None if aktiv else aufnahme + timedelta(days=rnd.randint(1, 8)),
                    diagnose=rnd.choice(DIAGNOSEN),
                )
            )
            for _ in range(rnd.randint(0, 3)):
                tag = datetime.combine(heute, datetime.min.time()) + timedelta(
                    days=rnd.randint(-3, 7), hours=rnd.randint(8, 16), minutes=rnd.choice([0, 15, 30, 45])
                )
                db.add(
                    Appointment(
                        patient_id=p.id,
                        termin=tag,
                        art=rnd.choice(ARTEN),
                        status="erledigt" if tag < datetime.now() else "geplant",
                    )
                )
        db.commit()
    return n


if __name__ == "__main__":
    count = seed(int(sys.argv[1]) if len(sys.argv) > 1 else 25)
    print(f"{count} fiktive Patienten angelegt" if count else "Datenbank enthält bereits Daten – nichts getan")
