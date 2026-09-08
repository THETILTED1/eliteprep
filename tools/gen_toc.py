#!/usr/bin/env python3
"""Regenerate the three generated indexes, from the solved files alone.

    TOC.md        every solved problem, broken down by topic
    STAR.md       the starred subset, same breakdown
    SOLUTIONS.md  what is not optimal, and where more than one approach was kept
    ISSUES.md     anything that did not fully process

TOC.md is the cover-all and carries nothing but the topic breakdown, so it
stays readable at a hundred problems. Neither it nor STAR.md lists solutions —
that comparison is the whole content of SOLUTIONS.md.

Only problems that exist as files are listed. NeetCode's own site is the better
roadmap for what is left, so none of this tries to be a checklist of the 150.

Nothing about a problem's identity is typed by hand: the id and slug come from
the filename, the title and difficulty from tools/neetcode.json. A source file
carries only what is yours:

    // 0217-contains-duplicate [Easy]   <- written by insert

    // @star yes                        <- yes or no
    // @related 0242-valid-anagram       <- comma-separated handles

    // @solution O(N log N) time O(1) space
    // @optimal no                       <- yes or no, once per solution
    // @patterns sorting                 <- comma-separated; labels this solution
    // @primary                          <- at most one per file
    //
    class Solution { ... };
    // @end

Comment blocks are grouped by blank lines. A group containing @solution
describes the class below it; @star and @related are file-level wherever they
appear. Solutions are labelled by their @patterns rather than their class name,
so every class in a file may be called Solution.

Run:  python3 tools/gen_toc.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"          # the eighteen topic directories live here
TOC = ROOT / "TOC.md"
STAR = ROOT / "STAR.md"
SOLUTIONS = ROOT / "SOLUTIONS.md"
ISSUES = ROOT / "ISSUES.md"
SEARCH = ROOT / "search.md"   # scratch output of `make search`, gitignored

TOPIC_DIR = re.compile(r"^\d\d-[a-z0-9-]+$")
FILENAME = re.compile(r"^(\d{4})-([a-z0-9-]+)\.(cpp|cc)$")
TAG = re.compile(r"^@(\w+)\s*(.*)$")
COMMENT = re.compile(r"^\s*//\s?(.*)$")

DIFFICULTIES = ("Easy", "Medium", "Hard")
RANK = {d: i for i, d in enumerate(DIFFICULTIES)}
SOURCE_EXT = {".cpp", ".cc"}
NOT_PROBLEMS = {"template.cpp", "input.cpp"}

TIME = re.compile(r"(O\([^)]*\))\s*time", re.I)
SPACE = re.compile(r"(O\([^)]*\))\s*space", re.I)


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


@dataclass
class Solution:
    complexity: str = ""
    patterns: list[str] = field(default_factory=list)
    primary: bool = False
    optimal: bool = True

    @property
    def label(self) -> str:
        return ", ".join(self.patterns) or "?"


@dataclass
class Entry:
    id: int
    slug: str
    title: str
    difficulty: str
    topic: str
    path: Path
    star: bool = False
    related: list[str] = field(default_factory=list)
    solutions: list[Solution] = field(default_factory=list)

    @property
    def handle(self) -> str:
        return f"{self.id:04d}-{self.slug}"

    @property
    def link(self) -> str:
        return f"src/{self.topic}/{self.path.name}"

    @property
    def name(self) -> str:
        return f"[{self.title}]({self.link})" + (" ⭐" if self.star else "")


def split_patterns(values: list[str]) -> list[str]:
    """Comma-separated, so a pattern can be several words: 'two pointers'."""
    out: list[str] = []
    for value in values:
        out += [x.strip() for x in value.split(",") if x.strip()]
    return out


def parse_tags(path: Path) -> tuple[bool, list[str], list[Solution]]:
    star, related, solutions = False, [], []

    def flush(group: list[str]) -> None:
        nonlocal star
        tags: dict[str, list[str]] = defaultdict(list)
        for line in group:
            m = TAG.match(line)
            if m:
                tags[m.group(1)].append(m.group(2).strip())
        for value in tags.get("star", []):
            star = value.strip().lower() == "yes"
        for value in tags.get("related", []):
            related.extend(x.strip() for x in value.split(",") if x.strip())
        if "solution" in tags:
            solutions.append(
                Solution(
                    complexity=" ".join(tags["solution"]).strip(),
                    patterns=split_patterns(tags.get("patterns", [])),
                    primary="primary" in tags,
                    optimal=all(v.strip().lower() == "yes"
                                for v in tags.get("optimal", ["yes"])),
                )
            )

    group: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        m = COMMENT.match(raw)
        if m:
            group.append(m.group(1).strip())
        else:
            flush(group)
            group = []
    flush(group)
    return star, related, solutions


def collect() -> tuple[list[Entry], list[str]]:
    entries: list[Entry] = []
    warnings: list[str] = []

    for d in sorted(SRC.iterdir()) if SRC.is_dir() else []:
        if not (d.is_dir() and TOPIC_DIR.match(d.name)):
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            m = FILENAME.match(f.name)
            if not m:
                warnings.append(f"unparseable filename: {f.relative_to(ROOT)}")
                continue
            try:
                p = manifest.resolve(m.group(2))  # the slug is the title, hyphenated
            except manifest.Unresolved:
                warnings.append(f"unknown problem: {f.relative_to(ROOT)}")
                continue

            if p["id"] != int(m.group(1)):
                warnings.append(
                    f"{f.relative_to(ROOT)}: slug is problem {p['id']}, not {m.group(1)}"
                )
            star, related, solutions = parse_tags(f)
            if not solutions:
                warnings.append(f"no @solution in {f.relative_to(ROOT)}")
            entries.append(
                Entry(int(m.group(1)), m.group(2), p["title"], p["difficulty"],
                      d.name, f, star, related, solutions)
            )

    # Every problem must live in a topic directory. A source file anywhere else
    # would be silently absent from all three indexes, so say so loudly.
    for f in ROOT.rglob("*"):
        rel = f.relative_to(ROOT)
        if (not f.is_file() or f.suffix not in SOURCE_EXT
                or f.name in NOT_PROBLEMS or rel.parts[0] in ("tools", ".git")):
            continue
        if (len(rel.parts) == 3 and rel.parts[0] == "src"
                and TOPIC_DIR.match(rel.parts[1])):
            continue
        warnings.append(f"{rel} is not in src/<topic>/, so it is indexed nowhere")

    for e in entries:
        for ref in e.related:
            try:
                manifest.resolve_ref(ref)
            except manifest.Unresolved as err:
                warnings.append(f"{e.handle}: @related {err}")
    return entries, warnings


def pretty(topic: str) -> str:
    """NeetCode's own display name, so dp-1d reads as 1-D Dynamic Programming."""
    slug = topic.split("-", 1)[1]
    for display, s in manifest.TOPIC_SLUG.items():
        if s == slug:
            return display
    return slug.replace("-", " ").title()


