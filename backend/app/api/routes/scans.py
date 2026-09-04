import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps import auth_dependency
from app.core.database import get_db
from app.core.logging import get_logger
from app.models.entities import Finding, Report, Target, TestResult, TestRun
from app.schemas.schemas import FindingOut, RerunRequest, ScanCreate, ScanOut, TestResultOut
from app.services.reporting import build_finding_dict, build_report_data, build_summary_dict
from app.services.scanner import run_scan

logger = get_logger("api.scans")

router = APIRouter(tags=["scans"])

SCAN_TASKS: dict[int, asyncio.Task] = {}


async def _execute_scan(scan_id: int) -> None:
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    SCAN_TASKS[scan_id] = task

    def progress_cb(_scan_id, done, total):
        pass  # progress is read from results count; kept for future SSE

    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        scan = db.get(TestRun, scan_id)
        if not scan:
            logger.error("scan task started for missing scan", scan_id=scan_id)
            return
        target = db.get(Target, scan.target_id)
        await run_scan(db, scan, target, scan.config or {}, progress_callback=progress_cb)
        logger.info("scan completed", scan_id=scan_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("scan failed", scan_id=scan_id, error=str(exc))
        db.rollback()
        scan = db.get(TestRun, scan_id)
        if scan:
            scan.status = "failed"
            scan.summary = {"error": str(exc)}
            scan.ended_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        SCAN_TASKS.pop(scan_id, None)
        db.close()


def _counts_for_scan(db: Session, scan_id: int) -> dict:
    rows = db.query(TestResult).filter_by(test_run_id=scan_id).all()
    counts = {
        "total": len(rows),
        "success": sum(1 for r in rows if r.classification == "success"),
        "partial": sum(1 for r in rows if r.classification == "partial"),
        "blocked": sum(1 for r in rows if r.classification == "blocked"),
        "uncertain": sum(1 for r in rows if r.classification == "uncertain"),
        "error": sum(1 for r in rows if r.classification == "error"),
    }
    return counts


@router.post("/scans", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
async def create_scan(
    data: ScanCreate,
    db: Session = Depends(get_db),
    _=Depends(auth_dependency),
):
    target = db.get(Target, data.target_id)
    if not target:
        raise HTTPException(status_code=404, detail="target not found")

    scan = TestRun(
        target_id=target.id,
        name=data.name,
        config=data.config.model_dump(exclude_none=True),
        status="pending",
        summary={"total": 0},
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    asyncio.create_task(_execute_scan(scan.id))
    return scan


@router.get("/scans", response_model=list[ScanOut])
def list_scans(db: Session = Depends(get_db), _=Depends(auth_dependency)):
    scans = db.query(TestRun).order_by(TestRun.id.desc()).limit(200).all()
    out = []
    for s in scans:
        item = ScanOut.model_validate(s)
        if s.status == "running":
            item.summary = _counts_for_scan(db, s.id)
        out.append(item)
    return out


@router.get("/scans/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: int, db: Session = Depends(get_db), _=Depends(auth_dependency)):
    scan = db.get(TestRun, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="scan not found")
    item = ScanOut.model_validate(scan)
    if scan.status == "running":
        item.summary = _counts_for_scan(db, scan_id)
    return item


@router.get("/scans/{scan_id}/results", response_model=list[TestResultOut])
def get_results(scan_id: int, db: Session = Depends(get_db), _=Depends(auth_dependency)):
    scan = db.get(TestRun, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="scan not found")
    rows = (
        db.query(TestResult)
        .filter_by(test_run_id=scan_id)
        .options(selectinload(TestResult.attack))
        .order_by(TestResult.id)
        .all()
    )
    out = []
    for r in rows:
        item = TestResultOut(
            id=r.id,
            test_run_id=r.test_run_id,
            attack_id=r.attack_id,
            payload=r.payload,
            response=r.response,
            http_status=r.http_status,
            latency_ms=r.latency_ms,
            error=r.error,
            classification=r.classification,
            confidence=r.confidence,
            severity=r.severity,
            evidence=r.evidence or {},
            layer_results=r.layer_results or {},
            attack_meta={
                "id": r.attack.attack_id if r.attack else None,
                "category": r.attack.category if r.attack else None,
                "objective": r.attack.objective if r.attack else None,
                "mutation_strategy": r.variant.mutation_strategy if r.variant else None,
            },
        )
        out.append(item)
    return out


@router.get("/scans/{scan_id}/findings", response_model=list[FindingOut])
def get_findings(scan_id: int, db: Session = Depends(get_db), _=Depends(auth_dependency)):
    scan = db.get(TestRun, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="scan not found")
    rows = db.query(Finding).filter_by(test_run_id=scan_id).all()
    return rows


@router.post("/scans/{scan_id}/rerun", response_model=ScanOut, status_code=status.HTTP_201_CREATED)
async def rerun_scan(
    scan_id: int,
    data: RerunRequest | None = None,
    db: Session = Depends(get_db),
    _=Depends(auth_dependency),
):
    original = db.get(TestRun, scan_id)
    if not original:
        raise HTTPException(status_code=404, detail="scan not found")
    config = data.config.model_dump(exclude_none=True) if data and data.config else original.config
    scan = TestRun(
        target_id=original.target_id,
        name=f"{original.name or f'Scan #{original.id}'} (rerun)",
        config=config,
        status="pending",
        summary={"total": 0},
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    asyncio.create_task(_execute_scan(scan.id))
    return scan


@router.delete("/scans/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_scan(scan_id: int, db: Session = Depends(get_db), _=Depends(auth_dependency)):
    scan = db.get(TestRun, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="scan not found")
    task = SCAN_TASKS.get(scan_id)
    if task and not task.done():
        task.cancel()
    if scan.status == "running":
        scan.status = "cancelled"
        scan.ended_at = datetime.now(timezone.utc)
        db.commit()
    return None