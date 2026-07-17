from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app import crud, schemas
from app import database

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[schemas.JobRead])
def list_jobs(
    status: str | None = Query(None),
    target_type: str | None = Query(None),
    target_id: int | None = Query(None),
    session: Session = Depends(database.session_dependency),
):
    return crud.list_jobs(
        session,
        status=status,
        target_type=target_type,
        target_id=target_id,
    )


@router.get("/{job_id}", response_model=schemas.JobRead)
def get_job(job_id: int, session: Session = Depends(database.session_dependency)):
    job = crud.get_job(session, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job 不存在")
    return job
