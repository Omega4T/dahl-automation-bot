#!/usr/bin/env python3
"""
Dahl Farm — Interactive CLI
───────────────────────────
Auto-register akun inference.dahl.global lewat proxy pool (rotasi IP nyata).

Mode:
  • Interaktif (default)  →  python dahl_farm.py
  • Non-interaktif        →  python dahl_farm.py --count 50 --workers 10
  • Subcommand lama tetap jalan (bright/sync/export/list/check)

Author : Omega4T — https://github.com/Omega4T
License: MIT
Note   : For educational / research purposes only.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Callable
from urllib.request import HTTPCookieProcessor, Request, build_opener

# ── third-party (rich / questionary) ────────────────────────────────
try:
    from rich.align import Align
    from rich.box import ROUNDED, SIMPLE, HEAVY
    from rich.columns import Columns
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import (
        BarColumn, Progress, SpinnerColumn, TaskProgressColumn,
        TextColumn, TimeElapsedColumn,
    )
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text
    from rich.theme import Theme

    import questionary
    from questionary import Style as QStyle

    HAS_TUI = True
except ImportError:  # graceful fallback ke mode plain
    HAS_TUI = False

# ══════════════════════════════════════════════════════════════════
#  KONFIGURASI
# ══════════════════════════════════════════════════════════════════
BASE = "https://inference.dahl.global"
HERE = Path(__file__).resolve().parent
CREDS_DIR = HERE / "creds"
MODEL_DEFAULT = "deepseek-ai/DeepSeek-V4-Flash-0731"
POOL_FILE = HERE / "keys.txt"
PROXY_POOL_FILE = HERE / "proxies-live.txt"
PROXY_SOURCE_FILE = HERE / "proxies.txt"
ENV_FILE = HERE / ".env"

FILE_LOCK = threading.Lock()

MODELS = {
    "MiniMax M2.7 (recommended)": "MiniMaxAI/MiniMax-M2.7",
    "GLM-5.3-Flash": "zai-org/GLM-5.3-Flash",
    "DeepSeek-V4-Flash": "deepseek-ai/DeepSeek-V4-Flash-0731",
}


# ── .env loader ─────────────────────────────────────────────────────
def load_env(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        if k and k not in os.environ:
            os.environ[k] = v


load_env()

BRIGHTDATA_URL = os.getenv("BRIGHTDATA_URL", "")
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")

UA = "Mozilla/5.0 (Android 13; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0"

ADJ = ["swift", "quiet", "brave", "lucky", "cosmic", "rapid", "clever", "mellow",
       "crimson", "golden", "amber", "bright", "calm", "coral", "daring", "eager",
       "fierce", "gentle", "icy", "jolly", "kind", "lunar", "misty", "noble",
       "polar", "proud", "rusty", "silver", "solar", "tidy", "vivid", "wild",
       "bold", "cozy", "keen", "nimble"]
NOUN = ["eagle", "otter", "falcon", "panda", "comet", "signal", "raven", "tiger",
        "nebula", "lynx", "badger", "birch", "bison", "cedar", "cloud", "crane",
        "dove", "ember", "fern", "finch", "fox", "heron", "maple", "mink", "moose",
        "orca", "owl", "pebble", "pine", "robin", "seal", "spruce", "stork",
        "whale", "wren", "brook"]


def rand_username() -> str:
    return f"{random.choice(ADJ)}_{random.choice(NOUN)}_{random.randint(100, 999)}"


# ══════════════════════════════════════════════════════════════════
#  TEMA & CONSOLE
# ══════════════════════════════════════════════════════════════════
THEME = Theme({
    "brand": "bold cyan",
    "brand2": "bold magenta",
    "ok": "bold green",
    "warn": "bold yellow",
    "err": "bold red",
    "dim2": "grey62",
    "accent": "bold blue",
    "key": "bold bright_green",
}) if HAS_TUI else None

console = Console(theme=THEME) if HAS_TUI else None

QSTYLE = QStyle([
    ("qmark", "fg:#00d7ff bold"),
    ("question", "bold"),
    ("answer", "fg:#00ff87 bold"),
    ("pointer", "fg:#ff5fff bold"),
    ("highlighted", "fg:#ff5fff bold"),
    ("selected", "fg:#00ff87"),
    ("separator", "fg:#6c6c6c"),
    ("instruction", "fg:#6c6c6c italic"),
]) if HAS_TUI else None

BANNER = r"""
   ██████╗  █████╗ ██╗  ██╗██╗         ███████╗ █████╗ ██████╗ ███╗   ███╗
   ██╔══██╗██╔══██╗██║  ██║██║         ██╔════╝██╔══██╗██╔══██╗████╗ ████║
   ██║  ██║███████║███████║██║         █████╗  ███████║██████╔╝██╔████╔██║
   ██║  ██║██╔══██║██╔══██║██║         ██╔══╝  ██╔══██║██╔══██╗██║╚██╔╝██║
   ██████╔╝██║  ██║██║  ██║███████╗    ██║     ██║  ██║██║  ██║██║ ╚═╝ ██║
   ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝    ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
