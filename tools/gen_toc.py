#!/usr/bin/env python3
"""Regenerate the three generated indexes, from the solved files alone.

    TOC.md        every solved problem, broken down by topic
    STAR.md       the starred subset, same breakdown
    SOLUTIONS.md  where more than one approach was kept, side by side
    OPTIMAL.md    what is not optimal, by the axis it falls short on
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
OPTIMAL = ROOT / "OPTIMAL.md"
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

# @optimal yes
# @optimal no time O(N)
# @optimal no style
# @optimal no time O(N) style
#
# `no` must name what beats it, on one or more axes. time and space carry the
# bound that does; style carries nothing, because there is no notation for
# "shorter than this". Requiring the axis is the same rule that made @optimal
# mandatory in the first place: a bare `no` records that you were unhappy
# without recording what would fix it, which is the half worth keeping.
AXES = ("time", "space", "style")
OPTIMAL_AXIS = re.compile(r"\b(time|space|style)\b\s*(O\([^)]*\))?", re.I)


@dataclass
class Optimal:
    """A parsed @optimal value. `error` non-empty means it did not parse."""

    ok: bool = True
    gaps: list[tuple[str, str]] = field(default_factory=list)
    error: str = ""

    @property
    def axes(self) -> list[str]:
        return [axis for axis, _ in self.gaps]

    def bound(self, axis: str) -> str:
        return next((b for a, b in self.gaps if a == axis), "")


def parse_optimal(value: str) -> Optimal:
    """'no time O(N) style' -> Optimal(False, [('time', 'O(N)'), ('style', '')])."""
    text = value.strip()
    if not text:
        return Optimal(error="is empty — write 'yes', or 'no' and what beats it")

    head, _, rest = text.partition(" ")
    head, rest = head.lower(), rest.strip()
    if head == "yes":
        if rest:
            return Optimal(error=f"'yes' takes nothing after it, found {rest!r}")
        return Optimal(True, [])
    if head != "no":
        return Optimal(error=f"must start with 'yes' or 'no', not {head!r}")
    if not rest:
        return Optimal(error="'no' must say what beats it, e.g. 'no time O(N)', "
                             "'no style', 'no space O(1) style'")

    gaps: list[tuple[str, str]] = []
    pos = 0
    for m in OPTIMAL_AXIS.finditer(rest):
        skipped = rest[pos:m.start()].strip()
        if skipped:
            return Optimal(error=f"did not understand {skipped!r} — expected one "
                                 f"of {', '.join(AXES)}")
        axis, bound = m.group(1).lower(), (m.group(2) or "")
        if axis == "style" and bound:
            return Optimal(error=f"'style' takes no bound, found {bound!r}")
        if axis != "style" and not bound:
            return Optimal(error=f"'{axis}' needs the bound that beats it, "
                                 f"e.g. '{axis} O(N)'")
        if axis in [a for a, _ in gaps]:
            return Optimal(error=f"'{axis}' named twice")
        gaps.append((axis, bound))
        pos = m.end()

    trailing = rest[pos:].strip()
    if trailing:
        return Optimal(error=f"did not understand {trailing!r} — expected one of "
                             f"{', '.join(AXES)}")
    if not gaps:
        return Optimal(error=f"names no axis — expected one of {', '.join(AXES)}")
    return Optimal(False, gaps)


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


@dataclass
class Solution:
    complexity: str = ""
    patterns: list[str] = field(default_factory=list)
    primary: bool = False
    optimal: Optimal = field(default_factory=Optimal)

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

    @property
    def optimal_mark(self) -> str:
        """One glyph for the whole problem: clean only if every solution is.

        A problem is not half-done because its second approach is the slow one
        you kept on purpose — but the mark is about whether anything here is
        still owed work, and a `no` anywhere means something is.
        """
        if not self.solutions:
            return ""
        return "✓" if all(s.optimal.ok for s in self.solutions) else "·"


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
                    optimal=parse_optimal(" ".join(tags.get("optimal", ["yes"]))),
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
             ("SOLUTIONS.md", "Solutions"), ("OPTIMAL.md", "Optimal"),
             ("ISSUES.md", "Issues")]
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
        out.append("| # | Problem | Diff | Opt |")
        out.append("|---|---|---|---|")
        for e in sorted(by_topic[topic], key=lambda e: (RANK.get(e.difficulty, 9), e.id)):
            name = e.name if star else f"[{e.title}]({e.link})"
            out.append(f"| {e.id} | {name} | {e.difficulty} | {e.optimal_mark} |")
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


AXIS_BLURB = {
    "time": ("Time", "A better bound exists and you know what it is."),
    "space": ("Space", "The same answer for less memory."),
    "style": ("Style", "The complexity is already optimal — what is owed here "
                       "is a clearer way of writing it."),
}


def emit_optimal(entries: list[Entry]) -> tuple[str, int]:
    """Everything marked `@optimal no`, grouped by the axis it falls short on.

    A solution that names two axes appears under both: the time debt and the
    style debt on one problem are different jobs, done on different days.
    """
    out = ["# Optimal", "", GENERATED, "", nav(OPTIMAL), ""]

    weak = [(e, s) for e in entries for s in e.solutions if not s.optimal.ok]
    total = sum(len(e.solutions) for e in entries)
    if not weak:
        clean = f"All {plural(total, 'solution')} are marked optimal." if total \
            else "Nothing solved yet."
        return "\n".join(out + [clean, ""]), 0

    out += [f"**{plural(len(weak), 'solution')}** of {total} marked "
            "`@optimal no`. They work — this is what is still owed on them.", ""]

    for axis in AXES:
        rows = [(e, s) for e, s in weak if axis in s.optimal.axes]
        if not rows:
            continue
        rows.sort(key=lambda pair: (RANK.get(pair[0].difficulty, 9), pair[0].id))
        heading, blurb = AXIS_BLURB[axis]
        out += [f"## {heading} <sub>{len(rows)}</sub>", "", blurb, ""]
        if axis == "style":
            out += ["| # | Problem | Diff | Approach | Time | Space |",
                    "|---|---|---|---|---|---|"]
        else:
            out += [f"| # | Problem | Diff | Approach | Has | Beaten by |",
                    "|---|---|---|---|---|---|"]
        for entry, sol in rows:
            time, space = split_complexity(sol.complexity)
            if axis == "style":
                out.append(f"| {entry.id} | {entry.name} | {entry.difficulty} "
                           f"| {sol.label} | `{time}` "
                           f"| {f'`{space}`' if space else ''} |")
            else:
                has = time if axis == "time" else space
                out.append(f"| {entry.id} | {entry.name} | {entry.difficulty} "
                           f"| {sol.label} | `{has}` "
                           f"| `{sol.optimal.bound(axis)}` |")
        out.append("")
    return "\n".join(out), len(weak)


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
    optimal, n_weak = emit_optimal(entries)
    for path, text in ((TOC, emit_toc(entries)), (STAR, emit_star(entries)),
                       (SOLUTIONS, emit_solutions(entries)),
                       (OPTIMAL, optimal), (ISSUES, issues)):
        path.write_text(text + "\n", encoding="utf-8", newline="\n")
    for msg in warnings:
        print(f"warning: {msg}", file=sys.stderr)
    print(f"wrote TOC.md, STAR.md, SOLUTIONS.md, OPTIMAL.md, ISSUES.md "
          f"({plural(len(entries), 'problem')} solved"
          + (f", {n_weak} not optimal" if n_weak else "")
          + (f", {n_issues} issue(s) -> ./ISSUES.md" if n_issues else "") + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
