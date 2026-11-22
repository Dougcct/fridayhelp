"""Servidor local para o Black Friday Tracker.

Serve os arquivos estáticos da pasta do projeto e expõe /api/deals
para ler e persistir alterações diretamente em data/deals.json.
"""

from __future__ import annotations

import concurrent.futures
import html as html_lib
import http.cookies
import json
import os
import re
import signal
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "deals.json"
DEFAULT_PORT = 8080

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "").strip()
SUPABASE_ENABLED = bool(SUPABASE_URL and SUPABASE_ANON_KEY)

SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

STOP_WORDS = {"de", "da", "do", "das", "dos", "e", "em", "com", "para", "por", "a", "o", "na", "no"}
ACCESSORY_WORDS = (
    "case", "gaveta", "adaptador", "capa", "capinha", "pelicula",
    "suporte", "cabo", "filtro de privacidade",
)
COMPONENT_TOKENS = {
    "ssd", "hd", "nvme", "m2", "ram", "ddr4", "ddr5", "memoria", "processador",
    "cpu", "gpu", "rtx", "gtx", "rx", "placa", "fonte", "cooler", "watercooler",
    "gabinete", "monitor", "teclado", "mouse", "headset", "webcam",
}
SYSTEM_WORDS = (
    "computador", "pc gamer", "pc home", "pc completo", "desktop",
    "notebook", "laptop", "all in one", "workstation", "servidor", "kit upgrade",
)
TRUSTED_KABUM_SELLERS = {"kabum!", "terabyte", "pichau"}

CATEGORY_HINTS: dict[str, dict[str, tuple[str, ...]]] = {
    "hardware": {
        "context": ("ssd", "nvme", "sata", "hd", "ram", "ddr4", "ddr5", "placa", "processador", "ryzen", "intel", "fonte", "gabinete", "cooler", "water"),
        "search_hint": "",
    },
    "perifericos": {
        "context": ("teclado", "mouse", "headset", "monitor", "webcam", "microfone", "mousepad", "controle"),
        "search_hint": "",
    },
    "notebooks pcs": {
        "context": ("notebook", "laptop", "pc", "computador", "desktop", "chromebook", "macbook"),
        "search_hint": "",
    },
    "celulares tablets": {
        "context": ("smartphone", "celular", "iphone", "galaxy", "redmi", "poco", "tablet", "ipad"),
        "search_hint": "",
    },
    "tv video": {
        "context": ("smart tv", "tv", "qled", "oled", "4k", "projetor", "chromecast", "fire tv"),
        "search_hint": "",
    },
    "audio som": {
        "context": ("fone", "headphone", "earbud", "caixa", "soundbar", "bluetooth", "speaker", "jbl", "microfone"),
        "search_hint": "",
    },
    "som automotivo": {
        "context": ("automotivo", "trio", "subwoofer", "woofer", "modulo", "taramps", "stetsom", "falcon", "driver", "tweeter", "corneta", "alto falante"),
        "exclude": ("portatil", "karaoke", "bluetooth"),
        "search_hint": "automotivo",
    },
    "games": {
        "context": ("ps5", "playstation", "xbox", "nintendo", "switch", "console", "controle", "jogo"),
        "search_hint": "",
    },
    "casa eletrodomesticos": {
        "context": ("air fryer", "geladeira", "fogao", "microondas", "aspirador", "cafeteira", "ventilador", "ar condicionado", "lavadora"),
        "search_hint": "",
    },
    "ferramentas": {
        "context": ("furadeira", "parafusadeira", "serra", "esmerilhadeira", "kit ferramentas", "chave", "makita", "bosch", "dewalt"),
        "search_hint": "",
    },
    "automotivo": {
        "context": ("automotivo", "carro", "pneu", "bateria", "oleo", "multimidia", "camera de re", "alarme"),
        "search_hint": "automotivo",
    },
    "moda beleza": {
        "context": ("tenis", "camiseta", "jaqueta", "calcado", "perfume", "maquiagem", "hidratante", "shampoo", "relogio", "bolsa", "oculos"),
        "search_hint": "",
    },
    "esporte lazer": {
        "context": ("bicicleta", "bike", "halter", "esteira", "academia", "suplemento", "whey", "bola", "corrida"),
        "search_hint": "",
    },
}


