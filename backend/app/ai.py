"""Penyusun itinerary. LLM hanya memilih destinasi & urutan; HARGA tidak pernah berasal dari LLM."""
import json
from .config import settings

TIMES = ["09:00", "13:00", "16:00"]


def _fallback(dests: list[dict], n_days: int) -> list[dict]:
    days, i = [], 0
    for d in range(1, n_days + 1):
        items = []
        for t in TIMES:
            items.append({"destination_id": dests[i % len(dests)]["id"], "time": t, "note": ""})
            i += 1
        days.append({"day": d, "items": items})
    return days


def _clean(raw: dict, valid_ids: set[int], n_days: int) -> list[dict]:
    days, seen = [], set()
    for d in raw.get("days", [])[:n_days]:
        items = []
        for it in d.get("items", [])[:4]:
            did = it.get("destination_id")
            if did in valid_ids and did not in seen:
                seen.add(did)
                items.append({"destination_id": did, "time": str(it.get("time", "09:00")), "note": str(it.get("note", ""))[:200]})
        if items:
            days.append({"day": len(days) + 1, "items": items})
    if not days:
        raise ValueError("Keluaran AI tidak valid")
    return days


def generate_days(dests: list[dict], n_days: int, travelers: int, budget: int, interests: list[str]):
    """Return (days, ai_used)."""
    if settings.openai_api_key and settings.openai_model:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key, timeout=30)
            catalog = [{"id": d["id"], "name": d["name"], "category": d["category"], "ticket_idr": d["price_estimate"]} for d in dests]
            system = ("Kamu perencana perjalanan wisata di Indonesia. Susun itinerari harian dari daftar destinasi yang diberikan. "
                      "Gunakan HANYA destinasi_id dari daftar, maksimal 3 destinasi per hari, jangan mengulang destinasi, "
                      "urutkan agar searah, sesuaikan dengan minat. Jangan menulis harga. "
                      'Balas JSON: {"days":[{"day":1,"items":[{"destination_id":1,"time":"09:00","note":"alasan singkat"}]}]}')
            user = json.dumps({"jumlah_hari": n_days, "peserta": travelers, "anggaran_idr": budget,
                               "minat": interests, "destinasi": catalog}, ensure_ascii=False)
            res = client.chat.completions.create(
                model=settings.openai_model, response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            return _clean(json.loads(res.choices[0].message.content), {d["id"] for d in dests}, n_days), True
        except Exception:
            pass  # jatuh ke fallback agar sistem tetap bisa dipakai (NFR-11)
    return _fallback(dests, n_days), False
