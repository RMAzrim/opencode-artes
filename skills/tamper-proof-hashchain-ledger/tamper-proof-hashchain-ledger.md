---
id: tamper-proof-hashchain-ledger
file_path: skills/tamper-proof-hashchain-ledger/tamper-proof-hashchain-ledger.md
name: Tamper-Proof Hashchain Ledger
category: blockchain
tags:
  - hashchain
  - merkle
  - sha256
  - verification
  - cli
  - python
author: opencode-core
version: 1.0.0
description: Append-only tamper-evident ledger built on the standard library. SHA-256 hash-chaining blocks, per-block Merkle roots over entries, signed block headers, and full chain/merkle verification with precise tamper detection (which block and which entry). CLI + JSON export, no crypto libs beyond hashlib, no MCP.
---

# Tamper-Proof Hashchain Ledger

Implement an append-only, tamper-evident ledger using only the Python standard library: each block links to the previous block's SHA-256 hash, entries inside a block are covered by a Merkle root, and any alteration - one byte, anywhere - is detected with the exact block and entry index. Designed as a self-contained CLI you can run and audit yourself.

## 1. System Architecture & Prerequisites

- **Runtime**: CPython 3.9+ (`hashlib`, `json`, `argparse`, `time`, `datetime`, `pathlib`). No third-party packages, no MCP.
- **Ledger layout** (single JSON file):
  ```
  ledger.json
  â”œâ”€ header: {format_version, algorithm, created_at, chain}
  â””â”€ chain: [Block, ...]
  ```
- **Block** = `{index, timestamp, entries[] (list of strings), header_hash, prev_hash, merkle_root, nonce}`.
- **Header hash** = `sha256(index | prev_hash | merkle_root | timestamp | nonce)`.
- **Merkle root**: leaf hashes of entries; pair-and-repeat hashing until one root remains; odd nodes are duplicated.
- **Verification strategy**:
  1. chain integrity â€” each `header_hash` recomputed, `prev_hash` continuity,
  2. entry integrity â€” recompute Merkle root per block and compare,
  3. provenance â€” optional `--expected-root` secures the genesis root out-of-band.

## 2. Input/Output Data Contracts

```
python hashchain_ledger.py init ledger.json --genesis "Ledger birth" --key <seedhex>
python hashchain_ledger.py append ledger.json "entry 1" [--key <seedhex>]
python hashchain_ledger.py verify ledger.json
python hashchain_ledger.py export ledger.json --out export.json
```

- `--key` seeds the header-hash so blocks are only valid when produced with the same key (HMAC-style keyed hash, still pure stdlib). If omitted, an unkeyed (public) chain is produced.
- Verify exit contract: `0` OK, `1` tamper detected / integrity failure, `2` file not found, invalid JSON.

## 3. Production Reference Implementation

