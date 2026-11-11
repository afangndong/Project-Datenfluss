from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Patient
from ..schemas import PatientIn, PatientOut
from ..security import require_write_access

router = APIRouter(prefix="/api/patients", tags=["Patienten"])


def _get(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient nicht gefunden")
    return patient


@router.get("", response_model=list[PatientOut])
def list_patients(
    response: Response,
    q: str | None = Query(None, description="Suche in Name oder Fallnummer"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Patient)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(Patient.nachname.ilike(like), Patient.vorname.ilike(like), Patient.fallnummer.ilike(like))
        )
    total = len(db.scalars(stmt).all())
    response.headers["X-Total-Count"] = str(total)
    return db.scalars(stmt.order_by(Patient.nachname, Patient.vorname).limit(limit).offset(offset)).all()


@router.post("", response_model=PatientOut, status_code=201, dependencies=[Depends(require_write_access)])
def create_patient(data: PatientIn, db: Session = Depends(get_db)):
    patient = Patient(**data.model_dump())
    db.add(patient)
    db.flush()
    patient.fallnummer = f"F{patient.id:06d}"
    db.commit()
    return patient


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: int, db: Session = Depends(get_db)):
    return _get(db, patient_id)


@router.put("/{patient_id}", response_model=PatientOut, dependencies=[Depends(require_write_access)])
def update_patient(patient_id: int, data: PatientIn, db: Session = Depends(get_db)):
    patient = _get(db, patient_id)
    for key, value in data.model_dump().items():
        setattr(patient, key, value)
    db.commit()
    return patient


@router.delete("/{patient_id}", status_code=204, dependencies=[Depends(require_write_access)])
def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    db.delete(_get(db, patient_id))
    db.commit()
    return Response(status_code=204)
