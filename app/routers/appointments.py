from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Appointment, Patient
from ..schemas import AppointmentIn, AppointmentOut, TerminStatus
from ..security import require_write_access

router = APIRouter(prefix="/api/appointments", tags=["Termine"])


def _out(a: Appointment) -> AppointmentOut:
    out = AppointmentOut.model_validate(a)
    out.patient_name = f"{a.patient.nachname}, {a.patient.vorname}" if a.patient else None
    return out


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    patient_id: int | None = None,
    status: TerminStatus | None = None,
    ab: datetime | None = Query(None, description="Termine ab (ISO-8601)"),
    db: Session = Depends(get_db),
):
    stmt = select(Appointment)
    if patient_id:
        stmt = stmt.where(Appointment.patient_id == patient_id)
    if status:
        stmt = stmt.where(Appointment.status == status)
    if ab:
        stmt = stmt.where(Appointment.termin >= ab)
    return [_out(a) for a in db.scalars(stmt.order_by(Appointment.termin).limit(500)).all()]


@router.post("", response_model=AppointmentOut, status_code=201, dependencies=[Depends(require_write_access)])
def create_appointment(data: AppointmentIn, db: Session = Depends(get_db)):
    if not db.get(Patient, data.patient_id):
        raise HTTPException(404, "Patient nicht gefunden")
    appt = Appointment(**data.model_dump())
    db.add(appt)
    db.commit()
    return _out(appt)


@router.patch("/{appt_id}/status", response_model=AppointmentOut, dependencies=[Depends(require_write_access)])
def set_status(appt_id: int, status: TerminStatus, db: Session = Depends(get_db)):
    appt = db.get(Appointment, appt_id)
    if not appt:
        raise HTTPException(404, "Termin nicht gefunden")
    appt.status = status
    db.commit()
    return _out(appt)


@router.delete("/{appt_id}", status_code=204, dependencies=[Depends(require_write_access)])
def delete_appointment(appt_id: int, db: Session = Depends(get_db)):
    appt = db.get(Appointment, appt_id)
    if not appt:
        raise HTTPException(404, "Termin nicht gefunden")
    db.delete(appt)
    db.commit()
    return Response(status_code=204)
