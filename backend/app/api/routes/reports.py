from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session, selectinload

from app.api.deps import auth_dependency
from app.core.database import get_db
from app.models.entities import Finding, Report, Target, TestResult, TestRun
from app.services.reporting import build_report_data, to_html, to_json

router = APIRouter(prefix="/reports", tags=["reports"])


def _collect(scan_id: int, db: Session):
    scan = db.get(TestRun, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="scan not found")
    target = db.get(Target, scan.target_id)
    results = (
        db.query(TestResult)
        .filter_by(test_run_id=scan_id)
        .options(selectinload(TestResult.attack))
        .all()
    )
    findings = db.query(Finding).filter_by(test_run_id=scan_id).all()
    if not target:
        raise HTTPException(status_code=404, detail="scan target missing")
    return scan, target, results, findings


@router.get("/{scan_id}/json")
async def get_json_report(scan_id: int, db: Session = Depends(get_db), _=Depends(auth_dependency)):
    scan, target, results, findings = _collect(scan_id, db)
    data = build_report_data(scan, target, results, findings)
    return JSONResponse(content=data)


@router.post("/{scan_id}/json", status_code=201)
async def store_json_report(scan_id: int, db: Session = Depends(get_db), _=Depends(auth_dependency)):
    scan, target, results, findings = _collect(scan_id, db)
    data = build_report_data(scan, target, results, findings)
    report = Report(test_run_id=scan_id, summary=data["summary"], breakdown=data["breakdown"], findings=data["findings"], format="json")
    db.add(report)
    db.commit()
    return to_json(data)


@router.get("/{scan_id}/html", response_class=HTMLResponse)
async def get_html_report(scan_id: int, db: Session = Depends(get_db), _=Depends(auth_dependency)):
    scan, target, results, findings = _collect(scan_id, db)
    data = build_report_data(scan, target, results, findings)
    return HTMLResponse(to_html(data))