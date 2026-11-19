import time

import httpx

from .config import settings


class KeitaroError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def _norm_domain(value: str) -> str:
    return value.replace("https://", "").replace("http://", "").strip("/ ").lower()


class Keitaro:
    """Тонкая обёртка над Keitaro Admin API (https://<хост>/admin_api/v1)."""

    def __init__(self):
        self.client = httpx.Client(
            base_url=settings.keitaro_url.rstrip("/") + "/admin_api/v1",
            headers={"Api-Key": settings.keitaro_api_key},
            timeout=30,
        )
        self._offers: tuple[float, list[dict]] = (0, [])
        self._refs: dict | None = None

    # ---- низкий уровень -------------------------------------------------
    def _req(self, method: str, path: str, **kw):
        if not settings.keitaro_api_key:
            raise KeitaroError("Не задан KEITARO_API_KEY в файле .env", 500)
        try:
            r = self.client.request(method, path, **kw)
        except httpx.HTTPError as e:
            raise KeitaroError(f"Нет связи с Keitaro: {e}")
        if r.status_code >= 400:
            raise KeitaroError(f"Keitaro ответил {r.status_code}: {r.text[:300]}")
        try:
            return r.json()
        except ValueError:
            return None

    # ---- справочники ----------------------------------------------------
    def offers(self) -> list[dict]:
        ts, data = self._offers
        if time.time() - ts > 60:
            data = self._req("GET", "/offers") or []
            self._offers = (time.time(), data)
        return data

    def search_offers(self, q: str, limit: int = 20) -> list[dict]:
        q = q.strip().lower()
        res = [
            o for o in self.offers()
            if o.get("state") != "deleted" and (q in str(o.get("id")) or q in (o.get("name") or "").lower())
        ]
        return res[:limit]

    def get_offer(self, offer_id: int) -> dict | None:
        return next((o for o in self.offers() if o.get("id") == offer_id), None)

    def refs(self) -> dict:
        """ID домена, группы и источника из .env (ищем по имени). Кэшируем."""
        if self._refs:
            return self._refs
        domains = self._req("GET", "/domains") or []
        groups = self._req("GET", "/groups") or []
        sources = self._req("GET", "/traffic_sources") or []

        dom = next((d for d in domains if _norm_domain(d.get("name", "")) == _norm_domain(settings.domain_name)), None)
        grp = next((g for g in groups if g.get("name", "").lower() == settings.group_name.lower()
                    and g.get("type", "campaigns") == "campaigns"), None)
        src = next((s for s in sources if s.get("name", "").lower() == settings.source_name.lower()), None)

        for obj, label, name in ((dom, "Домен", settings.domain_name), (grp, "Группа", settings.group_name),
                                 (src, "Источник", settings.source_name)):
            if not obj:
                raise KeitaroError(f"{label} «{name}» не найден(а) в Keitaro. Проверьте .env", 400)
        self._refs = {"domain_id": dom["id"], "group_id": grp["id"], "traffic_source_id": src["id"],
                      "domain_name": _norm_domain(dom["name"])}
        return self._refs

    # ---- кампании и потоки ----------------------------------------------
    def create_campaign(self, payload: dict) -> dict:
        return self._req("POST", "/campaigns", json=payload)

    def delete_campaign(self, campaign_id: int) -> None:
        self._req("DELETE", f"/campaigns/{campaign_id}")

    def get_campaign(self, campaign_id: int) -> dict:
        return self._req("GET", f"/campaigns/{campaign_id}")

    def get_streams(self, campaign_id: int) -> list[dict]:
        return self._req("GET", f"/campaigns/{campaign_id}/streams") or []

    def create_stream(self, payload: dict) -> dict:
        return self._req("POST", "/streams", json=payload)

    def get_stream(self, stream_id: int) -> dict:
        return self._req("GET", f"/streams/{stream_id}")

    def update_stream(self, stream_id: int, payload: dict) -> dict:
        return self._req("PUT", f"/streams/{stream_id}", json=payload)