def _normalize_text(text: str) -> str:
    """Remove accents, punctuation, and split joined word+number tokens (e.g. ssd240gb -> ssd 240gb)."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_only = "".join(ch for ch in nfkd if not unicodedata.combining(ch))
    spaced = re.sub(r"([a-z])(\d)", r"\1 \2", ascii_only)
    return re.sub(r"[^a-z0-9]+", " ", spaced).strip()


def _query_tokens(query: str) -> list[str]:
    return [t for t in _normalize_text(query).split() if len(t) >= 2 and t not in STOP_WORDS]


def _category_config(category: str) -> dict[str, tuple[str, ...]]:
    norm_cat = _normalize_text(category)
    return CATEGORY_HINTS.get(norm_cat, {"context": (), "search_hint": ""})


def _score_match(title: str, query: str, category: str = "") -> int:
    """Return relevance score (>0 if acceptable, 0 if rejected) using query + category context."""
    norm_title = _normalize_text(title)
    norm_query = _normalize_text(query)
    if not norm_title or not norm_query:
        return 0

    for acc in ACCESSORY_WORDS:
        if acc in norm_title and acc not in norm_query:
            return 0

    tokens = _query_tokens(query)
    if not tokens:
        return 1

    # When searching for a standalone hardware/peripheral component, reject whole PCs/notebooks
    if any(t in COMPONENT_TOKENS for t in tokens) and not any(sw in norm_query for sw in SYSTEM_WORDS):
        if any(sw in norm_title for sw in SYSTEM_WORDS):
            return 0

    title_words = set(norm_title.split())
    for tok in tokens:
        if any(ch.isdigit() for ch in tok):
            # Accept exact word or unit-suffixed form (e.g. "240" matching "240gb", or "12" matching "12pol")
            if tok not in title_words and not any(w.startswith(tok) and w[len(tok):].isalpha() for w in title_words):
                return 0

    hits = sum(1 for tok in tokens if tok in title_words or (len(tok) > 3 and tok in norm_title))
    cat_cfg = _category_config(category)
    for ex in cat_cfg.get("exclude", ()):
        if ex in norm_title and ex not in norm_query:
            return 0

    cat_context = cat_cfg.get("context", ())
    cat_hits = sum(1 for kw in cat_context if kw in norm_title) if cat_context else 0

    strict_req = len(tokens) if len(tokens) <= 4 else len(tokens) - 1
    if hits >= strict_req:
        return 100 + hits * 10 + cat_hits * 5

    # Category-assisted fallback when the user's product name is imprecise
    if cat_hits >= 2 and hits >= max(1, len(tokens) - 1):
        return 50 + hits * 10 + cat_hits * 5

    return 0


def _matches_query(title: str, query: str, category: str = "") -> bool:
    return _score_match(title, query, category) > 0


def _parse_brl_price(raw: str) -> float | None:
    cleaned = re.sub(r"[^\d,.]", "", raw or "")
    if not cleaned:
        return None
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def _fetch_html(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(url, headers=SEARCH_HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def _build_search_query(query: str, category: str) -> str:
    """Normalize joined tokens (e.g. ssd240gb -> ssd 240gb) and append category hint if helpful."""
    cleaned = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", query).strip()
    hint = _category_config(category).get("search_hint", "")
    if isinstance(hint, str) and hint and hint not in _normalize_text(cleaned):
        return f"{cleaned} {hint}".strip()
    return cleaned


def _search_kabum(query: str, category: str = "") -> list[dict]:
    """Query KaBuM! catalog and return direct product offers."""
    search_q = _build_search_query(query, category)
    slug = urllib.parse.quote(re.sub(r"\s+", "-", _normalize_text(search_q)))
    url = f"https://www.kabum.com.br/busca/{slug}?page_number=1&page_size=30&sort=price"
    html_text = _fetch_html(url)
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html_text, re.S)
    if not match:
        return []

    data = json.loads(match.group(1))
    catalog = data.get("props", {}).get("pageProps", {}).get("data")
    if isinstance(catalog, str):
        catalog = json.loads(catalog)
    products = (catalog or {}).get("catalogServer", {}).get("data", [])

    offers: list[dict] = []
    for p in products:
        if not p.get("available"):
            continue
        name = str(p.get("name") or "").strip()
        score = _score_match(name, query, category)
        if score <= 0:
            continue
        price = p.get("priceWithDiscount") or p.get("price")
        if not price or float(price) <= 0:
            continue
        code = p.get("code")
        friendly = p.get("friendlyName")
        if not code or not friendly:
            continue
        seller = str(p.get("sellerName") or "KaBuM!").strip()
        old_price = p.get("oldPrice")
        is_trusted = seller.lower() in TRUSTED_KABUM_SELLERS
        store_label = "KaBuM! (direto)" if seller.lower() == "kabum!" else f"KaBuM! ({seller})"

        offers.append({
            "store": store_label,
            "price": round(float(price), 2),
            "originalPrice": round(float(old_price), 2) if old_price and float(old_price) > float(price) else None,
            "coupon": "",
            "cashback": "",
            "shipping": "A calcular",
            "url": f"https://www.kabum.com.br/produto/{code}/{friendly}",
            "notes": f"{name} — Vendedor: {seller}",
            "_trusted": is_trusted,
            "_score": score,
        })

    offers.sort(key=lambda o: (o["_score"] < 100, not o["_trusted"], o["price"]))
    for o in offers:
        o.pop("_trusted", None)
        o.pop("_score", None)
    return offers[:4]


def _search_zoom(query: str, category: str = "") -> list[dict]:
    """Query Zoom sorted by lowest price, preferring canonical product pages and non-Magalu stores."""
    search_q = _build_search_query(query, category)
    url = f"https://www.zoom.com.br/search?q={urllib.parse.quote(search_q)}&sortBy=price_asc"
    html_text = _fetch_html(url)
    parts = html_text.split("<article ")
    offers: list[dict] = []
    seen_pairs: set[tuple[str, float]] = set()

    for part in parts[1:35]:
        href_m = re.search(r'href="([^"]+)"', part)
        name_m = re.search(r'data-testid="product-card::name"[^>]*>(.*?)</', part, re.S)
        price_m = re.search(r'data-testid="product-card::price"[^>]*>.*?<strong>(.*?)</strong>', part, re.S)
        if not (href_m and name_m and price_m):
            continue

        title = re.sub(r"\s+", " ", html_lib.unescape(name_m.group(1))).strip()
        score = _score_match(title, query, category)
        if score <= 0:
            continue

        price = _parse_brl_price(price_m.group(1))
        if price is None:
            continue

        merch_m = re.search(r"MerchantLink_OrqProductCard_MerchantLink[^>]*>(.*?)</article>", part, re.S)
        merchant = ""
        if merch_m:
            merchant = re.sub(r"<[^>]+>", " ", merch_m.group(1))
            merchant = re.sub(r"\s+", " ", html_lib.unescape(merchant)).strip()

        cashback_m = re.search(r'data-testid="product-card::cashback"[^>]*>(.*?)</div>', part, re.S)
        cashback = ""
        if cashback_m:
            cashback = re.sub(r"<[^>]+>", " ", cashback_m.group(1))
            cashback = re.sub(r"\s+", " ", html_lib.unescape(cashback)).strip()

        raw_href = html_lib.unescape(href_m.group(1))
        is_lead = "/lead?" in raw_href
        # Drop Magazine Luiza /lead ads because they frequently redirect to expired 404 ("Oops!") pages
        if is_lead and "magazine luiza" in merchant.lower():
            continue

        if is_lead:
            full_url = raw_href if raw_href.startswith("http") else f"https://www.zoom.com.br{raw_href}"
            store_label = f"{merchant} (via Zoom)" if merchant else "Zoom"
        else:
            clean_path = raw_href.split("?", 1)[0]
            full_url = clean_path if clean_path.startswith("http") else f"https://www.zoom.com.br{clean_path}"
            store_label = "Zoom (Comparador)"

        pair_key = (store_label, round(price, 2))
        if pair_key in seen_pairs:
            continue
        seen_pairs.add(pair_key)

        offers.append({
            "store": store_label,
            "price": round(price, 2),
            "originalPrice": None,
            "coupon": "",
            "cashback": cashback,
            "shipping": "Consultar no site",
            "url": full_url,
            "notes": title,
            "_score": score,
        })

    offers.sort(key=lambda o: (o["_score"] < 100, o["price"]))
    for o in offers:
        o.pop("_score", None)
    return offers[:4]


def _search_carrefour(query: str, category: str = "") -> list[dict]:
    """Query Carrefour Brasil and return direct /produto/ offers."""
    search_q = _build_search_query(query, category)
    url = f"https://www.carrefour.com.br/busca/{urllib.parse.quote(search_q)}"
    html_text = _fetch_html(url)
    parts = html_text.split('data-testid="search-product-card"')
    offers: list[dict] = []

    for idx in range(len(parts) - 1):
        before = parts[idx][-500:]
        after = parts[idx + 1][:2500]
        href_m = re.search(r'href="(/produto/[^"]+)"', before)
        if not href_m:
            href_m = re.search(r'href="(/produto/[^"]+)"', after)
        title_m = re.search(r"<h2[^>]*>(.*?)</h2>", after, re.S)
        price_m = re.search(r"R\$\s*([\d.,]+)", after)
        if not (href_m and title_m and price_m):
            continue

        title = re.sub(r"\s+", " ", html_lib.unescape(re.sub(r"<[^>]+>", " ", title_m.group(1)))).strip()
        score = _score_match(title, query, category)
        if score <= 0:
            continue

        price = _parse_brl_price(price_m.group(1))
        if price is None:
            continue

        offers.append({
            "store": "Carrefour",
            "price": round(price, 2),
            "originalPrice": None,
            "coupon": "",
            "cashback": "",
            "shipping": "Consultar no site",
            "url": f"https://www.carrefour.com.br{html_lib.unescape(href_m.group(1))}",
            "notes": title,
            "_score": score,
        })

    offers.sort(key=lambda o: (o["_score"] < 100, o["price"]))
    for o in offers:
        o.pop("_score", None)
    return offers[:4]


def _search_kalunga(query: str, category: str = "") -> list[dict]:
    """Query Kalunga and return direct /prod/ offers."""
    search_q = _build_search_query(query, category)
    url = f"https://www.kalunga.com.br/busca/{urllib.parse.quote(search_q)}/1"
    html_text = _fetch_html(url)
    parts = html_text.split('class="blocoproduto__link"')
    offers: list[dict] = []

    for part in parts[1:25]:
        href_m = re.search(r'href="(/prod/[^"]+)"', part)
        title_m = re.search(r'<h2 class="blocoproduto__title[^"]*">(.*?)</h2>', part, re.S)
        price_m = re.search(r'blocoproduto__price"[^>]*>\s*R\$\s*([\d.,]+)', part)
        if not (href_m and title_m and price_m):
            continue

        title = re.sub(r"\s+", " ", html_lib.unescape(title_m.group(1))).strip()
        score = _score_match(title, query, category)
        if score <= 0:
            continue

        price = _parse_brl_price(price_m.group(1))
        if price is None:
            continue

        offers.append({
            "store": "Kalunga",
            "price": round(price, 2),
            "originalPrice": None,
            "coupon": "",
            "cashback": "",
            "shipping": "A calcular",
            "url": f"https://www.kalunga.com.br{html_lib.unescape(href_m.group(1))}",
            "notes": title,
            "_score": score,
        })

    offers.sort(key=lambda o: (o["_score"] < 100, o["price"]))
    for o in offers:
        o.pop("_score", None)
    return offers[:4]


def _search_dafiti(query: str, category: str = "") -> list[dict]:
    """Query Dafiti Brasil for fashion, footwear, and beauty products."""
    search_q = _build_search_query(query, category)
    url = f"https://www.dafiti.com.br/catalog/?q={urllib.parse.quote(search_q)}"
    html_text = _fetch_html(url)
    parts = html_text.split('class="product-box"')
    offers: list[dict] = []

    for part in parts[1:25]:
        href_m = re.search(r'href="(https://www\.dafiti\.com\.br/[^"]+\.html)"', part)
        title_m = re.search(r'<p class="product-box-title"[^>]*>(.*?)</p>', part, re.S)
        price_m = re.search(r'class="product-box-price-to"[^>]*>\s*R\$\s*([\d.,]+)', part)
        if not price_m:
            price_m = re.search(r'class="product-box-price"[^>]*>.*?R\$\s*([\d.,]+)', part, re.S)
        if not (href_m and title_m and price_m):
            continue

        title = re.sub(r"\s+", " ", html_lib.unescape(title_m.group(1))).strip()
        score = _score_match(title, query, category)
        if score <= 0:
            continue

        price = _parse_brl_price(price_m.group(1))
        if price is None:
            continue

        from_m = re.search(r'class="product-box-price-from"[^>]*>\s*R\$\s*([\d.,]+)', part)
        orig_price = _parse_brl_price(from_m.group(1)) if from_m else None

        offers.append({
            "store": "Dafiti",
            "price": round(price, 2),
            "originalPrice": round(orig_price, 2) if orig_price and orig_price > price else None,
            "coupon": "",
            "cashback": "",
            "shipping": "Grátis acima de R$ 199,90",
            "url": html_lib.unescape(href_m.group(1)),
            "notes": title,
            "_score": score,
        })

    offers.sort(key=lambda o: (o["_score"] < 100, o["price"]))
    for o in offers:
        o.pop("_score", None)
    return offers[:4]


def _search_offers(query: str, category: str = "", max_offers: int = 6) -> dict:
    """Run store searches in parallel and return deduplicated, price-sorted offers."""
    providers = [
        ("KaBuM!", _search_kabum),
        ("Carrefour", _search_carrefour),
        ("Kalunga", _search_kalunga),
        ("Dafiti", _search_dafiti),
        ("Zoom", _search_zoom),
    ]
    all_offers: list[dict] = []
    sources_ok: list[str] = []
    errors: list[str] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(providers)) as pool:
        future_map = {pool.submit(fn, query, category): name for name, fn in providers}
        for future in concurrent.futures.as_completed(future_map):
            name = future_map[future]
            try:
                res = future.result()
                sources_ok.append(name)
                all_offers.extend(res)
            except Exception as exc:
                errors.append(f"{name}: {exc}")

    ordered = sorted(all_offers, key=lambda o: o["price"])

    # Drop extreme price outliers (> 2.3x cheapest offer) when cheaper real offers exist
    if len(ordered) >= 2:
        max_reasonable = ordered[0]["price"] * 2.3
        ordered = [o for o in ordered if o["price"] <= max_reasonable]

    seen: set[str] = set()
    deduped: list[dict] = []
    for offer in ordered:
        key = offer["url"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(offer)

    return {
        "offers": deduped[:max_offers],
        "sources": sources_ok,
        "errors": errors,
    }


def _empty_tracker_data() -> dict:
    return {
        "meta": {"title": "Friday Help", "currency": "BRL"},
        "items": [],
        "history": [],
    }


def _supabase_request(
    method: str,
    path: str,
    payload: dict | None = None,
    token: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict | list]:
    """Call Supabase Auth or PostgREST REST API using stdlib urllib."""
    url = f"{SUPABASE_URL}{path}"
    req_headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Content-Type": "application/json",
    }
    if token:
        req_headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        req_headers.update(extra_headers)

    body_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=body_bytes, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8", "ignore")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "ignore")
        try:
            err_data = json.loads(raw) if raw else {"error": exc.reason}
        except json.JSONDecodeError:
            err_data = {"error": raw or str(exc.reason)}
        return exc.code, err_data


def _get_supabase_user(token: str) -> dict | None:
    if not token or not SUPABASE_ENABLED:
        return None
    status, data = _supabase_request("GET", "/auth/v1/user", token=token)
    if status == 200 and isinstance(data, dict) and data.get("id"):
        return {"id": data["id"], "email": data.get("email", "")}
    return None


class TrackerHandler(SimpleHTTPRequestHandler):
    """Handler HTTP para arquivos estáticos e API JSON de ofertas."""

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _get_cookie(self, name: str) -> str:
        raw_cookie = self.headers.get("Cookie", "")
        if not raw_cookie:
            return ""
        cookie = http.cookies.SimpleCookie()
        cookie.load(raw_cookie)
        morsel = cookie.get(name)
        return morsel.value if morsel else ""

    def _set_auth_cookie(self, token: str, max_age: int = 604800) -> None:
        is_https = self.headers.get("X-Forwarded-Proto", "").lower() == "https"
        secure_flag = "; Secure" if is_https else ""
        self.send_header(
            "Set-Cookie",
            f"bf_token={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}{secure_flag}",
        )

    def _send_json(
        self,
        status: int,
        payload: dict,
        auth_cookie: tuple[str, int] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if auth_cookie is not None:
            self._set_auth_cookie(auth_cookie[0], auth_cookie[1])
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "Content-Length inválido."})
            return None

        if length <= 0 or length > 10 * 1024 * 1024:
            self._send_json(400, {"error": "Tamanho do payload inválido."})
            return None

        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send_json(400, {"error": f"Payload JSON inválido: {exc}"})
            return None
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Payload JSON deve ser um objeto."})
            return None
        return payload

    def do_GET(self) -> None:
        endpoint = self.path.split("?", 1)[0]

        if endpoint == "/api/health":
            db_ok = None
            if SUPABASE_ENABLED:
                status, _ = _supabase_request("GET", "/rest/v1/tracker_data?select=user_id&limit=1")
                db_ok = status == 200
            self._send_json(200, {"ok": True, "mode": "supabase" if SUPABASE_ENABLED else "local", "supabase": db_ok})
            return

        if endpoint == "/api/auth/status":
            if not SUPABASE_ENABLED:
                self._send_json(200, {"mode": "local", "authenticated": True, "user": None})
                return
            token = self._get_cookie("bf_token")
            user = _get_supabase_user(token)
            if user:
                self._send_json(200, {"mode": "supabase", "authenticated": True, "user": user})
            else:
                self._send_json(200, {"mode": "supabase", "authenticated": False, "user": None})
            return

        if endpoint == "/api/deals":
            if SUPABASE_ENABLED:
                token = self._get_cookie("bf_token")
                user = _get_supabase_user(token)
                if not user:
                    self._send_json(401, {"error": "Faça login para acessar seus dados."})
                    return
                status, rows = _supabase_request(
                    "GET",
                    f"/rest/v1/tracker_data?user_id=eq.{urllib.parse.quote(user['id'])}&select=data",
                    token=token,
                )
                if status != 200:
                    self._send_json(500, {"error": "Erro ao consultar Supabase.", "details": rows})
                    return
                if isinstance(rows, list) and rows:
                    self._send_json(200, rows[0].get("data") or _empty_tracker_data())
                else:
                    self._send_json(200, _empty_tracker_data())
                return

            if not DATA_FILE.exists():
                self._send_json(404, {"error": "Arquivo data/deals.json não encontrado."})
                return
            try:
                data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                self._send_json(200, data)
            except (OSError, json.JSONDecodeError) as exc:
                self._send_json(500, {"error": f"Erro ao ler deals.json: {exc}"})
            return

        super().do_GET()

    def do_POST(self) -> None:
        endpoint = self.path.split("?", 1)[0]

        if endpoint == "/api/auth/logout":
            self._send_json(200, {"ok": True}, auth_cookie=("", 0))
            return

        if endpoint not in ("/api/deals", "/api/search", "/api/auth/login", "/api/auth/signup"):
            self._send_json(404, {"error": "Endpoint não encontrado."})
            return

        payload = self._read_json_body()
        if payload is None:
            return

        if endpoint in ("/api/auth/login", "/api/auth/signup"):
            if not SUPABASE_ENABLED:
                self._send_json(400, {"error": "Modo nuvem (Supabase) não está configurado."})
                return
            email = str(payload.get("email") or "").strip()
            password = str(payload.get("password") or "")
            if not email or len(password) < 6:
                self._send_json(400, {"error": "Informe e-mail válido e senha com no mínimo 6 caracteres."})
                return

            sb_path = (
                "/auth/v1/token?grant_type=password"
                if endpoint == "/api/auth/login"
                else "/auth/v1/signup"
            )
            status, res = _supabase_request("POST", sb_path, payload={"email": email, "password": password})
            if status >= 400 or not isinstance(res, dict):
                msg = (res.get("msg") or res.get("error_description") or res.get("error") or "Falha na autenticação") if isinstance(res, dict) else "Falha na autenticação"
                self._send_json(401, {"error": str(msg)})
                return

            access_token = res.get("access_token", "")
            user_obj = res.get("user") or {}
            if not access_token and endpoint == "/api/auth/signup":
                self._send_json(200, {"ok": True, "needsConfirmation": True})
                return
            if not access_token:
                self._send_json(401, {"error": "Token de sessão não retornado pelo Supabase."})
                return

            self._send_json(
                200,
                {"ok": True, "user": {"id": user_obj.get("id", ""), "email": user_obj.get("email", email)}},
                auth_cookie=(access_token, int(res.get("expires_in", 604800))),
            )
            return

        if endpoint == "/api/search":
            query = str(payload.get("query") or "").strip()
            if len(query) < 2:
                self._send_json(400, {"error": "Informe um termo de busca válido."})
                return
            category = str(payload.get("category") or "").strip()
            max_offers = int(payload.get("maxOffers", 6))
            result = _search_offers(query, category=category, max_offers=max(1, min(max_offers, 12)))
            self._send_json(200, result)
            return

        if "items" not in payload:
            self._send_json(400, {"error": "Payload JSON inválido: JSON deve conter a chave 'items'."})
            return

        if SUPABASE_ENABLED:
            token = self._get_cookie("bf_token")
            user = _get_supabase_user(token)
            if not user:
                self._send_json(401, {"error": "Sessão expirada. Faça login novamente."})
                return
            status, res = _supabase_request(
                "POST",
                "/rest/v1/tracker_data?on_conflict=user_id",
                payload={"user_id": user["id"], "data": payload},
                token=token,
                extra_headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            )
            if status not in (200, 201, 204):
                self._send_json(500, {"error": "Erro ao salvar no Supabase.", "details": res})
                return
            self._send_json(200, {"ok": True})
            return

        try:
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            DATA_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self._send_json(200, {"ok": True})
        except OSError as exc:
            self._send_json(500, {"error": f"Erro ao salvar deals.json: {exc}"})


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    handler = partial(TrackerHandler, directory=str(BASE_DIR))
    server = ThreadingHTTPServer((host, port), handler)
    url = f"http://{host}:{port}"
    print(f"Black Friday Tracker rodando em {url}")
    print("Pressione Ctrl+C para encerrar.")

    if "--no-browser" not in sys.argv:
        webbrowser.open(url)

    def _handle_sigterm(signum: int, frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _handle_sigterm)

    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        print("\nServidor encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