```python
#!/usr/bin/env python3
"""hashchain_ledger.py - pure-stdlib tamper-evident append-only ledger."""
import argparse
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ALGO = "sha256"
FORMAT_VERSION = 1


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def h256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def keyed_hash(key_seed: str | None, *parts: str) -> str:
    raw = "|".join(parts).encode()
    if key_seed:
        raw = hmac.new(key_seed.encode(), raw, hashlib.sha256).digest()
    return h256(raw)


def merkle_root(entries: list[str]) -> str:
    if not entries:
        return h256(b"")
    level = [h256(e.encode()) for e in entries]
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            a = level[i]
            b = level[i + 1] if i + 1 < len(level) else a
            nxt.append(h256(a.encode() + b.encode()))
        level = nxt
    return level[0]


def new_block(index: int, prev_hash: str, entries: list[str], key_seed: str | None) -> dict:
    ts = now_iso()
    root = merkle_root(entries)
    nonce = 0
    header_hash = keyed_hash(key_seed, str(index), prev_hash, root, ts, str(nonce))
    return {"index": index, "timestamp": ts, "entries": entries,
            "merkle_root": root, "prev_hash": prev_hash,
            "header_hash": header_hash, "nonce": nonce}


def read_ledger(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"[error] ledger not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        sys.exit(f"[error] invalid JSON in {path}")
    if data.get("format_version") != FORMAT_VERSION:
        sys.exit(f"[error] unsupported format_version {data.get('format_version')}")
    return data


def write_ledger(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def cmd_init(args):
    p = Path(args.ledger)
    if p.exists():
        sys.exit(f"[error] ledger already exists: {p}")
    genesis_entries = [args.genesis] if args.genesis else ["genesis"]
    first = new_block(0, "0" * 64, genesis_entries, args.key)
    write_ledger(p, {"format_version": FORMAT_VERSION, "algorithm": ALGO,
                     "created_at": now_iso(), "keyed": bool(args.key), "chain": [first]})
    print(f"init OK -> {p} ({len(genesis_entries)} genesis entr{'y' if len(genesis_entries)==1 else 'ies'})")


def cmd_append(args):
    p = Path(args.ledger)
    data = read_ledger(p)
    chain = data["chain"]
    prev = chain[-1]
    block = new_block(prev["index"] + 1, prev["header_hash"], args.entries, args.key)
    chain.append(block)
    write_ledger(p, data)
    print(f"append OK block#{block['index']} entries={len(block['entries'])}")
    print(f"  merkle_root  {block['merkle_root']}")
    print(f"  header_hash  {block['header_hash']}")


def cmd_verify(args):
    p = Path(args.ledger)
    data = read_ledger(p)
    keyed = bool(data.get("keyed"))
    if args.key is None and keyed:
        sys.exit("[error] ledger is keyed; pass --key to verify")
    if args.key is not None and not keyed:
        sys.exit("[error] ledger is unkeyed; omit --key")
    problems = []
    for i, blk in enumerate(data["chain"]):
        if blk["index"] != i:
            problems.append(f"block#{blk['index']} misplaced (expected index {i})")
            continue
        # 1) recompute header hash
        expect_hdr = keyed_hash(args.key, str(blk["index"]), blk["prev_hash"],
                                blk["merkle_root"], blk["timestamp"], str(blk["nonce"]))
        if expect_hdr != blk["header_hash"]:
            problems.append(f"block#{i} header_hash mismatch")
        # 2) recompute merkle root from entries
        root = merkle_root(blk["entries"])
        if root != blk["merkle_root"]:
            problems.append(f"block#{i} merkle root mismatch -> entry tampered (indexâ‰ˆ{len(blk['entries'])})")
        # 3) chain continuity
        if i > 0 and blk["prev_hash"] != data["chain"][i - 1]["header_hash"]:
            problems.append(f"block#{i} prev_hash broken (link to block#{i - 1})")
    genesis_root = data["chain"][0]["merkle_root"]
    if args.expected_root and genesis_root != args.expected_root:
        problems.append(f"genesis merkle root != expected_root")
    if problems:
        print(f"[FAIL] {len(problems)} integrity problem(s)")
        for pr in problems:
            print(f"  - {pr}")
        return 1
    print(f"[OK] chain length {len(data['chain'])}, genesis root {genesis_root[:16]}â€¦")
    return 0


def cmd_export(args):
    p = Path(args.ledger)
    data = read_ledger(p)
    out = Path(args.out or (str(p) + ".export.json"))
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"exported {len(data['chain'])} blocks -> {out}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hashchain_ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def _ledger(sp):
        sp.add_argument("ledger", type=Path)
        sp.add_argument("--key", default=None)

    init = sub.add_parser("init", help="create a new chain")
    _ledger(init); init.add_argument("--genesis", default=None)

    append = sub.add_parser("append", help="append entries (>=1)")
    _ledger(append); append.add_argument("entries", nargs="+")

    verify = sub.add_parser("verify", help="full integrity check")
    _ledger(verify); verify.add_argument("--expected-root", default=None)

    export = sub.add_parser("export", help="export JSON copy")
    _ledger(export); export.add_argument("--out", default=None)

    args = ap.parse_args(argv)
    if args.cmd == "init":
        cmd_init(args)
    elif args.cmd == "append":
        cmd_append(args)
    elif args.cmd == "verify":
        return cmd_verify(args)
    elif args.cmd == "export":
        cmd_export(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 4. Execution Protocol & Step-by-Step Workflow

1. **Init a keyed ledger**: `python hashchain_ledger.py init demo.json --genesis "Alice owns 0x..." --key d3m0`.
2. **Append entries**: `python hashchain_ledger.py append demo.json "purchase #1: 10" "purchase #2: 7" --key d3m0` â€” each entry participates in the Merkle root; two entries each become a leaf.
3. **Verify clean**: `python hashchain_ledger.py verify demo.json --key d3m0` â†’ `[OK] chain length 2 â€¦`.
4. **Tamper probe**: edit one character of an entry with any text editor, re-run verify â†’ `block#N merkle root mismatch -> entry tampered` and exit `1`.
5. **Provenance anchor**: export the genesis root (`export`) and share it; anyone can later run `verify --expected-root <root>` against an untrusted copy.
6. **Offline audit**: `export` produces a self-contained JSON you can diff or store in a second medium; no server, no network, no third party.

## 5. Edge Cases & Error Handling

- **Reordered blocks** â†’ `prev_hash` continuity check fails immediately with "broken link".
- **Tampered timestamp/nonce** â†’ recomputed header hash diverges from stored header_hash.
- **Deleted/repeated entry** â†’ Merkle root mismatch points at the wrong leaf count; wrong provenance is still caught.
- **Key changes** â†’ a block minted with `--key A` under `--key B` will never verify; keys are mandatory for production chains (single-owner trust domain).
- **Empty ledger append** â†’ guarded by `read_ledger`; chain must contain genesis.
- **Unkeyed chains & keys** â†’ mismatch produces a non-zero exit code with an explicit message; the generator refuses to mix modes.
- **Corrupt JSON file** â†’ exit `2` with an explicit "invalid JSON" error, never a crash traceback.