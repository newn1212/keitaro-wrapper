import re
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .keitaro import Keitaro, KeitaroError
from .models import CampaignRecord, ChangeLog
from .shares import even_shares, validate_shares

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="Keitaro wrapper")
keitaro = Keitaro()


@app.exception_handler(KeitaroError)
def keitaro_error_handler(request, exc: KeitaroError):
    return JSONResponse(status_code=exc.status, content={"detail": str(exc)})


# ---------- схемы ----------------------------------------------------------
class CampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    geo: str = Field(min_length=2, max_length=100)
    offer_id: int


class AddOfferIn(BaseModel):
    offer_id: int


class SharesIn(BaseModel):
    shares: dict[int, int]


# ---------- вспомогательное ------------------------------------------------
def parse_geo(raw: str) -> list[str]:
    codes = [c.strip().upper() for c in raw.split(",") if c.strip()]
    if not codes or any(not re.fullmatch(r"[A-Z]{2}", c) for c in codes):
        raise HTTPException(400, "Гео — двухбуквенные коды стран через запятую, например AU или MX,RO")
    return list(dict.fromkeys(codes))


def stream_offers(stream: dict) -> list[dict]:
    return [o for o in stream.get("offers") or [] if o.get("state") != "deleted"]


def filters_text(stream: dict) -> str:
    parts = []
    for f in stream.get("filters") or []:
        if f.get("name") == "country":
            verb = "принимает" if f.get("mode") == "accept" else "исключает"
            parts.append(f"Страны {verb}: {', '.join(f.get('payload') or [])}")
        else:
            parts.append(f.get("name", ""))
    return "; ".join(parts)


def editable_stream(stream_id: int) -> dict:
    stream = keitaro.get_stream(stream_id)
    if stream.get("schema") != "landings":
        raise HTTPException(400, "В этом потоке нет офферов — это редирект на ссылку")
    return stream


def save_offers(stream_id: int, offers: list[dict]) -> None:
    keitaro.update_stream(stream_id, {"offers": offers})


# ---------- офферы ---------------------------------------------------------
@app.get("/api/offers")
def search_offers(q: str = ""):
    return [
        {"id": o["id"], "name": o.get("name"), "country": o.get("country") or []}
        for o in keitaro.search_offers(q)
    ]


# ---------- часть 1: создаватель кампаний ----------------------------------
@app.post("/api/campaigns", status_code=201)
def create_campaign(data: CampaignIn, db: Session = Depends(get_db)):
    name = data.name.strip()
    if settings.name_prefix and not name.startswith(settings.name_prefix):
        raise HTTPException(400, f"Название должно начинаться с «{settings.name_prefix}»")
    geos = parse_geo(data.geo)
    if db.scalar(select(CampaignRecord).where(CampaignRecord.name == name)):
        raise HTTPException(409, "Кампания с таким названием уже создана")
    if not keitaro.get_offer(data.offer_id):
        raise HTTPException(404, f"Оффер {data.offer_id} не найден в Keitaro")

    refs = keitaro.refs()
    campaign = keitaro.create_campaign({
        "name": name,
        "type": "position",
        "state": "active",
        "domain_id": refs["domain_id"],
        "group_id": refs["group_id"],
        "traffic_source_id": refs["traffic_source_id"],
    })
    cid = campaign["id"]

    try:
        # Поток 1: все из указанной страны уходят на Google
        keitaro.create_stream({
            "campaign_id": cid, "type": "regular", "name": "Flow 1", "position": 1, "weight": 100,
            "state": "active", "collect_clicks": True, "filter_or": False,
            "schema": "redirect", "action_type": "http", "action_payload": "https://google.com",
            "filters": [{"name": "country", "mode": "accept", "payload": geos}],
        })
        # Поток 2: остальные уходят на выбранный оффер
        keitaro.create_stream({
            "campaign_id": cid, "type": "regular", "name": "Flow 2", "position": 2, "weight": 100,
            "state": "active", "collect_clicks": True, "filter_or": False,
            "schema": "landings", "filters": [],
            "offers": [{"offer_id": data.offer_id, "share": 100, "state": "active"}],
        })
    except KeitaroError:
        # не оставляем в Keitaro «недоделанную» кампанию
        try:
            keitaro.delete_campaign(cid)
        except KeitaroError:
            pass
        raise

    alias = campaign.get("alias") or ""
    db.add(CampaignRecord(keitaro_id=cid, name=name, alias=alias, geo=",".join(geos), offer_id=data.offer_id))
    db.commit()
    return {
        "id": cid, "name": name, "alias": alias,
        "url": f"https://{refs['domain_name']}/{alias}",
        "admin_url": f"{settings.keitaro_url.rstrip('/')}/admin/#!/campaigns/{cid}",
    }


