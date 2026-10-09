#!/usr/bin/env python3
"""Verify that every citation quote in rules/*.yaml appears verbatim (whitespace-collapsed)
in the text file of the referenced source listed in sources/manifest.json.

Usage: uv run --with pyyaml python scripts/verify_citations.py [rules/US.yaml ...]
Exit code 1 if any failure is found.
"""
import glob, json, os, re, sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def norm(s):
    return re.sub(r"\s+", " ", s).strip()

def main(argv):
    manifest = json.load(open(os.path.join(ROOT, "sources", "manifest.json"), encoding="utf-8"))
    by_id = {}
    for e in manifest:
        if e["id"] in by_id:
            print(f"FAIL manifest: duplicate id {e['id']}")
            return 1
        by_id[e["id"]] = e
    cache, failures, n_quotes, n_facts = {}, 0, 0, 0

    def text_for(sid):
        if sid not in cache:
            e = by_id.get(sid)
            if e is None:
                cache[sid] = None
            else:
                p = os.path.join(ROOT, e["text_path"])
                cache[sid] = norm(open(p, encoding="utf-8").read()) if os.path.exists(p) else None
        return cache[sid]

    files = argv or sorted(glob.glob(os.path.join(ROOT, "rules", "*.yaml")))
    for f in files:
        doc = yaml.safe_load(open(f, encoding="utf-8"))
        seen = set()
        for fact in doc.get("facts", []):
            n_facts += 1
            fid = fact.get("id", "<no id>")
            if fid in seen:
                print(f"FAIL {f}: duplicate fact id {fid}"); failures += 1
            seen.add(fid)
            if not fact.get("citations"):
                print(f"FAIL {fid}: no citations"); failures += 1
            for c in fact.get("citations", []):
                n_quotes += 1
                sid, q = c.get("source_id"), c.get("quote", "")
                t = text_for(sid)
                if t is None:
                    print(f"FAIL {fid}: source '{sid}' missing from manifest or text file missing"); failures += 1
                elif not norm(q) or norm(q) not in t:
                    print(f"FAIL {fid}: quote not found in {sid}: {norm(q)[:140]!r}"); failures += 1
    print(f"checked {n_facts} facts, {n_quotes} quotes in {len(files)} file(s); failures: {failures}")
    return 1 if failures else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
