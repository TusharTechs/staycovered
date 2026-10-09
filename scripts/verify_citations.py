#!/usr/bin/env python3
"""Verify that every citation quote in rules/*.yaml appears verbatim (whitespace-collapsed)
in the text file of the referenced source listed in sources/manifest.json.

Usage: uv run --with pyyaml python scripts/verify_citations.py [--bench] [rules/US.yaml ...]

With --bench, also checks every rubric citation in bench/questions/*.yaml: the quote must appear
verbatim (whitespace-collapsed) in the cited source's text file, and the cited source's as_of must be
<= the question's as_of (a question may only be graded against sources that existed on its date).
Also checks basic question structure (unique ids, 2-4 criteria, valid kinds/splits).
Exit code 1 if any failure is found.
"""
import datetime, glob, json, os, re, sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def norm(s):
    return re.sub(r"\s+", " ", s).strip()

def as_date(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    return datetime.date.fromisoformat(str(v))

def main(argv):
    bench = "--bench" in argv
    argv = [a for a in argv if a != "--bench"]
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
    if bench:
        failures += check_bench(by_id, text_for)
    return 1 if failures else 0

def check_bench(by_id, text_for):
    failures, n_q, n_crit, n_cites = 0, 0, 0, 0
    seen_ids = set()
    files = sorted(glob.glob(os.path.join(ROOT, "bench", "questions", "*.yaml")))
    for f in files:
        for q in yaml.safe_load(open(f, encoding="utf-8")) or []:
            n_q += 1
            qid = q.get("id", "<no id>")
            if qid in seen_ids:
                print(f"FAIL {qid}: duplicate question id"); failures += 1
            seen_ids.add(qid)
            try:
                q_asof = as_date(q.get("as_of"))
            except Exception:
                print(f"FAIL {qid}: missing or invalid as_of"); failures += 1
                continue
            if q.get("split") not in ("dev", "heldout"):
                print(f"FAIL {qid}: split must be dev|heldout"); failures += 1
            rubric = q.get("rubric") or []
            if not 2 <= len(rubric) <= 4:
                print(f"FAIL {qid}: rubric must have 2-4 criteria (has {len(rubric)})"); failures += 1
            for c in rubric:
                n_crit += 1
                cid = f"{qid}/{c.get('id', '?')}"
                if c.get("kind") not in ("must_include", "must_not_claim"):
                    print(f"FAIL {cid}: invalid kind {c.get('kind')!r}"); failures += 1
                if not c.get("citations"):
                    print(f"FAIL {cid}: no citations"); failures += 1
                for cit in c.get("citations", []):
                    n_cites += 1
                    sid, quote = cit.get("source_id"), cit.get("quote", "")
                    t = text_for(sid)
                    if t is None:
                        print(f"FAIL {cid}: source '{sid}' missing from manifest or text file missing"); failures += 1
                        continue
                    if not norm(quote) or norm(quote) not in t:
                        print(f"FAIL {cid}: quote not found in {sid}: {norm(quote)[:140]!r}"); failures += 1
                    if as_date(by_id[sid]["as_of"]) > q_asof:
                        print(f"FAIL {cid}: source {sid} (as_of {by_id[sid]['as_of']}) is later than question as_of {q_asof}"); failures += 1
    print(f"checked {n_q} questions, {n_crit} criteria, {n_cites} citations in {len(files)} file(s); failures: {failures}")
    return failures

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
