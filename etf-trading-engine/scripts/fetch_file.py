#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_file.py — Fetch arbitrary files from a repo (by path or glob) and mirror them into outputs/mirror.
"""
import os, sys, argparse, json, fnmatch, requests

def get_tree(owner: str, repo: str, ref: str, token: str|None):
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"
    headers = {"User-Agent": "file-fetcher/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=60)
    r.raise_for_status()
    return r.json().get("tree", [])

def raw_url(owner: str, repo: str, ref: str, path: str):
    ref_part = f"refs/heads/{ref}" if len(ref) < 40 else ref
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{ref_part}/{path}"

def fetch(url: str, token: str|None):
    headers = {"User-Agent": "file-fetcher/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(url, headers=headers, timeout=60)
    return r.status_code, r.content

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="antoniosanso/etf-trading-suite")
    ap.add_argument("--ref", default="main")
    ap.add_argument("--patterns", default="**/*.md,**/*.yml,**/*.yaml,**/*.csv,**/*.json,**/*.py")
    ap.add_argument("--outdir", default="outputs/mirror")
    args = ap.parse_args()

    owner, repo = args.repo.split("/", 1)
    token = os.environ.get("GITHUB_TOKEN", "").strip() or None
    tree = get_tree(owner, repo, args.ref, token)
    pats = [p.strip() for p in args.patterns.split(",") if p.strip()]

    os.makedirs(args.outdir, exist_ok=True)
    mirrored = []
    for node in tree:
        if node.get("type") != "blob":
            continue
        path = node["path"]
        if any(fnmatch.fnmatch(path, pat) for pat in pats):
            url = raw_url(owner, repo, args.ref, path)
            code, content = fetch(url, token)
            if code == 200:
                dst = os.path.join(args.outdir, path)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "wb") as f:
                    f.write(content)
                mirrored.append(path)

    with open(os.path.join(args.outdir, "_index.json"), "w", encoding="utf-8") as f:
        json.dump({"count": len(mirrored), "files": mirrored}, f, ensure_ascii=False, indent=2)
    print(f"Mirrored {len(mirrored)} files to {args.outdir}")

if __name__ == "__main__":
    main()
