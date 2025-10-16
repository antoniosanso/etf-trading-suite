#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
index_repo.py — Build full repo index & summaries; write docs/CONTENT_INDEX.md and JSON artifacts.
"""
import os
import sys
import argparse
import json
import base64
import mimetypes
import re
from typing import List, Dict, Any

import requests

G = "https://api.github.com"


def gh_get(url: str, token: str | None) -> requests.Response:
    headers = {"User-Agent": "repo-indexer/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    return r


def build_raw_url(owner: str, repo: str, ref: str, path: str) -> str:
    # If 'ref' is not a 40-char SHA, assume it's a branch name and use refs/heads/<ref>
    ref_part = f"refs/heads/{ref}" if not re.fullmatch(r"[0-9a-f]{40}", ref) else ref
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref_part}/{path}"


def is_textual(path: str, size: int, textual_exts: set[str]) -> bool:
    ext = os.path.splitext(path.lower())[1]
    if ext in textual_exts:
        return True
    binary_exts = {
        ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".gz", ".xz",
        ".7z", ".rar", ".mp3", ".mp4", ".wav", ".ogg", ".webp", ".ico"
    }
    return ext not in binary_exts and size <= 1024 * 1024


def head_extract(text: str, max_lines: int = 30) -> str:
    lines = text.splitlines()
    return "\n".join(lines[:max_lines])


def extract_headings_md(text: str, max_items: int = 20) -> List[str]:
    heads = []
    for line in text.splitlines():
        if line.startswith("#"):
            heads.append(line.strip())
        if len(heads) >= max_items:
            break
    return heads


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="antoniosanso/etf-trading-suite")
    ap.add_argument("--ref", default="main")
    ap.add_argument("--max-bytes", type=int, default=65536)
    ap.add_argument("--summarize-exts", default=".md,.yml,.yaml,.txt,.csv,.json,.py")
    ap.add_argument("--outdir", default="outputs/index")
    ap.add_argument("--docs", default="docs/CONTENT_INDEX.md")
    args = ap.parse_args()

    token = os.environ.get("GITHUB_TOKEN", "").strip() or None
    owner, repo = args.repo.split("/", 1)

    # Fetch tree listing (recursive)
    try:
        r = gh_get(f"{G}/repos/{owner}/{repo}/git/trees/{args.ref}?recursive=1", token)
    except requests.HTTPError:
        r = gh_get(f"{G}/repos/{owner}/{repo}/git/trees/heads/{args.ref}?recursive=1", token)
    data = r.json()
    tree = data.get("tree", [])

    textual_exts = {e.strip().lower() for e in args.summarize_exts.split(",") if e.strip()}
    files_meta: List[Dict[str, Any]] = []
    summaries: Dict[str, Any] = {}

    for node in tree:
        if node.get("type") != "blob":
            continue
        path = node["path"]
        size = node.get("size", 0)
        sha = node.get("sha", "")
        raw = build_raw_url(owner, repo, args.ref, path)
        mime, _ = mimetypes.guess_type(path)
        files_meta.append({
            "path": path,
            "size": size,
            "sha": sha,
            "raw_url": raw,
            "blob_url": f"https://github.com/{owner}/{repo}/blob/{args.ref}/{path}",
            "mime": mime or "text/plain"
        })

        if is_textual(path, size, textual_exts) and size <= args.max_bytes:
            try:
                cr = gh_get(f"{G}/repos/{owner}/{repo}/contents/{path}?ref={args.ref}", token)
                cj = cr.json()
                if cj.get("encoding") == "base64" and cj.get("content"):
                    text = base64.b64decode(cj["content"]).decode("utf-8", errors="replace")
                    head = head_extract(text, max_lines=40)
                    heads = extract_headings_md(text, max_items=20) if path.lower().endswith(".md") else []
                    summaries[path] = {
                        "lines": text.count("\n") + 1,
                        "head": head,
                        "headings": heads
                    }
            except Exception:
                # best-effort
                pass

    os.makedirs(args.outdir, exist_ok=True)
    with open(os.path.join(args.outdir, "repo_index.json"), "w", encoding="utf-8") as f:
        json.dump({"repo": args.repo, "ref": args.ref, "files": files_meta}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.outdir, "summaries.json"), "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    rows = []
    rows.append(f"# Repository Content Index — {args.repo}@{args.ref}\n")
    rows.append("Questa pagina è generata automaticamente dal workflow **Content Indexer**.\n")
    rows.append("| Path | Size | SHA (short) | Link | Raw |\n|---|---:|---|---|---|\n")
    for m in files_meta:
        sha_short = m["sha"][:8]
        rows.append(f"| `{m['path']}` | {m['size']:,} | `{sha_short}` | [blob]({m['blob_url']}) | [raw]({m['raw_url']}) |")
    rows.append("\n## Estratti e Headings\n")
    for p, s in list(summaries.items())[:50]:
        rows.append(f"### `{p}`")
        if s.get("headings"):
            rows.append("\n".join(s["headings"]))
        head = s.get("head", "").strip()
        if head:
            rows.append("\n```text\n" + head[:2000] + "\n```\n")

    os.makedirs(os.path.dirname(args.docs), exist_ok=True)
    with open(args.docs, "w", encoding="utf-8") as f:
        f.write("\n".join(rows))

    print(f"Indexed {len(files_meta)} files. Wrote {args.outdir}/repo_index.json, summaries.json and {args.docs}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        sys.stderr.write(f"[ERROR] {e}\n")
        sys.exit(2)