@app.get("/api/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    rows = db.scalars(select(CampaignRecord).order_by(CampaignRecord.id.desc()).limit(50)).all()
    return [{"id": r.keitaro_id, "name": r.name, "geo": r.geo} for r in rows]


# ---------- часть 2: редактор кампании -------------------------------------
@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: int):
    campaign = keitaro.get_campaign(campaign_id)
    names = {o["id"]: o.get("name") for o in keitaro.offers()}
    streams = []
    for s in sorted(keitaro.get_streams(campaign_id), key=lambda s: s.get("position") or 0):
        is_offers = s.get("schema") == "landings"
        streams.append({
            "id": s["id"], "name": s.get("name") or f"Поток {s['id']}", "filters": filters_text(s),
            "editable": is_offers,
            "redirect_url": None if is_offers else s.get("action_payload"),
            "offers": [
                {"offer_id": o["offer_id"], "name": names.get(o["offer_id"], f"Оффер {o['offer_id']}"),
                 "share": o.get("share", 0), "state": o.get("state")}
                for o in stream_offers(s)
            ] if is_offers else [],
        })
    return {"id": campaign["id"], "name": campaign.get("name"), "alias": campaign.get("alias"), "streams": streams}


@app.post("/api/streams/{stream_id}/offers")
def add_offer(stream_id: int, data: AddOfferIn, db: Session = Depends(get_db)):
    if not keitaro.get_offer(data.offer_id):
        raise HTTPException(404, f"Оффер {data.offer_id} не найден в Keitaro")
    stream = editable_stream(stream_id)
    current = stream_offers(stream)
    if any(o["offer_id"] == data.offer_id for o in current):
        raise HTTPException(409, "Этот оффер уже есть в потоке")

    ids = [o["offer_id"] for o in current] + [data.offer_id]
    new = [{"offer_id": i, "share": s, "state": "active"} for i, s in zip(ids, even_shares(len(ids)))]
    save_offers(stream_id, new)

    db.add(ChangeLog(campaign_id=stream.get("campaign_id"), stream_id=stream_id, action="add", offer_id=data.offer_id))
    db.commit()
    return {"ok": True}


@app.delete("/api/streams/{stream_id}/offers/{offer_id}")
def delete_offer(stream_id: int, offer_id: int, db: Session = Depends(get_db)):
    stream = editable_stream(stream_id)
    current = stream_offers(stream)
    if not any(o["offer_id"] == offer_id for o in current):
        raise HTTPException(404, "Такого оффера нет в потоке")
    if len(current) == 1:
        raise HTTPException(400, "Нельзя удалить последний оффер — поток останется пустым")

    ids = [o["offer_id"] for o in current if o["offer_id"] != offer_id]
    new = [{"offer_id": i, "share": s, "state": "active"} for i, s in zip(ids, even_shares(len(ids)))]
    save_offers(stream_id, new)

    db.add(ChangeLog(campaign_id=stream.get("campaign_id"), stream_id=stream_id, action="delete", offer_id=offer_id))
    db.commit()
    return {"ok": True}


@app.put("/api/streams/{stream_id}/shares")
def set_shares(stream_id: int, data: SharesIn, db: Session = Depends(get_db)):
    stream = editable_stream(stream_id)
    current = stream_offers(stream)
    try:
        validate_shares(data.shares, {o["offer_id"] for o in current})
    except ValueError as e:
        raise HTTPException(400, str(e))

    new = [{"offer_id": o["offer_id"], "share": data.shares[o["offer_id"]], "state": o.get("state") or "active"}
           for o in current]
    save_offers(stream_id, new)

    db.add(ChangeLog(campaign_id=stream.get("campaign_id"), stream_id=stream_id, action="shares", offer_id=None))
    db.commit()
    return {"ok": True}


# ---------- фронтенд -------------------------------------------------------
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")