"""


CREDIT = "github.com/Omega4T"


def show_banner() -> None:
    if not HAS_TUI:
        print("DAHL FARM — dahl.global auto-register")
        print(f"  by Omega4T  ·  {CREDIT}  ·  MIT License")
        return
    console.print(Text(BANNER, style="brand2"), justify="center")
    console.print(Align.center(
        Text("dahl.global  ·  auto-register  ·  proxy-pool rotation",
             style="dim2")))
    console.print(Align.center(
        Text(f"by Omega4T  ·  {CREDIT}  ·  MIT License", style="brand")))
    console.print()


def print_credit() -> None:
    """Baris credit untuk semua run non-interaktif (subcommand)."""
    line = f"DAHL FARM  ·  by Omega4T  ·  {CREDIT}  ·  MIT License"
    if HAS_TUI:
        console.print(Align.center(Text(line, style="dim2")))
    else:
        print(line)


# ══════════════════════════════════════════════════════════════════
#  HTTP CLIENT
# ══════════════════════════════════════════════════════════════════
class Dahl:
    """Klien direct (urllib) — dipakai buat check key & tanpa proxy."""

    def __init__(self) -> None:
        self.jar = CookieJar()
        self.op = build_opener(HTTPCookieProcessor(self.jar))

    def _req(self, method, path, payload=None, extra=None, timeout=15):
        url = BASE + path
        data = json.dumps(payload).encode() if payload is not None else None
        hdrs = {"User-Agent": UA, "Accept": "application/json",
                "Referer": f"{BASE}/account", "Origin": BASE}
        if data is not None:
            hdrs["Content-Type"] = "application/json"
        if extra:
            hdrs.update(extra)
        req = Request(url, data=data, headers=hdrs, method=method)
        try:
            r = self.op.open(req, timeout=timeout)
            status, raw = r.status, r.read()
        except Exception as e:
            code = getattr(e, "code", None)
            raw = getattr(e, "read", lambda: b"")() if code else b""
            if code:
                status, raw = code, raw
            else:
                raise RuntimeError(f"network error {url}: {e}")
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {"_raw": raw.decode(errors="replace")}
        return status, body

    def signup(self, u):          return self._req("POST", "/v1/auth/signup", {"username": u})
    def signin(self, fp):         return self._req("POST", "/v1/auth/signin", {"fingerprint": fp})
    def account(self):            return self._req("GET", "/v1/account")
    def allocate(self, kid, amt): return self._req("POST", "/v1/account/allocate", {"amount": amt, "key_id": kid})
    def account_keys(self):       return self._req("GET", "/v1/account/keys")
    def signout(self):            return self._req("POST", "/v1/auth/signout")
    def key_tokens(self, tok):    return self._req("GET", "/tokens/current", extra={"Authorization": f"Bearer {tok}"})
    def chat(self, model, tok, content="ping"):
        return self._req("POST", "/v1/chat/completions",
                         {"model": model, "messages": [{"role": "user", "content": content}], "max_tokens": 4},
                         extra={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})


class ProxyPool:
    """Pool proxy thread-safe: ambil acak, blacklist yang mati."""

    def __init__(self, proxies=None, path=None):
        self._lock = threading.Lock()
        self.proxies = list(proxies) if proxies else self._load(path)
        self.bad: set[str] = set()          # proxy RUSAK permanen (407/timeout/refused)
        self._cooldown: dict[str, float] = {}  # proxy PARKING (rate limit) → waktu bebas
        if not self.proxies:
            raise RuntimeError(f"pool proxy kosong ({path or PROXY_POOL_FILE})")

    @staticmethod
    def _load(path):
        p = Path(path or PROXY_POOL_FILE)
        if not p.exists():
            return []
        return [l.strip() for l in p.read_text(encoding="utf-8").splitlines()
                if l.strip().startswith("http")]

    def _is_parked(self, p: str) -> bool:
        until = self._cooldown.get(p)
        if until is None:
            return False
        if time.time() >= until:
            self._cooldown.pop(p, None)   # cooldown selesai → balik ke live
            return False
        return True

    def get(self, exclude=None):
        """Ambil proxy acak yang TIDAK bad dan TIDAK sedang parking."""
        with self._lock:
            live = [p for p in self.proxies
                    if p not in self.bad and not self._is_parked(p)]
            if exclude:
                alt = [p for p in live if p not in exclude]
                if alt:
                    live = alt
            if not live:
                # semua parking/bad → kalau ada yang parking, pakai yang paling cepat bebas
                parked = [(p, u) for p, u in self._cooldown.items() if p not in self.bad]
                if parked:
                    return min(parked, key=lambda kv: kv[1])[0]
                raise RuntimeError("semua proxy di pool sudah ditandai bad")
            return random.choice(live)

    def mark_bad(self, proxy):
        """Proxy RUSAK permanen: 407 auth, connection refused, timeout berulang."""
        with self._lock:
            self.bad.add(proxy)

    def cooldown(self, proxy, seconds=45.0):
        """Proxy HIDUP tapi kena rate-limit → parking sebentar, balik otomatis."""
        with self._lock:
            if proxy not in self.bad:
                self._cooldown[proxy] = time.time() + seconds

    def mark_ok(self, proxy):
        with self._lock:
            self.bad.discard(proxy)
            self._cooldown.pop(proxy, None)

    @property
    def live_count(self):
        with self._lock:
            return len([p for p in self.proxies
                        if p not in self.bad and not self._is_parked(p)])

    @property
    def parked_count(self):
        with self._lock:
            return len([p for p in self.proxies
                        if p not in self.bad and self._is_parked(p)])

    @property
    def bad_count(self):
        with self._lock:
            return len(self.bad)

    @property
    def total(self):
        return len(self.proxies)


class DahlProxied:
    """Klien httpx lewat pool proxy — rotasi IP nyata per akun."""

    def __init__(self, proxy_url=None, pool=None):
        import httpx
        self.httpx = httpx
        self.pool = pool
        self.base_proxy = proxy_url or BRIGHTDATA_URL
        self.current_proxy = None
        self.c = None
        self._pick()

    def _pick(self, exclude=None):
        if self.pool is not None:
            self.current_proxy = self.pool.get(exclude=exclude)
        else:
            self.current_proxy = self.base_proxy
        self._build_client()

    def rotate_ip(self, reason="dead", cooldown=45.0):
        """Ganti IP.

        reason='rate_limit' → proxy PARKING (masih hidup, kena 429).
        reason='dead'       → proxy DIBUANG permanen (407/timeout/refused).
        """
        if self.pool is None:
            self._build_client()
            return
        old = self.current_proxy
        if old:
            if reason == "rate_limit":
                self.pool.cooldown(old, cooldown)
            else:
                self.pool.mark_bad(old)
        # hindari langsung memilih proxy yang sama
        self._pick(exclude={old} if old else None)

    def _build_client(self):
        kwargs = dict(follow_redirects=True,
                      timeout=self.httpx.Timeout(12.0, connect=5.0),
                      headers={"User-Agent": UA})
        if self.current_proxy:
            kwargs["proxy"] = self.current_proxy
        self.c = self.httpx.Client(**kwargs)

    def _req(self, method, path, payload=None, extra=None, timeout=12):
        hdrs = {"Accept": "application/json",
                "Referer": f"{BASE}/account", "Origin": BASE}
        if payload is not None:
            hdrs["Content-Type"] = "application/json"
        if extra:
            hdrs.update(extra)
        try:
            r = self.c.request(method, BASE + path, json=payload, headers=hdrs, timeout=timeout)
            try:
                body = r.json()
            except Exception:
                body = {"_raw": r.text[:200]}
            return r.status_code, body
        except Exception:
            return 500, {}

    def signup(self, u):        return self._req("POST", "/v1/auth/signup", {"username": u})
    def signin(self, fp):       return self._req("POST", "/v1/auth/signin", {"fingerprint": fp})
    def account(self):          return self._req("GET", "/v1/account")
    def allocate(self, kid, a): return self._req("POST", "/v1/account/allocate", {"key_id": kid, "amount": a})
    def account_keys(self):     return self._req("GET", "/v1/account/keys")
    def signout(self):          return self._req("POST", "/v1/auth/signout", {})
    def key_tokens(self, tok):  return self._req("GET", "/tokens/current", extra={"Authorization": f"Bearer {tok}"})
    def chat(self, model, tok):
        return self._req("POST", "/v1/chat/completions",
                         {"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 4},
                         extra={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})


# ── nama lama dipertahankan biar kompatibel ─────────────────────────
DahlBrightData = DahlProxied


# ══════════════════════════════════════════════════════════════════
#  PENYIMPANAN
# ══════════════════════════════════════════════════════════════════
def append_key_to_file(api_key: str) -> None:
    try:
        with FILE_LOCK:
            existing = set()
            if POOL_FILE.exists():
                existing = set(POOL_FILE.read_text(encoding="utf-8").splitlines())
            if api_key not in existing:
                with open(POOL_FILE, "a", encoding="utf-8") as f:
                    f.write(f"{api_key}\n")
    except Exception:
        pass


def save_cred(rec, idx) -> Path:
    CREDS_DIR.mkdir(parents=True, exist_ok=True)
    user = rec["user"]["username"]
    f = CREDS_DIR / f"{user}.txt"
    lines = ["# Dahl account credentials",
             "# Keep this file safe: fingerprint = password, cannot be recovered.",
             "# Sign in at: https://dahl.global", "",
             f"username: {user}",
             f"user_id: {rec['user']['user_id']}",
             f"fingerprint: {rec['fingerprint']}",
             f"api_key: {rec['api_key']['token']}",
             f"key_id: {rec['api_key']['id']}",
             f"farmed: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}", ""]
    with FILE_LOCK:
        f.write_text("\n".join(lines), encoding="utf-8")
    append_key_to_file(rec["api_key"]["token"])
    return f


def send_telegram_msg(token, chat_id, text) -> bool:
    if not token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
        req = Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        build_opener().open(req, timeout=10)
        return True
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════
#  CORE FARM LOGIC
# ══════════════════════════════════════════════════════════════════
def do_signup(api, index, backoff=1.5, max_tries=1000):
    """Signup sampai berhasil. Rotasi IP dengan alasan tepat:

    429 rate_limit → proxy PARKING (masih hidup, balik nanti).
    lain (>=400 / exception) → proxy DIBUANG permanen.
    """
    attempt = 0
    while attempt < max_tries:
        attempt += 1
        try:
            st, body = api.signup(rand_username())
            if st in (200, 201) and "fingerprint" in body:
                return body, st
            if st == 429:
                # rate limit per-IP: parking proxy, jangan buang
                api.rotate_ip(reason="rate_limit", cooldown=45.0)
                time.sleep(backoff + random.random())
            elif st >= 400:
                # error permanen: buang proxy ini
                api.rotate_ip(reason="dead")
                time.sleep(0.3)
        except Exception:
            api.rotate_ip(reason="dead")
            time.sleep(0.3)
    raise RuntimeError("signup exhausted")


def finish_account(api, body, index, model, verify_chat=False):
    fp, tok, kid = body["fingerprint"], body["api_key"]["token"], body["api_key"]["id"]
    st, _ = api.signin(fp)
    if st != 200:
        raise RuntimeError(f"signin HTTP {st}")
    pool = 0
    st, acc = api.account()
    if st == 200:
        pool = acc.get("token_balance", 0)
    allocated = 0
    if pool:
        ok_alloc = False
        try:
            st_alloc, _ = api.allocate(kid, pool)
            ok_alloc = st_alloc in (200, 201)
        except Exception:
            pass
        stv, tv = api.key_tokens(tok)
        if stv == 200 and isinstance(tv, dict):
            allocated = tv.get("available_tokens", 0)
        elif ok_alloc:
            allocated = pool
    if verify_chat:
        try:
            api.chat(model, tok)
        except Exception:
            pass
    try:
        api.signout()
    except Exception:
        pass
    save_cred(body, index)
    return {"index": index, "username": body["user"]["username"],
            "key": tok, "allocated": allocated}


def worker_process(index, opts, pool):
    try:
        api = DahlProxied(pool=pool)
        body, st = do_signup(api, index, backoff=opts["backoff"])
        res = finish_account(api, body, index, opts["model"], opts["verify_chat"])
        return True, res
    except Exception as e:
        return False, {"index": index, "err": str(e)[:80]}


# ══════════════════════════════════════════════════════════════════
#  UI HELPERS
# ══════════════════════════════════════════════════════════════════
def ram_info() -> tuple[float, float, float]:
    """(available_gb, total_gb, swap_used_pct)"""
    try:
        with open("/proc/meminfo") as f:
            d = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
        total = d["MemTotal"] / 1_048_576
        avail = d.get("MemAvailable", d["MemFree"]) / 1_048_576
        swap_total = d.get("SwapTotal", 1) or 1
        swap_used = (swap_total - d.get("SwapFree", 0)) / swap_total * 100
        return avail, total, swap_used
    except Exception:
        return 0.0, 0.0, 0.0


def safe_workers() -> int:
    """Rekomendasi worker berdasar RAM tersedia (≈20MB per worker + margin)."""
    avail, _, swap_pct = ram_info()
    base = 2
    by_ram = max(base, int((avail - 0.8) * 1024 / 20))
    if swap_pct > 90:
        by_ram = min(by_ram, 10)
    return max(2, min(by_ram, 60))


def count_creds() -> int:
    if not CREDS_DIR.exists():
        return 0
    return len(list(CREDS_DIR.glob("*.txt")))


def count_keys() -> int:
    if not POOL_FILE.exists():
        return 0
    return len([l for l in POOL_FILE.read_text().splitlines() if l.strip().startswith("dahl_")])


def pool_status() -> tuple[int, int, bool]:
    """(total, live_hint, exists) — live_hint dari file (tanpa validasi jaringan)."""
    p = PROXY_POOL_FILE
    if not p.exists():
        return 0, 0, False
    lines = [l for l in p.read_text().splitlines() if l.strip().startswith("http")]
    return len(lines), len(lines), True


def status_panel() -> Panel:
    avail, total, swap_pct = ram_info()
    p_total, _, p_ok = pool_status()
    swap_style = "err" if swap_pct > 90 else ("warn" if swap_pct > 60 else "ok")
    line1 = Text.assemble(
        ("  Akun tersimpan  ", "dim2"), (f"{count_creds():>4}", "ok"),
        ("    API keys  ", "dim2"), (f"{count_keys():>4}", "ok"),
        ("    Proxy pool  ", "dim2"),
        (f"{p_total if p_ok else 'MISSING':>4}", "ok" if p_ok else "err"),
    )
    line2 = Text.assemble(
        ("  RAM tersedia  ", "dim2"), (f"{avail:4.1f} GB", "accent"),
        ("/", "dim2"), (f"{total:.1f} GB", "dim2"),
        ("      Swap  ", "dim2"), (f"{swap_pct:4.0f}%", swap_style),
        ("      Worker saran  ", "dim2"), (f"{safe_workers():>2}", "brand"),
    )
    return Panel(Group(line1, line2), title="[brand]STATUS[/]",
                 border_style="bright_blue", box=ROUNDED, padding=(0, 1))


def progress_bar():
    return Progress(
        SpinnerColumn(style="brand"),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=None, complete_style="brand2", finished_style="ok"),
        TaskProgressColumn(),
        TextColumn("[dim2]{task.fields[status]}"),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )


# ══════════════════════════════════════════════════════════════════
#  AKSI: FARM
# ══════════════════════════════════════════════════════════════════
def run_farm(count: int, workers: int, model: str, backoff: float,
             verify_chat: bool, notify_tg: bool, pool_path: Path | None = None) -> dict:
    """Jalankan farming dengan progress bar live. Return ringkasan."""
    if not HAS_TUI:
        return _run_farm_plain(count, workers, model, backoff, verify_chat, notify_tg, pool_path)

    try:
        pool = ProxyPool(path=pool_path or PROXY_POOL_FILE)
    except RuntimeError as e:
        console.print(Panel(f"[err]{e}[/]\n\n[dim2]Taruh daftar proxy di:[/] {PROXY_POOL_FILE}",
                            title="[err]PROXY POOL ERROR[/]", border_style="red"))
        return {"ok": [], "fail": [], "aborted": True}

    console.print(Panel(
        Text.assemble(
            ("  Target      ", "dim2"), (f"{count} akun\n", "ok"),
            ("  Workers     ", "dim2"), (f"{workers}\n", "accent"),
            ("  Model       ", "dim2"), (f"{model}\n", "brand2"),
            ("  Proxy pool  ", "dim2"), (f"{pool.total} IP\n", "brand"),
            ("  Verify chat ", "dim2"), (("ya" if verify_chat else "tidak") + "\n", "warn"),
            ("  Notif TG    ", "dim2"), ("ya" if notify_tg else "tidak", "warn"),
        ),
        title="[brand2]KONFIGURASI FARM[/]", border_style="magenta", box=ROUNDED,
        padding=(1, 2)))

    ok, fail = [], []
    start = time.time()

    with progress_bar() as bar:
        task = bar.add_task("Farming", total=count, status="memulai…")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            opts = {"model": model, "backoff": backoff, "verify_chat": verify_chat}
            futs = {ex.submit(worker_process, i, opts, pool): i for i in range(1, count + 1)}
            done = 0
            for f in as_completed(futs):
                success, res = f.result()
                done += 1
                (ok if success else fail).append(res)
                status = (f"[ok]✓ {res['username']} ({res['allocated']:,})"
                          if success else "[err]✗ gagal")
                bar.update(task, advance=1,
                           status=f"{status}  [dim2]pool {pool.live_count}/{pool.total} "
                                  f"parked {pool.parked_count}[/]")

    total_time = time.time() - start
    summary = {"ok": ok, "fail": fail, "time": total_time,
               "avg": total_time / max(1, count), "pool": (pool.live_count, pool.total)}
    show_summary(summary)
    if notify_tg:
        _notify(summary)
    return summary


def _run_farm_plain(count, workers, model, backoff, verify_chat, notify_tg, pool_path=None):
    """Fallback tanpa rich."""
    try:
        pool = ProxyPool(path=pool_path or PROXY_POOL_FILE)
    except RuntimeError as e:
        print(f"[!] {e}")
        return {"ok": [], "fail": [], "aborted": True}
    print(f"== Farm {count} akun, {workers} worker, pool {pool.total} ==")
    ok, fail = [], []
    start = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        opts = {"model": model, "backoff": backoff, "verify_chat": verify_chat}
        futs = {ex.submit(worker_process, i, opts, pool): i for i in range(1, count + 1)}
        for f in as_completed(futs):
            s, r = f.result()
            if s:
                ok.append(r)
                print(f"[{r['index']:02d}] OK {r['username']} alloc={r['allocated']}")
            else:
                fail.append(r)
                print(f"[{r['index']:02d}] FAILED")
    tt = time.time() - start
    print(f"\n== DONE: {len(ok)} ok, {len(fail)} fail | {tt:.1f}s | {tt/max(1,count):.2f}s/akun ==")
    if notify_tg:
        _notify({"ok": ok, "fail": fail, "time": tt, "avg": tt / max(1, count)})
    return {"ok": ok, "fail": fail, "time": tt, "avg": tt / max(1, count)}


def show_summary(s: dict) -> None:
    ok, fail = s["ok"], s["fail"]
    total_alloc = sum(r.get("allocated", 0) for r in ok)
    tbl = Table(title="[brand2]HASIL FARM[/]", box=ROUNDED, border_style="magenta",
                header_style="brand", show_lines=False)
    tbl.add_column("#", justify="right", style="dim2", width=4)
    tbl.add_column("Username", style="ok")
    tbl.add_column("API Key", style="key")
    tbl.add_column("Tokens", justify="right", style="accent")

    for r in ok[:20]:
        tbl.add_row(str(r["index"]), r["username"],
                    r["key"][:22] + "…", f"{r['allocated']:,}")
    if len(ok) > 20:
        tbl.add_row("…", f"[dim2](+{len(ok) - 20} lainnya)[/]", "", "")

    stats = Text.assemble(
        ("\n  Berhasil  ", "dim2"), (f"{len(ok)}", "ok"),
        ("    Gagal  ", "dim2"), (f"{len(fail)}", "err"),
        ("    Waktu  ", "dim2"), (f"{s['time']:.1f}s", "accent"),
        ("    Rata2  ", "dim2"), (f"{s['avg']:.2f}s/akun", "accent"),
        ("    Total token  ", "dim2"), (f"{total_alloc:,}", "brand2"),
    )
    console.print(tbl)
    console.print(stats)
    console.print(f"[dim2]  Keys →[/] {POOL_FILE}   [dim2]Creds →[/] {CREDS_DIR}")
    console.print()


def _notify(s: dict) -> None:
    if not (TG_BOT_TOKEN and TG_CHAT_ID):
        return
    ok, fail = s["ok"], s["fail"]
    msg = ("<b>🌾 DAHL FARMING SUMMARY</b>\n"
           "========================\n"
           f"<b>Success:</b> {len(ok)}\n"
           f"<b>Failed:</b> {len(fail)}\n"
           f"<b>Time:</b> {s['time']:.1f}s\n"
           f"<b>Avg:</b> {s['avg']:.2f}s / account\n\n"
           "<b>Keys:</b>\n")
    for r in ok:
        msg += f"<code>{r['key']}</code>\n"
    if send_telegram_msg(TG_BOT_TOKEN, TG_CHAT_ID, msg):
        console.print("[ok]✓ Ringkasan dikirim ke Telegram[/]")


# ══════════════════════════════════════════════════════════════════
#  AKSI: PROXY POOL
# ══════════════════════════════════════════════════════════════════
def validate_pool(max_check: int = 100, save: bool = True) -> list[str]:
    """Validasi proxy dari file sumber → simpan yang hidup ke proxies-live.txt."""
    import httpx

    src = PROXY_SOURCE_FILE if PROXY_SOURCE_FILE.exists() else PROXY_POOL_FILE
    lines = [l.strip() for l in src.read_text().splitlines() if l.strip().startswith("http")]
    if not lines:
        console.print("[err]Tidak ada proxy di file sumber[/]")
        return []
    lines = lines[:max_check]

    live: list[str] = []
    with progress_bar() as bar:
        task = bar.add_task("Validasi proxy", total=len(lines), status="…")

        def _check(px):
            try:
                with httpx.Client(proxy=px, timeout=httpx.Timeout(12.0, connect=7.0),
                                  headers={"User-Agent": UA}) as c:
                    ip = c.get("https://api.ipify.org").text.strip()
                return px, ip if len(ip) > 5 else None
            except Exception:
                return px, None

        with ThreadPoolExecutor(max_workers=25) as ex:
            for px, ip in ex.map(_check, lines):
                if ip:
                    live.append(px)
                    bar.update(task, advance=1, status=f"[ok]✓ {ip}[/]")
                else:
                    bar.update(task, advance=1, status="[err]✗ dead[/]")

    if save and live:
        PROXY_POOL_FILE.write_text("\n".join(live) + "\n", encoding="utf-8")
        console.print(f"[ok]✓ {len(live)} proxy hidup[/] → [dim2]{PROXY_POOL_FILE}[/]")
    else:
        console.print(f"[warn]{len(live)}/{len(lines)} proxy hidup (tidak disimpan)[/]")
    return live


# ══════════════════════════════════════════════════════════════════
#  AKSI: LIST / EXPORT / SYNC / CHECK
# ══════════════════════════════════════════════════════════════════
def load_creds() -> list[dict]:
    rows = []
    if not CREDS_DIR.exists():
        return rows
    for f in sorted(CREDS_DIR.glob("*.txt")):
        d = {}
        for line in f.read_text(errors="ignore").splitlines():
            if ": " in line and not line.startswith("#"):
                k, v = line.split(": ", 1)
                d[k] = v
        if d.get("username"):
            rows.append(d)
    return rows


def action_list() -> None:
    rows = load_creds()
    if not rows:
        console.print("[warn]Belum ada akun tersimpan.[/]")
        return
    tbl = Table(title=f"[brand2]AKUN TERFARM ({len(rows)})[/]", box=ROUNDED,
                border_style="magenta", header_style="brand")
    tbl.add_column("Username", style="ok")
    tbl.add_column("API Key", style="key")
    tbl.add_column("Farmed", style="dim2")
    for d in rows:
        tbl.add_row(d.get("username", "?"), (d.get("api_key", "?")[:26] + "…"),
                    d.get("farmed", "?")[:19])
    console.print(tbl)


def action_export(all_time: bool = False, out: Path | None = None) -> None:
    since = None if all_time else time.strftime("%Y-%m-%d")
    rows = load_creds()
    rows = [d for d in rows if not since or d.get("farmed", "").startswith(since)]
    out = out or HERE / "keys_farmed.txt"
    lines = [f"# Dahl API keys — since {since or 'ALL'}", f"# total: {len(rows)} keys", ""]
    for d in rows:
        lines.append(f"{d.get('api_key','')}   # {d.get('username','?')}  {d.get('farmed','?')}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"[ok]✓ {len(rows)} keys →[/] {out}")


def action_sync() -> None:
    keys = set()
    for d in load_creds():
        if d.get("api_key"):
            keys.add(d["api_key"])
    if POOL_FILE.exists():
        for line in POOL_FILE.read_text().splitlines():
            if line.strip().startswith("dahl_"):
                keys.add(line.strip())
    POOL_FILE.write_text("\n".join(sorted(keys)) + "\n", encoding="utf-8")
    console.print(f"[ok]✓ keys.txt: {len(keys)} unik[/]")


def action_check(token: str | None = None) -> None:
    if not token:
        token = questionary.text("API key (dahl_…):", qmark="▸",
                                 style=QSTYLE).ask()
    if not token:
        return
    token = token.strip()
    api = Dahl()
    with console.status("[brand]Memeriksa key…[/]", spinner="dots"):
        st_tok, tok_body = api.key_tokens(token)
        st_chat, chat_body = api.chat(MODEL_DEFAULT, token)

    ok_tok = st_tok == 200 and tok_body.get("available_tokens", 0) > 0
    tbl = Table(box=SIMPLE, show_header=False, border_style="bright_blue")
    tbl.add_column(style="dim2", width=14)
    tbl.add_column()
    tbl.add_row("Key", token[:20] + "…")
    tbl.add_row("Tokens", f"[ok]{tok_body.get('available_tokens', 0):,}[/]"
                if ok_tok else f"[err]HTTP {st_tok}[/]")
    tbl.add_row("Chat API", f"[ok]HTTP {st_chat}[/]" if st_chat == 200
                else f"[err]HTTP {st_chat}[/]")
    if st_chat == 200:
        try:
            msg = chat_body["choices"][0]["message"]["content"][:60].replace("\n", " ")
            tbl.add_row("Respons", f"[dim2]{msg}[/]")
        except Exception:
            pass
    console.print(Panel(tbl, title="[brand]HASIL CHECK[/]", border_style="cyan", box=ROUNDED))


# ══════════════════════════════════════════════════════════════════
#  MENU INTERAKTIF
# ══════════════════════════════════════════════════════════════════
def ask_farm_config() -> dict | None:
    console.print(Rule("[brand2]Konfigurasi Farm[/]", style="bright_black"))

    count = questionary.text(
        "Jumlah akun:", default="10", qmark="▸", style=QSTYLE,
        validate=lambda x: x.isdigit() and int(x) > 0 or "masukkan angka > 0").ask()
    if count is None:
        return None

    sug = safe_workers()
    workers = questionary.text(
        f"Workers (aman untuk mesin ini: {sug}):", default=str(sug), qmark="▸",
        style=QSTYLE, validate=lambda x: x.isdigit() and int(x) > 0 or "angka > 0").ask()
    if workers is None:
        return None

    model = questionary.select("Model (untuk verifikasi chat):",
                               choices=list(MODELS.keys()), default=list(MODELS.keys())[0],
                               qmark="▸", style=QSTYLE).ask()
    if model is None:
        return None

    verify = questionary.confirm("Verifikasi chat per akun? (lebih lambat, lebih pasti)",
                                 default=False, qmark="▸", style=QSTYLE).ask()
    notify = questionary.confirm("Kirim ringkasan ke Telegram?",
                                 default=bool(TG_BOT_TOKEN and TG_CHAT_ID),
                                 qmark="▸", style=QSTYLE).ask()

    if verify is None or notify is None:
        return None

    return {"count": int(count), "workers": int(workers),
            "model": MODELS[model], "verify_chat": verify, "notify_tg": notify}


def menu() -> None:
    while True:
        console.clear()
        show_banner()
        console.print(status_panel())
        console.print()

        p_total, _, p_ok = pool_status()
        choice = questionary.select(
            "Pilih aksi:",
            qmark="❯",
            style=QSTYLE,
            choices=[
                questionary.Choice("🌾  Farm akun baru", "farm"),
                questionary.Choice("🔍  Validasi / refresh proxy pool", "proxy"),
                questionary.Choice("📋  Lihat akun terfarm", "list"),
                questionary.Choice("📤  Export keys", "export"),
                questionary.Choice("🔑  Cek satu API key", "check"),
                questionary.Choice("🔄  Sync keys.txt", "sync"),
                questionary.Separator(),
                questionary.Choice("🚪  Keluar", "quit"),
            ],
        ).ask()

        if choice is None or choice == "quit":
            console.print("\n[dim2]Sampai jumpa, bro. 👋[/]\n")
            return

        console.print()
        try:
            if choice == "farm":
                cfg = ask_farm_config()
                if cfg:
                    run_farm(cfg["count"], cfg["workers"], cfg["model"],
                             0.2, cfg["verify_chat"], cfg["notify_tg"])
            elif choice == "proxy":
                console.print(Panel("Validasi proxy dari file sumber → simpan yang hidup.",
                                    border_style="cyan", box=ROUNDED))
                if questionary.confirm("Mulai validasi (bisa lama)?", default=True,
                                       qmark="▸", style=QSTYLE).ask():
                    validate_pool()
            elif choice == "list":
                action_list()
            elif choice == "export":
                allt = questionary.confirm("Export SEMUA (bukan hanya hari ini)?",
                                           default=False, qmark="▸", style=QSTYLE).ask()
                action_export(all_time=bool(allt))
            elif choice == "check":
                action_check()
            elif choice == "sync":
                action_sync()
        except KeyboardInterrupt:
            console.print("\n[warn]Dibatalkan.[/]")

        console.print()
        questionary.press_any_key_to_continue("Tekan enter untuk kembali ke menu…",
                                              style=QSTYLE).ask()


# ══════════════════════════════════════════════════════════════════
#  CLI (non-interaktif / subcommand lama)
# ══════════════════════════════════════════════════════════════════
def cmd_brightfarm(args) -> None:
    pool_path = Path(args.proxy_pool) if args.proxy_pool else None
    if args.proxy:
        p = Path(args.proxy)
        prox = ProxyPool._load(p) if p.exists() else [args.proxy]
        pool_path = None
        # tulis sementara
        tmp = HERE / ".proxy-tmp.txt"
        tmp.write_text("\n".join(prox) + "\n")
        pool_path = tmp
    run_farm(args.count, args.workers, args.model, args.backoff,
             not args.skip_chat,  # --skip-chat = jangan chat
             bool(args.tg_token or TG_BOT_TOKEN) and bool(args.tg_chatid or TG_CHAT_ID),
             pool_path)


def cmd_sync(args): action_sync() if HAS_TUI else print("(butuh rich)")
def cmd_list(args): action_list() if HAS_TUI else print("(butuh rich)")
def cmd_export(args): action_export(all_time=args.all, out=Path(args.out) if args.out else None)
def cmd_check(args): action_check(args.token) if HAS_TUI else print("(butuh rich)")
def cmd_proxy(args): validate_pool(max_check=args.limit)


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="dahl_farm",
        description="Dahl Farm — interactive CLI for dahl.global auto-registration",
        epilog="Author: Omega4T (github.com/Omega4T)  ·  License: MIT  ·  Educational use only")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("bright", help="farm via proxy pool (non-interaktif)")
    p.add_argument("count", type=int)
    p.add_argument("--proxy", default=None, help="1 URL atau file daftar proxy")
    p.add_argument("--proxy-pool", default=None)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--backoff", type=float, default=1.5,
                   help="delay retry saat 429 (default: 1.5 dtk + jitter)")
    p.add_argument("--model", default=MODEL_DEFAULT)
    p.add_argument("--skip-chat", action="store_true", help="lewati verifikasi chat")
    p.add_argument("--tg-token", default=None)
    p.add_argument("--tg-chatid", default=None)
    p.set_defaults(fn=cmd_brightfarm)

    p = sub.add_parser("sync", help="merge creds -> keys.txt"); p.set_defaults(fn=cmd_sync)
    p = sub.add_parser("list", help="list akun terfarm"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("proxy", help="validasi proxy pool")
    p.add_argument("--limit", type=int, default=100); p.set_defaults(fn=cmd_proxy)
    p = sub.add_parser("export", help="export keys")
    p.add_argument("--all", action="store_true"); p.add_argument("--since", default=None)
    p.add_argument("--out", default=None); p.set_defaults(fn=cmd_export)
    p = sub.add_parser("check", help="verify a key")
    p.add_argument("token", nargs="?"); p.add_argument("--model", default=MODEL_DEFAULT)
    p.set_defaults(fn=cmd_check)

    # shortcut: `dahl_farm 50` = farm 50 akun
    argv = sys.argv[1:]
    if argv and argv[0].isdigit():
        argv = ["bright"] + argv
    a = ap.parse_args(argv)

    if not getattr(a, "cmd", None):
        if not HAS_TUI:
            sys.exit("Butuh 'rich' + 'questionary' untuk mode interaktif.\n"
                     "  pip install rich questionary")
        try:
            menu()
        except KeyboardInterrupt:
            console.print("\n[dim2]Keluar.[/]\n")
        return

    print_credit()
    if a.cmd == "bright" and a.workers is None:
        a.workers = safe_workers()
    a.fn(a)


if __name__ == "__main__":
    main()
