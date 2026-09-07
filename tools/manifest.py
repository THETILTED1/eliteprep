#!/usr/bin/env python3
"""Fetch, cache and query the problem manifests.

Two caches, both written by running this file with no arguments:

  tools/neetcode.json  the NeetCode 250 (which contains the 150), with topics
  tools/leetcode.json  every LeetCode problem, for supplementary practice

neetcode.io is a single-page app with no API — every URL returns the same HTML
shell — but its main bundle ships the whole problem table inline, carrying both
slugs, the roadmap topic and the difficulty:

    {problem:"Contains Duplicate", pattern:"Arrays & Hashing",
     link:"contains-duplicate/", ncLink:"duplicate-integer/",
     difficulty:"Easy", code:"0217-contains-duplicate", neetcode150:!0}

`link` is the LeetCode slug, `ncLink` is NeetCode's renamed one, and `code` is
already the `NNNN-leetcode-slug` handle this repo names files with. The 250 and
the 150 share the same 18 topics, so anything in either infers a topic.

    python3 tools/manifest.py            # refresh both caches, then verify
    python3 tools/manifest.py <query>    # resolve one string
"""

from __future__ import annotations

import difflib
import functools
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

if sys.version_info < (3, 9):  # only the standard library is used, but a
    raise SystemExit(          # recent-ish one: dataclasses, pathlib, f-strings
        f"python 3.9+ required, found {sys.version.split()[0]} at {sys.executable}"
    )

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NEETCODE = HERE / "neetcode.json"
SIGNATURES = HERE / "signatures.json"
LEETCODE = HERE / "leetcode.json"

UA = {"User-Agent": "Mozilla/5.0"}
LC_LIST = "https://leetcode.com/api/problems/all/"
LEVEL = {1: "Easy", 2: "Medium", 3: "Hard"}

# NeetCode's pattern names are display strings; these are the directory slugs.
# The 01-18 prefix is not hardcoded — it comes from the order patterns first
# appear in the bundle, which is the roadmap order.
TOPIC_SLUG = {
    "Arrays & Hashing": "arrays-hashing",
    "Two Pointers": "two-pointers",
    "Sliding Window": "sliding-window",
    "Stack": "stack",
    "Binary Search": "binary-search",
    "Linked List": "linked-list",
    "Trees": "trees",
    "Heap / Priority Queue": "heap-priority-queue",
    "Backtracking": "backtracking",
    "Tries": "tries",
    "Graphs": "graphs",
    "Advanced Graphs": "advanced-graphs",
    "1-D Dynamic Programming": "dp-1d",
    "2-D Dynamic Programming": "dp-2d",
    "Greedy": "greedy",
    "Intervals": "intervals",
    "Math & Geometry": "math-geometry",
    "Bit Manipulation": "bit-manipulation",
}

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"//[^\n]*")
CLASS_DECL = re.compile(r"\bclass\s+(\w+)\s*\{")
METHOD = re.compile(r"^\s+(?:[A-Za-z_][\w:<>,\s&*]*?\s+)?(\w+)\s*\([^)]*\)\s*\{", re.M)
SNIPPET = ("query q($titleSlug:String!){question(titleSlug:$titleSlug)"
           "{codeSnippets{langSlug code}}}")

OBJECT = re.compile(r'\{problem:"(?:[^"\\]|\\.)*"[^{}]*\}')
PAIR = re.compile(r'(\w+):(?:"((?:[^"\\]|\\.)*)"|(!0|!1))')
CODE = re.compile(r"^(\d+)-[a-z0-9-]+$")  # a couple of the 250 are unpadded
REF = re.compile(r"^(\d{4})-([a-z0-9-]+)$")
LOOKS_LIKE_URL = re.compile(r"://|\bleetcode\.com|\bneetcode\.io|/problems/")


class Unresolved(Exception):
    """Raised instead of guessing. Callers must not fall back to a default."""


def normalize(text: str) -> str:
    """Reduce a title or slug to the key both share.

    Across all 4046 LeetCode problems normalize(title) == normalize(slug) with
    zero mismatches and zero collisions, so 'Capital Gain/Loss' and
    'capital-gainloss' land on the same key.
    """
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def topics() -> list[str]:
    """The 18 topic directory names, in roadmap order."""
    seen: dict[str, None] = {}
    for p in load_neetcode():
        seen.setdefault(p["topic"], None)
    return sorted(seen)


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------

