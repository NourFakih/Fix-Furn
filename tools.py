from datetime import datetime
from pathlib import Path
import csv
import json
import re
from typing import Dict, List

BASE = Path(__file__).parent
LOGS = BASE / "logs"
DATA = BASE / "data"
LOGS.mkdir(exist_ok=True)

CATALOG = json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))
PRICE_RULES = json.loads((DATA / "price_rules.json").read_text(encoding="utf-8"))
IKEA_CSV = DATA / "IKEA_SA_Furniture_Web_Scrapings_sss.csv"
SAR_TO_USD = 0.2667  # rough mid-market exchange rate


def _to_float(value: str):
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower().startswith("no "):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_bool(value: str):
    if value is None:
        return None
    value = value.strip().lower()
    if value in {"true", "yes", "y", "1"}:
        return True
    if value in {"false", "no", "n", "0"}:
        return False
    return None


def _load_ikea_catalog() -> List[Dict]:
    if not IKEA_CSV.exists():
        fallback = BASE / "IKEA_SA_Furniture_Web_Scrapings_sss.csv"
        if not fallback.exists():
            return []
        target = fallback
    else:
        target = IKEA_CSV

    items: List[Dict] = []
    with target.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            item_id = (row.get("item_id") or "").strip()
            name = (row.get("name") or "").strip()
            if not item_id or not name:
                continue
            category = (row.get("category") or "").strip()
            price_sar = _to_float(row.get("price"))
            price_usd = round(price_sar * SAR_TO_USD, 2) if price_sar is not None else None
            width = _to_float(row.get("width"))
            height = _to_float(row.get("height"))
            depth = _to_float(row.get("depth"))
            short_description = (row.get("short_description") or "").strip()
            if short_description:
                short_description = re.sub(r"\s+", " ", short_description)
            other_colors = (row.get("other_colors") or "").strip()
            if other_colors.lower() in {"no", "n/a"}:
                other_colors = ""
            sellable = _to_bool(row.get("sellable_online"))
            link = (row.get("link") or "").strip()
            designer = (row.get("designer") or "").strip()

            searchable = " ".join(
                filter(
                    None,
                    [
                        item_id.lower(),
                        name.lower(),
                        category.lower(),
                        short_description.lower(),
                        other_colors.lower(),
                        designer.lower(),
                    ],
                )
            )

            items.append(
                {
                    "item_id": item_id,
                    "name": name,
                    "category": category,
                    "price_usd": price_usd,
                    "price_currency": "USD" if price_usd is not None else None,
                    "price_note": (
                        f"Converted from SAR at 1 SAR = {SAR_TO_USD:.4f} USD"
                        if price_usd is not None
                        else None
                    ),
                    "sellable_online": sellable,
                    "link": link,
                    "other_colors": other_colors,
                    "short_description": short_description,
                    "designer": designer,
                    "dimensions_cm": {
                        k: v
                        for k, v in {"width": width, "height": height, "depth": depth}.items()
                        if v is not None
                    },
                    "_search": searchable,
                }
            )
    return items


IKEA_ITEMS = _load_ikea_catalog()


def _copy_public_item(item: Dict) -> Dict:
    return {k: v for k, v in item.items() if not k.startswith("_")}


def _search_ikea_items(query: str, limit: int = 5) -> List[Dict]:
    if not IKEA_ITEMS:
        return []
    q = query.strip().lower()
    if not q:
        return []
    words = [w for w in re.split(r"\W+", q) if w]
    scored: Dict[str, List] = {}
    for item in IKEA_ITEMS:
        score = 0
        if q == item["item_id"].lower():
            score += 10
        if q in item["_search"]:
            score += 3
        if words:
            score += sum(1 for w in words if w and w in item["_search"])
        if score > 0:
            existing = scored.get(item["item_id"])
            if existing is None or score > existing[0]:
                scored[item["item_id"]] = [score, item]
    if not scored:
        return []
    top = sorted(scored.values(), key=lambda pair: (-pair[0], pair[1]["name"]))
    return [_copy_public_item(item) for _, item in top[:limit]]


def record_customer_interest(email: str, name: str, message: str):
    entry = {"ts": datetime.utcnow().isoformat(), "email": email, "name": name, "message": message}
    out = LOGS / "leads.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    print(f"[LEAD] {entry}")
    return {"ok": True, "msg": "Thanks! We'll follow up soon."}


def record_feedback(question: str):
    entry = {"ts": datetime.utcnow().isoformat(), "question": question}
    out = LOGS / "feedback.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    print(f"[FEEDBACK] {entry}")
    return {"ok": True, "msg": "Noted. We'll improve our answers."}


def record_service_feedback(
    email: str,
    name: str,
    service_type: str,
    satisfaction: str,
    comments: str = "",
):
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "email": email,
        "name": name,
        "service_type": service_type,
        "satisfaction": satisfaction,
        "comments": comments or "",
    }
    out = LOGS / "service_feedback.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    print(f"[SERVICE_FEEDBACK] {entry}")
    return {"ok": True, "msg": "Thanks for the feedback! We'll share it with the team."}


def lookup_product(query: str):
    q = (query or "").strip()
    if not q:
        return {"ok": False, "msg": "Please provide a product keyword, SKU, or IKEA item ID."}
    q_lower = q.lower()
    result = {"ok": True, "query": q}

    sku_match = next((item for item in CATALOG if item.get("sku", "").lower() == q_lower), None)
    if sku_match:
        result["catalog_match"] = sku_match

    name_hits = [
        item
        for item in CATALOG
        if q_lower in item.get("name", "").lower()
        or any(q_lower in (opt or "").lower() for opt in item.get("color_options", []))
    ]
    if name_hits and not sku_match:
        result["catalog_results"] = name_hits

    category_hits = [item for item in CATALOG if item.get("category", "").lower() == q_lower]
    if category_hits:
        result["catalog_category"] = category_hits

    ikea_hits = _search_ikea_items(q_lower)
    if ikea_hits:
        result["ikea_results"] = ikea_hits

    if len(result) == 2:
        return {"ok": False, "msg": f"No products found for '{q}'."}
    return result


def estimate_repair(issue: str, material: str = "any", size_category: str = "medium"):
    issue = issue.strip().lower()
    material = (material or "any").strip().lower()
    size = (size_category or "medium").strip().lower()
    rules = PRICE_RULES.get(issue)
    if not rules:
        return {"ok": False, "msg": f"No pricing rule for issue '{issue}'."}
    if material in rules:
        bucket = rules[material]
    elif "any" in rules:
        bucket = rules["any"]
    else:
        bucket = next(iter(rules.values()))
    if size not in bucket:
        return {"ok": False, "msg": f"Unsupported size_category '{size}'. Use small/medium/large."}
    min_p, max_p, min_d, max_d = bucket[size]
    tiers = {
        "budget": {"price": round(min_p * 0.9), "days": [min_d, max(min_d, min_d + 1)]},
        "standard": {"price": round((min_p + max_p) / 2), "days": [min_d, max_d]},
        "rush": {"price": round(max_p * 1.25), "days": [max(1, min_d - 1), max(1, max_d - 1)]},
    }
    return {"ok": True, "issue": issue, "material": material, "size": size, "estimate": tiers}
