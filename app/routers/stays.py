from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Patient, Stay
from ..schemas import StayIn, StayOut
from ..security import require_write_access

router = APIRouter(prefix="/api/stays", tags=["Aufenthalte"])


@router.get("", response_model=list[StayOut])
def list_stays(
    patient_id: int | None = None,
    nur_aktuell: bool = Query(False, description="Nur Aufenthalte ohne Entlassung"),
    db: Session = Depends(get_db),
):
    stmt = select(Stay)
    if patient_id:
        stmt = stmt.where(Stay.patient_id == patient_id)
    if nur_aktuell:
        stmt = stmt.where(Stay.entlassung.is_(None))
    return db.scalars(stmt.order_by(Stay.aufnahme.desc())).all()


@router.post("", response_model=StayOut, status_code=201, dependencies=[Depends(require_write_access)])
def create_stay(data: StayIn, db: Session = Depends(get_db)):
    if not db.get(Patient, data.patient_id):
        raise HTTPException(404, "Patient nicht gefunden")
    stay = Stay(**data.model_dump())
    db.add(stay)
    db.commit()
    return stay


@router.post("/{stay_id}/entlassen", response_model=StayOut, dependencies=[Depends(require_write_access)])
def discharge(stay_id: int, db: Session = Depends(get_db)):
    stay = db.get(Stay, stay_id)
    if not stay:
        raise HTTPException(404, "Aufenthalt nicht gefunden")
    if stay.entlassung:
        raise HTTPException(409, "Patient ist bereits entlassen")
    stay.entlassung = max(date.today(), stay.aufnahme)
    db.commit()
    return stay


@router.delete("/{stay_id}", status_code=204, dependencies=[Depends(require_write_access)])
def delete_stay(stay_id: int, db: Session = Depends(get_db)):
    stay = db.get(Stay, stay_id)
    if not stay:
        raise HTTPException(404, "Aufenthalt nicht gefunden")
    db.delete(stay)
    db.commit()
    return Response(status_code=204)