GENERATED = "<!-- Generated by tools/gen_toc.py. Do not edit by hand. -->"


def nav(current: Path) -> str:
    links = [("TOC.md", "Index"), ("STAR.md", "Starred"),
             ("SOLUTIONS.md", "Solutions"), ("ISSUES.md", "Issues")]
    return " · ".join(
        label if f == current.name else f"[{label}]({f})" for f, label in links
    )


def topic_tables(entries: list[Entry], out: list[str], star: bool = True) -> None:
    by_topic: dict[str, list[Entry]] = defaultdict(list)
    for e in entries:
        by_topic[e.topic].append(e)
    for topic in sorted(by_topic):
        out.append(f"## {pretty(topic)}")
        out.append("")
        out.append("| # | Problem | Diff |")
        out.append("|---|---|---|")
        for e in sorted(by_topic[topic], key=lambda e: (RANK.get(e.difficulty, 9), e.id)):
            name = e.name if star else f"[{e.title}]({e.link})"
            out.append(f"| {e.id} | {name} | {e.difficulty} |")
        out.append("")


def emit_toc(entries: list[Entry]) -> str:
    out = ["# Solved", "", GENERATED, ""]
    if not entries:
        return "\n".join(out + ["Nothing solved yet.", ""])

    counts = {d: sum(1 for e in entries if e.difficulty == d) for d in DIFFICULTIES}
    bits = [f"**{plural(len(entries), 'problem')}**",
            plural(sum(len(e.solutions) for e in entries), "solution")]
    bits += [f"{d} {n}" for d, n in counts.items() if n]
    out += [" · ".join(bits), "", nav(TOC), ""]
    topic_tables(entries, out)
    return "\n".join(out)


