from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import auth_dependency
from app.attacks.library import ATTACK_LIBRARY, CATEGORY_LABELS, DEFAULT_CATEGORIES
from app.core.database import get_db
from app.models.entities import Attack

router = APIRouter(prefix="/attacks", tags=["attacks"])


@router.get("/catalog")
async def get_catalog(_=Depends(auth_dependency)):
    return {
        "categories": CATEGORY_LABELS,
        "default_categories": DEFAULT_CATEGORIES,
        "attacks": ATTACK_LIBRARY,
    }


@router.get("")
async def list_stored_attacks(db: Session = Depends(get_db), _=Depends(auth_dependency)):
    rows = db.query(Attack).limit(500).all()
    return [
        {
            "id": a.id,
            "attack_id": a.attack_id,
            "category": a.category,
            "objective": a.objective,
            "severity": a.severity,
            "template": a.template,
            "tags": a.tags,
        }
        for a in rows
    ]