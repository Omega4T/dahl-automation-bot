# Dahl Farm

An interactive CLI that automates account creation on **[inference.dahl.global](https://inference.dahl.global)** through a rotating proxy pool, then allocates each account's token balance into an API key and saves the credentials locally.

**Author:** [Omega4T](https://github.com/Omega4T) · **License:** MIT

---

## Disclaimer

> ⚠️ **For educational and research purposes only.**
>
> This project is published to demonstrate automation, proxy-pool management, and CLI design patterns. It is **not** intended for abuse, spam, or violating any service's Terms of Service.
>
> Use it only against systems you own or are explicitly authorized to test, and in compliance with all applicable laws and the target service's Terms of Service. The author provides this software **as-is, without warranty of any kind**, and accepts no liability for any misuse or damage caused by it. **You are solely responsible for how you run it.**

---

## Features

- 🌾 **Automated registration** — one account per worker, fully unattended.
- 🌐 **Rotating proxy pool** — a 3-state pool (`live` / `parked` / `dead`) with correct handling of rate limits vs. dead proxies, so a single bad proxy never kills the run.
- 🧠 **RAM-aware worker sizing** — suggests a safe concurrency based on available memory (`~20 MB / worker`), avoiding OOM and swap thrash.
- 🔑 **Key collection** — sign-in → balance check → allocate → export, with an optional chat verification step.
- 🎨 **Rich terminal UI** — banner, live status panel, progress bar, and a navigable menu built with `rich` + `questionary`.
- 📨 **Optional Telegram summary** — post the farming result and keys to a Telegram chat.
- 🖥️ **Plain fallback** — works without the TUI dependencies (single-line progress output).

---

## How it works

For every account the worker performs the same flow:

```
POST /v1/auth/signup          {"username": "<random>"}      → fingerprint + api_key
POST /v1/auth/signin          {"fingerprint": <fp>}          → session cookie
GET  /v1/account                                             → token_balance
POST /v1/account/allocate     {"key_id": <id>, "amount": n}  → move balance to key
GET  /tokens/current          Authorization: Bearer <token>  → available_tokens
POST /v1/chat/completions     Authorization: Bearer <token>  → optional verify
POST /v1/auth/signout
```

- **`fingerprint` is the password.** It is the only credential that can sign in to the account — it cannot be recovered. Treat the saved files as secrets.
- Each username is generated from an adjective/noun/wordlist (`swift_otter_412`, `quiet_cedar_905`, …).
- Proxies are picked at random per account; on `429` the proxy is **parked** (cooldown, returns to the pool later), on any other error it is **marked dead** permanently.

Optional verification sends a tiny `max_tokens=4` chat request with the newly minted key to confirm the whole chain works end-to-end before saving.

---

## Requirements

- Python **3.10+** (developed on 3.12)
- `httpx`, `rich`, `questionary` (see `requirements.txt`)
- A list of HTTP/SOCKS proxies — **one proxy per line** in `proxies.txt`

> Using proxies is effectively mandatory: registration is rate-limited per IP, so a single IP will exhaust quickly.

---

## Install

```bash
git clone https://github.com/<you>/dahl-farm.git
cd dahl-farm

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Then set up your configuration:

```bash
cp .env.example .env             # optional: fill in proxy / telegram settings
cp proxies.txt.example proxies.txt
$EDITOR proxies.txt              # paste your proxy list (one per line)
```

---

## Configuration

All configuration lives in `.env` (auto-loaded by the script — no manual `export` needed).

| Variable          | Required | Description                                                                 |
| ----------------- | -------- | --------------------------------------------------------------------------- |
| `BRIGHTDATA_URL`  | no       | A single proxy URL. If set, the tool can run without a pool file.           |
| `TG_BOT_TOKEN`    | no       | Telegram bot token — enables the post-run summary.                           |
| `TG_CHAT_ID`      | no       | Target chat id for the Telegram summary.                                     |

### Proxy files

| File               | Purpose                                                           |
| ------------------ | ----------------------------------------------------------------- |
| `proxies.txt`      | Source list you paste into (one `http://user:pass@host:port` per line). |
| `proxies-live.txt` | Output of the validator — only proxies that passed a live IP check. |

Validate your pool first (recommended):

```bash
python dahl_farm.py proxy            # checks against https://api.ipify.org
```

Live proxies are written back to `proxies-live.txt`, which the farming run uses by default.

---

## Usage

### Interactive (default)

```bash
python dahl_farm.py
```

A full-screen menu with: farm new accounts, validate/refresh the proxy pool, list farmed accounts, export keys, check a key, and sync `keys.txt`.

### Non-interactive

```bash
# shortcut — farm 50 accounts
python dahl_farm.py 50

# explicit, single proxy list
python dahl_farm.py bright 50

# tune workers and model
python dahl_farm.py bright 50 --workers 10 --model MiniMaxAI/MiniMax-M2.7

# skip the per-account chat verification (faster)
python dahl_farm.py bright 50 --skip-chat
```

### Subcommands

| Command                       | Description                                         |
| ----------------------------- | --------------------------------------------------- |
| `bright <count>`              | Farm `count` accounts via the proxy pool.           |
| `proxy [--limit N]`           | Validate proxies and keep the live ones.            |
| `list`                        | Table of farmed accounts.                           |
| `export [--all] [--out FILE]` | Export API keys (today, or all-time).               |
| `sync`                        | Merge all saved creds into `keys.txt`.              |
| `check <token>`               | Verify a single API key (tokens + chat).            |

**`bright` options:** `--proxy`, `--proxy-pool`, `--workers`, `--backoff`, `--model`, `--skip-chat`, `--tg-token`, `--tg-chatid`.

### Available models

```
MiniMaxAI/MiniMax-M2.7          (recommended)
zai-org/GLM-5.3-Flash
deepseek-ai/DeepSeek-V4-Flash-0731
```

---

## Output

```
creds/<username>.txt     # full account record (username, user_id, fingerprint, api_key, key_id)
keys.txt                 # every collected API key, one per line
keys_farmed.txt          # dated export produced by the `export` command
```

`creds/<username>.txt` looks like:

```
# Dahl account credentials
# Keep this file safe: fingerprint = password, cannot be recovered.
# Sign in at: https://dahl.global

username: swift_otter_412
user_id: ...
fingerprint: ...
api_key: dahl_...
key_id: ...
farmed: 2026-10-01T18:04:00+0000
```

All of these paths are listed in `.gitignore` — **never commit them.**

---

## Project structure

```
dahl_farm.py          # single-file tool (CLI + TUI + core logic)
requirements.txt
.env.example          # config template
proxies.txt.example   # proxy list template
.gitignore
README.md
```

---

## Notes & troubleshooting

- **`ProxyPool kosong` / empty pool** — you haven't created `proxies.txt` (or `proxies-live.txt` is empty). Run `python dahl_farm.py proxy` after pasting proxies.
- **Lots of `429`s** — normal under load; the pool parks the offending proxy and rotates. Lower `--workers` or grow the pool.
- **`Butuh 'rich' + 'questionary'`** — install the dependencies (`pip install -r requirements.txt`) or use the non-interactive `bright` subcommand.
- **Missing `httpx` errors with `proxy=`** — requires `httpx >= 0.26` (pinned in `requirements.txt`).
- **Worker sizing** — the suggested value is capped and adapts to free RAM; override with `--workers` at your own risk.

---

## License

Released under the **MIT License** — see [LICENSE](LICENSE) for the full text.

## Author

**Omega4T** — [github.com/Omega4T](https://github.com/Omega4T)