def emit_star(entries: list[Entry]) -> str:
    starred = [e for e in entries if e.star]
    out = ["# Starred", "", GENERATED, ""]
    if not starred:
        return "\n".join(out + [nav(STAR), "", "Nothing starred yet.", ""])
    out += [f"**{plural(len(starred), 'problem')}** worth coming back to.",
            "", nav(STAR), ""]
    topic_tables(starred, out, star=False)
    return "\n".join(out)


def split_complexity(text: str) -> tuple[str, str]:
    """'O(N) time O(1) space' -> ('O(N)', 'O(1)'); anything else passes through."""
    time, space = TIME.search(text), SPACE.search(text)
    if time and space:
        return time.group(1), space.group(1)
    return text, ""


def emit_solutions(entries: list[Entry]) -> str:
    out = ["# Solutions", "", GENERATED, "", nav(SOLUTIONS), ""]

    weak = [(e, s) for e in entries for s in e.solutions if not s.optimal]
    weak.sort(key=lambda pair: (RANK.get(pair[0].difficulty, 9), pair[0].id))
    if weak:
        out += [f"## Not optimal <sub>{len(weak)}</sub>", "",
                "Marked `@optimal no` — they work, but you know better exists. "
                "This is the queue to come back to.", "",
                "| # | Problem | Diff | Approach | Time | Space |",
                "|---|---|---|---|---|---|"]
        for entry, sol in weak:
            time, space = split_complexity(sol.complexity)
            out.append(f"| {entry.id} | {entry.name} | {entry.difficulty} "
                       f"| {sol.label} | `{time}` "
                       f"| {f'`{space}`' if space else ''} |")
        out.append("")

    multi = sorted((e for e in entries if len(e.solutions) > 1),
                   key=lambda e: (RANK.get(e.difficulty, 9), e.id))
    if not multi:
        return "\n".join(out + [nav(SOLUTIONS), "",
                                "No problem has more than one solution yet.", ""])

    out += [f"**{plural(len(multi), 'problem')}** where a second approach earned "
            "its keep. The primary one — what you would write in an interview — "
            "is in bold.", "", nav(SOLUTIONS), "",
            "| Problem | Approach | Time | Space |",
            "|---|---|---|---|"]
    for e in multi:
        for n, s in enumerate(e.solutions):
            label = f"**{s.label}**" if s.primary else s.label
            time, space = split_complexity(s.complexity)
            out.append(
                f"| {e.name if n == 0 else ''} | {label} "
                f"| `{time}` | {f'`{space}`' if space else ''} |"
            )
    out.append("")
    return "\n".join(out)