def get(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def scrape_neetcode(js: str) -> list[dict]:
    rows = []
    for obj in OBJECT.findall(js):
        d = {}
        for key, string, boolean in PAIR.findall(obj):
            d[key] = string if boolean == "" else boolean == "!0"
        if d.get("neetcode250") or d.get("neetcode150"):
            rows.append(d)

    order: dict[str, int] = {}
    for r in rows:  # first appearance == roadmap order
        order.setdefault(r["pattern"], len(order) + 1)

    out = []
    for r in rows:
        m = CODE.match(r["code"])
        if not m:
            sys.exit(f"unexpected code field: {r['code']!r}")
        slug = r["link"].strip("/")  # authoritative; `code` is occasionally unpadded
        if r["pattern"] not in TOPIC_SLUG:
            sys.exit(f"unknown pattern {r['pattern']!r} — add it to TOPIC_SLUG")
        out.append(
            {
                "id": int(m.group(1)),
                "slug": slug,
                "nc_slug": r["ncLink"].strip("/") if r.get("ncLink") else "",
                "title": r["problem"],
                "difficulty": r["difficulty"],
                "topic": f"{order[r['pattern']]:02d}-{TOPIC_SLUG[r['pattern']]}",
                "nc150": bool(r.get("neetcode150")),
            }
        )
    return out


def scrape_leetcode(payload: str) -> list[dict]:
    return [
        {
            "id": p["stat"]["frontend_question_id"],
            "slug": p["stat"]["question__title_slug"],
            "title": p["stat"]["question__title"],
            "difficulty": LEVEL.get(p["difficulty"]["level"], "?"),
        }
        for p in json.loads(payload)["stat_status_pairs"]
    ]


def refresh() -> None:
    m = re.search(r'src="(main\.[0-9a-f]+\.js)"', get("https://neetcode.io/"))
    if not m:
        sys.exit("could not find main.*.js in the neetcode.io shell")
    url = f"https://neetcode.io/{m.group(1)}"

    nc = scrape_neetcode(get(url))
    NEETCODE.write_text(
        json.dumps({"generated": date.today().isoformat(), "source": url,
                    "problems": nc}, indent=1) + "\n",
        encoding="utf-8", newline="\n",
    )
    n150 = sum(1 for p in nc if p["nc150"])
    print(f"wrote {NEETCODE.relative_to(ROOT)} ({len(nc)} problems, {n150} in the 150)")

    lc = scrape_leetcode(get(LC_LIST))
    LEETCODE.write_text(
        json.dumps({"generated": date.today().isoformat(), "source": LC_LIST,
                    "problems": lc}, separators=(",", ":")) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"wrote {LEETCODE.relative_to(ROOT)} ({len(lc)} problems)")

    _keys.cache_clear()  # the caches on disk just changed

    by_slug = {p["slug"]: p for p in lc}
    bad = [p for p in nc if by_slug.get(p["slug"], {}).get("id") != p["id"]]
    for p in bad:
        print(f"  ! {p['slug']}: manifest {p['id']}, leetcode "
              f"{by_slug.get(p['slug'], {}).get('id')}", file=sys.stderr)
    print(f"{len(nc) - len(bad)}/{len(nc)} ids cross-check against LeetCode")


# --------------------------------------------------------------------------
# querying
# --------------------------------------------------------------------------

def _load(path: Path) -> list[dict]:
    if not path.exists():
        refresh()
    return json.loads(path.read_text(encoding="utf-8"))["problems"]


def load_neetcode() -> list[dict]:
    return _load(NEETCODE)


def load_leetcode() -> list[dict]:
    return _load(LEETCODE)


@functools.lru_cache(maxsize=1)
def _keys() -> dict[str, dict]:
    """Every accepted spelling of every problem -> its entry.

    Cached, because gen_toc resolves once per solved file and re-parsing the
    4046-entry LeetCode catalogue each time costs ~50 ms a call.
    """
    keys: dict[str, dict] = {}
    # One key per problem per site: its displayed title, run through the same
    # transform a query gets. Nothing else is indexed — no ids, no handles — so
    # anything that resolves does so by surviving that transform, not by having
    # been special-cased into working.
    for p in load_neetcode():
        keys[normalize(p["title"])] = {**p, "in_neetcode": True}
    for p in load_leetcode():  # NeetCode entries win — they carry a topic
        keys.setdefault(normalize(p["title"]), {**p, "in_neetcode": False, "topic": None})
    return keys


def resolve(query: str, sync: bool = False) -> dict:
    """One string in, one problem out. Raises Unresolved rather than guessing.

    The input is the problem's title as displayed on either site. Case,
    spacing, hyphens and punctuation are discarded first, so a slugified title
    (`contains-duplicate`) resolves as well as the pasted one — not because it
    is accepted as a second format, but because it survives the same transform
    onto the same key.

    Nothing is indexed but titles. A bare id, a `NNNN-slug` handle or a URL do
    not resolve; NeetCode's renamed slug does not either, since it is a
    different word rather than a differently punctuated one.

    A problem in the NeetCode 250 carries a topic; anything else has topic
    None. Both sites change — LeetCode adds problems every week, NeetCode
    revises its lists — so with sync=True a miss refreshes the caches once and
    retries before giving up.
    """
    query = query.strip()
    if not query:
        raise Unresolved("empty query")
    if LOOKS_LIKE_URL.search(query):
        raise Unresolved(
            f"{query!r} looks like a URL — enter the problem's title instead, "
            "as shown on either site (e.g. 'Contains Duplicate')"
        )

    keys = _keys()
    if normalize(query) in keys:
        return keys[normalize(query)]

    if sync:
        print(f"  {query!r} is not in the cached manifests — refreshing ...",
              file=sys.stderr)
        refresh()
        return resolve(query, sync=False)

    near = difflib.get_close_matches(normalize(query), keys, n=5, cutoff=0.7)
    hint = ""
    if near:
        hint = "\n  did you mean: " + ", ".join(
            repr(t) for t in sorted({keys[n]["title"] for n in near})
        )
    raise Unresolved(f"no LeetCode problem matches {query!r}{hint}")


def resolve_ref(text: str, sync: bool = False) -> dict:
    """Resolve a title, or a `NNNN-slug` handle this repo wrote itself.

    The handle is not a second input format. It is the canonical form insert
    stamps into @title and @related, and reading it back is a structural
    decomposition of a field we own — the slug half still goes through
    resolve() exactly like a pasted title, and the id half is checked against
    what that returns rather than trusted.
    """
    text = text.strip()
    m = REF.match(text)
    if not m:
        return resolve(text, sync=sync)
    found = resolve(m.group(2), sync=sync)
    if f"{found['id']:04d}" != m.group(1):
        raise Unresolved(
            f"{text!r} is inconsistent: {m.group(2)!r} is problem "
            f"{found['id']:04d}, not {m.group(1)}"
        )
    return found


def handle(problem: dict) -> str:
    """The canonical `NNNN-slug` form."""
    return f"{problem['id']:04d}-{problem['slug']}"


def parse_signature(code: str) -> dict:
    """The class and method names LeetCode's C++ starter declares.

    Comments are stripped first: several snippets carry a commented-out
    ListNode or TreeNode definition whose inline constructor would otherwise
    look like a method of the class under test.
    """
    code = LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", code))
    m = CLASS_DECL.search(code)
    if not m:
        raise Unresolved("no class in the LeetCode C++ snippet")

    depth, i, opened = 0, m.end() - 1, False
    while i < len(code):
        depth += (code[i] == "{") - (code[i] == "}")
        opened = opened or code[i] == "{"
        i += 1
        if opened and depth <= 0:
            break
    body = code[m.end() : i - 1]
    methods = [n for n in METHOD.findall(body)]
    return {"cls": m.group(1), "methods": sorted(set(methods))}


@functools.lru_cache(maxsize=1)
def _signature_cache() -> dict:
    if not SIGNATURES.exists():
        return {}
    return json.loads(SIGNATURES.read_text(encoding="utf-8"))


def signature_status(slug: str) -> str:
    """'checked', 'unavailable' or 'unknown'. Never fetches anything.

    'unknown' only means nothing has looked yet — insert and sync both fill
    the cache in, so it resolves on the next run.
    """
    cache = _signature_cache()
    if slug not in cache:
        return "unknown"
    return "checked" if cache[slug] else "unavailable"


def signature(slug: str) -> dict | None:
    """LeetCode's expected C++ class and methods, cached per problem.

    None when LeetCode exposes no C++ starter, in which case there is nothing
    to check a solution against. That is not rare: the seven premium problems
    in the NeetCode 150 return codeSnippets: null to anyone without a
    subscription. The None is cached like any other answer, so a premium
    problem costs one request, not one per run.
    """
    cache = (json.loads(SIGNATURES.read_text(encoding="utf-8"))
             if SIGNATURES.exists() else {})
    if slug in cache:
        return cache[slug]

    body = json.dumps({"query": SNIPPET, "variables": {"titleSlug": slug}}).encode()
    req = urllib.request.Request(
        "https://leetcode.com/graphql", data=body,
        headers={**UA, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            question = json.load(r)["data"]["question"]
    except Exception as e:
        raise Unresolved(
            f"could not fetch the LeetCode C++ signature for {slug!r} ({e}). "
            "This needs the network once per problem, then it is cached."
        ) from e
    if not question:
        raise Unresolved(f"leetcode returned no question for {slug!r}")

    snippets = question.get("codeSnippets") or []
    code = next((s["code"] for s in snippets if s["langSlug"] == "cpp"), None)
    cache[slug] = parse_signature(code) if code else None
    _signature_cache.cache_clear()
    SIGNATURES.write_text(json.dumps(cache, indent=1, sort_keys=True) + "\n",
                          encoding="utf-8", newline="\n")
    return cache[slug]


def main(argv: list[str]) -> int:
    if not argv:
        refresh()
        return 0
    status = 0
    for q in argv:
        try:
            p = resolve(q)
        except Unresolved as e:
            print(f"{q!r}: {e}", file=sys.stderr)
            status = 1
            continue
        where = p["topic"] or "not in NeetCode"
        print(f"{q!r} -> {p['id']:04d}-{p['slug']}  ({p['difficulty']}, {where})")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