def emit_search(entries: list[Entry], query: str) -> tuple[str, int]:
    """Every solution whose @patterns match, newest question of matching last."""
    terms = [x.strip().lower() for x in query.split(",") if x.strip()]
    hits: list[tuple[Entry, Solution, list[str]]] = []
    for e in entries:
        for s in e.solutions:
            matched = [p for p in s.patterns
                       if any(term in p.lower() for term in terms)]
            if matched:
                hits.append((e, s, matched))
    hits.sort(key=lambda h: (RANK.get(h[0].difficulty, 9), h[0].id))

    out = [f"# Pattern: {query}", "", GENERATED, ""]
    if not hits:
        known = sorted({p for e in entries for s in e.solutions for p in s.patterns})
        out += [f"Nothing matches `{query}`.", "",
                "Patterns in use: " + (", ".join(f"`{p}`" for p in known) or "none"), ""]
        return "\n".join(out), 0

    out += [f"**{plural(len(hits), 'solution')}** across "
            f"{plural(len({e.handle for e, _, _ in hits}), 'problem')}, easiest first.",
            "", f"[Index](TOC.md)", "",
            "| # | Problem | Diff | Approach | Time | Space |",
            "|---|---|---|---|---|---|"]
    for e, s, matched in hits:
        label = ", ".join(f"**{p}**" if p in matched else p for p in s.patterns)
        time, space = split_complexity(s.complexity)
        out.append(f"| {e.id} | [{e.title}]({e.link}) | {e.difficulty} | {label} "
                   f"| `{time}` | {f'`{space}`' if space else ''} |")
    out.append("")
    return "\n".join(out), len(hits)


def search(query: str) -> int:
    entries, _ = collect()
    text, n = emit_search(entries, query)
    SEARCH.write_text(text + "\n", encoding="utf-8", newline="\n")
    rel = SEARCH.relative_to(ROOT)
    print(f"{n} match(es) -> ./{rel}" if n else f"no matches -> ./{rel}")
    return 0


def emit_issues(entries: list[Entry], warnings: list[str],
                failures: list[str]) -> tuple[str, int]:
    """Everything that did not fully process, so it is not lost in scrollback."""
    out = ["# Issues", "", GENERATED, "", nav(ISSUES), ""]

    unchecked = [e for e in entries
                 if manifest.signature_status(e.slug) == "unavailable"]
    pending = [e for e in entries
               if manifest.signature_status(e.slug) == "unknown"]
    count = len(unchecked) + len(failures) + len(warnings)

    if not count and not pending:
        out += ["Nothing to report.", ""]
        return "\n".join(out), 0

    if failures:
        out += ["## Not valid", "",
                "These do not pass the tag rules, so `sync` left them alone "
                "and they are indexed from whatever is currently in them.", ""]
        out += [f"- {f}" for f in failures] + [""]

    if unchecked:
        out += ["## Class and method names unverified", "",
                "LeetCode publishes no C++ starter for these — they are premium "
                "— so nothing confirms the class and methods match what the "
                "judge expects. Worth an extra look before submitting.", "",
                "| # | Problem | Topic |", "|---|---|---|"]
        for e in sorted(unchecked, key=lambda e: (RANK.get(e.difficulty, 9), e.id)):
            out.append(f"| {e.id} | [{e.title}]({e.link}) | {pretty(e.topic)} |")
        out.append("")

    if warnings:
        out += ["## Index warnings", ""] + [f"- {w}" for w in warnings] + [""]

    if pending:
        out += ["## Not yet checked", "",
                f"{plural(len(pending), 'problem')} whose signature has not been "
                "looked up yet; `make sync` resolves them.", ""]
        out += [f"- [{e.title}]({e.link}) ({e.id})" for e in
                sorted(pending, key=lambda e: e.id)] + [""]
    return "\n".join(out), count


def main(failures: list[str] | None = None) -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--search":
        return search(" ".join(sys.argv[2:]))
    entries, warnings = collect()
    issues, n_issues = emit_issues(entries, warnings, failures or [])
    for path, text in ((TOC, emit_toc(entries)), (STAR, emit_star(entries)),
                       (SOLUTIONS, emit_solutions(entries)), (ISSUES, issues)):
        path.write_text(text + "\n", encoding="utf-8", newline="\n")
    for msg in warnings:
        print(f"warning: {msg}", file=sys.stderr)
    print(f"wrote TOC.md, STAR.md, SOLUTIONS.md, ISSUES.md "
          f"({plural(len(entries), 'problem')} solved"
          + (f", {n_issues} issue(s) -> ./ISSUES.md" if n_issues else "") + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
