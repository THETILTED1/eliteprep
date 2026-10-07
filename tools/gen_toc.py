#!/usr/bin/env python3
"""Regenerate the generated indexes, from the solved files alone.

Each section keeps its own, beside its problems:

    neetcode/TOC.md        every solved problem, broken down by topic
    neetcode/STAR.md       the starred subset, same breakdown
    neetcode/SOLUTIONS.md  where more than one approach was kept, side by side
    neetcode/OPTIMAL.md    what is not optimal, by the axis it falls short on
    contests/CONTESTS.md   a row per contest, the standalone problems, and what
                           is still owed

Two cross both sections, and so sit at the root:

    ISSUES.md              anything that did not fully process
    search.md              `make search`, scratch and gitignored

Links are written relative to the page that holds them, so each section's pages
work wherever the section is being read from.

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
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import manifest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NEETCODE_SRC = ROOT / "neetcode"   # the eighteen topic directories, and their indexes
CONTEST_SRC = ROOT / "contests"    # a directory per contest, misc/, and their index
TOC = NEETCODE_SRC / "TOC.md"
STAR = NEETCODE_SRC / "STAR.md"
SOLUTIONS = NEETCODE_SRC / "SOLUTIONS.md"
OPTIMAL = NEETCODE_SRC / "OPTIMAL.md"
CONTESTS = CONTEST_SRC / "CONTESTS.md"
ISSUES = ROOT / "ISSUES.md"
SEARCH = ROOT / "search.md"   # scratch output of `make search`, gitignored

TOPIC_DIR = re.compile(r"^\d\d-[a-z0-9-]+$")
MISC = "misc"   # contests/misc/: problems solved on their own, not in a contest
CONTEST_DIR = re.compile(r"^(weekly|biweekly)-(\d+)$|^misc$")
FILENAME = re.compile(r"^(\d{4})-([a-z0-9-]+)\.(cpp|cc)$")
TAG = re.compile(r"^@(\w+)\s*(.*)$")
COMMENT = re.compile(r"^\s*//\s?(.*)$")

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"//[^\n]*")
# A function body with something in it. LeetCode's starter leaves every one
# empty, so this is what tells a solution from the stub `make contest` wrote.
FILLED_BODY = re.compile(r"\)\s*(?:const\s*)?(?:noexcept\s*)?(?:override\s*)?\{\s*[^\s}]")

DIFFICULTIES = ("Easy", "Medium", "Hard")
RANK = {d: i for i, d in enumerate(DIFFICULTIES)}
SOURCE_EXT = {".cpp", ".cc"}
NOT_PROBLEMS = {"template.cpp", "input.cpp"}

LABEL = re.compile(r"\s*(time|space)\b", re.I)
AXIS_WORD = re.compile(r"(time|space|style)\b", re.I)


def read_bound(text: str, pos: int) -> tuple[str, int]:
    r"""Read a balanced `O(...)` at pos. Returns ('', pos) if there is none.

    Parenthesis counting rather than a regex, because a bound may nest:
    O(log (min(M, N))) is one bound, and `O\([^)]*\)` stops at the first
    close paren and mangles it.
    """
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if text[pos:pos + 2].lower() != "o(":
        return "", pos
    depth = 0
    for i in range(pos + 1, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[pos:i + 1], i + 1
    return "", pos  # unbalanced; treated as absent

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
    while pos < len(rest):
        while pos < len(rest) and rest[pos].isspace():
            pos += 1
        if pos >= len(rest):
            break
        m = AXIS_WORD.match(rest, pos)
        if not m:
            return Optimal(error=f"did not understand {rest[pos:].strip()!r} — "
                                 f"expected one of {', '.join(AXES)}")
        axis = m.group(1).lower()
        bound, pos = read_bound(rest, m.end())  # balanced, so O(log (min(M, N)))
        if axis == "style" and bound:           # survives intact
            return Optimal(error=f"'style' takes no bound, found {bound!r}")
        if axis != "style" and not bound:
            return Optimal(error=f"'{axis}' needs the bound that beats it, "
                                 f"e.g. '{axis} O(N)'")
        if axis in [a for a, _ in gaps]:
            return Optimal(error=f"'{axis}' named twice")
        gaps.append((axis, bound))

    if not gaps:
        return Optimal(error=f"names no axis — expected one of {', '.join(AXES)}")
    return Optimal(False, gaps)


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# @verdict subs 1 pass
# @verdict subs 3 pass
# @verdict subs 1 fail
# @verdict subs 0 fail
#
# Whether you solved it yourself, in LeetCode's own terms: in the window for a
# contest, unaided for a standalone problem. `subs` counts every submission, the
# accepted one included, so `subs 3 pass` is two wrong answers and then the
# right one. No clock: the count is what is remembered afterwards, and a field
# nobody notes down at the time is one that gets made up later.
#
# A fail stays a fail. Every miss gets studied and solved, and a solution in a
# file marked fail is that upsolve — the verdict keeps saying what happened on
# the day, and the code says it has been dealt with since.
VERDICT_FORMS = "subs 1 pass | subs 3 pass | subs 1 fail | subs 0 fail"

# @contest biweekly-190 Q1 2026-10-05 — written by `make contest`, never typed
# @contest misc                      — written by `make misc`
CONTEST_LINE = re.compile(r"^((?:weekly|biweekly)-\d+)\s+Q(\d+)\s+(\d{4}-\d\d-\d\d)$")


@dataclass
class Verdict:
    """A parsed @verdict value. `error` non-empty means it did not parse."""

    subs: int = 0
    passed: bool = False
    error: str = ""

    @property
    def wrong(self) -> int:
        return self.subs - 1 if self.passed else self.subs

    def __str__(self) -> str:
        return f"subs {self.subs} " + ("pass" if self.passed else "fail")


def parse_verdict(value: str) -> Verdict:
    """'subs 3 pass' -> Verdict(3, passed=True)."""
    words = value.split()
    if not words:
        return Verdict(error="is empty — say how it went, e.g. "
                             "'subs 1 pass' or 'subs 0 fail'")
    if len(words) < 3 or words[0].lower() != "subs" or not words[1].isdigit():
        return Verdict(error="must read 'subs N pass' or 'subs N fail', "
                             f"not {value.strip()!r}")
    subs, outcome, rest = int(words[1]), words[2].lower(), words[3:]

    if outcome not in ("pass", "fail"):
        return Verdict(error=f"expected 'pass' or 'fail' after the count, "
                             f"not {words[2]!r}")
    if rest:
        return Verdict(error=f"'{outcome}' takes nothing after it, found "
                             f"{' '.join(rest)!r} — a solution written after a "
                             "fail is the upsolve, with nothing to add here")
    if outcome == "pass" and subs < 1:
        return Verdict(error="a pass is at least one submission — the accepted one")
    return Verdict(subs, passed=outcome == "pass")


def has_solution(text: str) -> bool:
    """Has any method been written, or is it still LeetCode's empty starter?"""
    return bool(FILLED_BODY.search(LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))))


def contest_name(contest: str) -> str:
    """biweekly-190 -> Biweekly 190."""
    if contest == MISC:
        return "Misc"
    kind, n = CONTEST_DIR.match(contest).groups()
    return f"{kind.title()} {n}"


def contest_url(contest: str) -> str:
    kind, n = CONTEST_DIR.match(contest).groups()
    return f"https://leetcode.com/contest/{kind}-contest-{n}/"


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
        """From a page in neetcode/."""
        return f"{self.topic}/{self.path.name}"

    @property
    def href(self) -> str:
        """From the root, where ISSUES.md and search.md sit."""
        return f"neetcode/{self.link}"

    @property
    def name(self) -> str:
        return f"[{self.title}]({self.link})" + (" ⭐" if self.star else "")

    @property
    def where(self) -> str:
        return pretty(self.topic)

    @property
    def has_optimal(self) -> bool:
        """Is an optimal solution to this problem in the file at all?

        Any, not every. A second approach kept on purpose — the O(N log N)
        sort next to the O(N) hash set, there because it teaches something or
        trades time for space — does not put the problem back in the queue.
        Once the best answer is written down, the problem is done.
        """
        return any(s.optimal.ok for s in self.solutions)

    @property
    def optimal_mark(self) -> str:
        if not self.solutions:
            return ""
        if self.has_optimal:
            return "✓"
        return "[·](OPTIMAL.md)"  # the dot is the question; the link answers it


@dataclass
class Attempt:
    """One problem under contests/: a contest's, or a standalone one in misc/.

    Its tags are all file-level — a contest file keeps one solution, so its
    @solution is a tag like the rest rather than a block with an @end.
    """

    id: int
    slug: str
    title: str
    difficulty: str
    contest: str             # the directory: weekly-470, biweekly-190, misc
    path: Path
    q: int | None = None     # position in the contest, from @contest
    date: str = ""           # the day it was sat, from @contest
    verdict: Verdict | None = None
    solution: bool = False   # anything written yet, or still the starter
    complexity: str = ""
    star: bool = False
    patterns: list[str] = field(default_factory=list)

    @property
    def handle(self) -> str:
        return f"{self.id:04d}-{self.slug}"

    @property
    def link(self) -> str:
        """From a page in contests/."""
        return f"{self.contest}/{self.path.name}"

    @property
    def href(self) -> str:
        """From the root, where ISSUES.md and search.md sit."""
        return f"contests/{self.link}"

    @property
    def upsolved(self) -> bool:
        return bool(self.verdict and not self.verdict.error
                    and not self.verdict.passed and self.solution)

    @property
    def owed(self) -> bool:
        return bool(self.verdict and not self.verdict.error
                    and not self.verdict.passed and not self.solution)

    @property
    def name(self) -> str:
        return f"[{self.title}]({self.link})" + (" ⭐" if self.star else "")

    @property
    def where(self) -> str:
        return contest_name(self.contest) + (f" Q{self.q}" if self.q else "")

    @property
    def result(self) -> str:
        """What LeetCode's ranking would print in this problem's cell."""
        v = self.verdict
        if v is None or v.error:
            return "?"
        if v.passed:
            return "✓" + (f" ({v.wrong})" if v.wrong else "")
        return "↻" if self.solution else "✗"

    @property
    def cell(self) -> str:
        tip = f"{self.title} · {self.difficulty}".replace('"', "'")
        return f'[{self.result}]({self.link} "{tip}")' + (" ⭐" if self.star else "")


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

    for d in sorted(NEETCODE_SRC.iterdir()) if NEETCODE_SRC.is_dir() else []:
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
        if (len(rel.parts) == 3 and rel.parts[0] == "neetcode"
                and TOPIC_DIR.match(rel.parts[1])):
            continue
        if (len(rel.parts) == 3 and rel.parts[0] == "contests"
                and CONTEST_DIR.match(rel.parts[1])):
            continue  # collect_contests() has its own say about these
        warnings.append(f"{rel} is in neither neetcode/<topic>/ nor contests/<contest>/, "
                        "so it is indexed nowhere")

    for e in entries:
        for ref in e.related:
            try:
                manifest.resolve_ref(ref)
            except manifest.Unresolved as err:
                warnings.append(f"{e.handle}: @related {err}")
    return entries, warnings


def contest_tags(lines: list[str]) -> dict[str, list[tuple[int, str]]]:
    """Every tag in a contest file, by name, with the line each sits on."""
    tags: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for i, raw in enumerate(lines):
        m = COMMENT.match(raw)
        tag = TAG.match(m.group(1).strip()) if m else None
        if tag:
            tags[tag.group(1)].append((i, tag.group(2).strip()))
    return tags


def collect_contests() -> tuple[list[Attempt], list[str]]:
    """Every contest problem, read as leniently as the topic files are.

    A draft still being filled in is indexed with whatever it has — a `?` in
    its cell — rather than dropped. Whether it is *valid* is `make sync`'s
    question, and the answer goes to ISSUES.md.
    """
    attempts: list[Attempt] = []
    warnings: list[str] = []

    for d in sorted(CONTEST_SRC.iterdir()) if CONTEST_SRC.is_dir() else []:
        if not d.is_dir():
            continue
        if not CONTEST_DIR.match(d.name):
            warnings.append(f"contests/{d.name} is not named weekly-N, biweekly-N "
                            "or misc, so it is indexed nowhere")
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            rel = f.relative_to(ROOT)
            m = FILENAME.match(f.name)
            if not m:
                warnings.append(f"unparseable filename: {rel}")
                continue
            try:
                p = manifest.resolve(m.group(2))
            except manifest.Unresolved:
                warnings.append(f"unknown problem: {rel}")
                continue
            if p["id"] != int(m.group(1)):
                warnings.append(f"{rel}: slug is problem {p['id']}, not {m.group(1)}")

            text = f.read_text(encoding="utf-8")
            tags = contest_tags(text.splitlines())
            a = Attempt(int(m.group(1)), m.group(2), p["title"], p["difficulty"],
                        d.name, f, solution=has_solution(text))
            placed = [v for _, v in tags.get("contest", [])]
            line = CONTEST_LINE.match(placed[0]) if len(placed) == 1 else None
            if d.name == MISC:
                pass  # nothing to place it by; sync checks it reads `misc`
            elif line and line.group(1) == d.name:
                a.q, a.date = int(line.group(2)), line.group(3)
            else:
                warnings.append(f"{rel} has no usable @contest line, so it has no "
                                "column in CONTESTS.md")
            if len(tags.get("verdict", [])) == 1:
                a.verdict = parse_verdict(tags["verdict"][0][1])
            a.complexity = " ".join(v for _, v in tags.get("solution", []))
            a.star = any(v.lower() == "yes" for _, v in tags.get("star", []))
            a.patterns = split_patterns([v for _, v in tags.get("patterns", [])])
            attempts.append(a)
    return attempts, warnings


def pretty(topic: str) -> str:
    """NeetCode's own display name, so dp-1d reads as 1-D Dynamic Programming."""
    slug = topic.split("-", 1)[1]
    for display, s in manifest.TOPIC_SLUG.items():
        if s == slug:
            return display
    return slug.replace("-", " ").title()


GENERATED = "<!-- Generated by tools/gen_toc.py. Do not edit by hand. -->"
LEGEND = ("**Opt** · ✓ an optimal solution is here · "
          "[·](OPTIMAL.md) not one yet")


def relative(target: Path, page: Path) -> str:
    """A link to target, as written on page."""
    return Path(os.path.relpath(target, page.parent)).as_posix()


def nav(current: Path) -> str:
    pages = [(TOC, "NeetCode"), (STAR, "Starred"), (SOLUTIONS, "Solutions"),
             (OPTIMAL, "Optimal"), (CONTESTS, "Contests"), (ISSUES, "Issues")]
    return " · ".join(
        label if page == current else f"[{label}]({relative(page, current)})"
        for page, label in pages
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
    out += [" · ".join(bits), "", nav(TOC), "", LEGEND, ""]
    topic_tables(entries, out)
    return "\n".join(out)


def emit_star(entries: list[Entry]) -> str:
    starred = [e for e in entries if e.star]
    out = ["# Starred", "", GENERATED, ""]
    if not starred:
        return "\n".join(out + [nav(STAR), "", "Nothing starred yet.", ""])
    out += [f"**{plural(len(starred), 'problem')}** worth coming back to.",
            "", nav(STAR), "", LEGEND, ""]
    topic_tables(starred, out, star=False)
    return "\n".join(out)


def split_complexity(text: str) -> tuple[str, str]:
    """'O(N) time O(1) space' -> ('O(N)', 'O(1)'); anything else passes through."""
    found: dict[str, str] = {}
    pos = 0
    while pos < len(text):
        bound, after = read_bound(text, pos)
        if not bound:
            pos += 1
            continue
        label = LABEL.match(text, after)
        if label:
            found.setdefault(label.group(1).lower(), bound)
        pos = after
    if "time" in found and "space" in found:
        return found["time"], found["space"]
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


def emit_catalogue(entries: list[Entry], attempts: list[Attempt]) -> tuple[str, int]:
    """Every pattern in use, commonest first — what `make search` has to search.

    Written when no PATTERN is given, because the useful answer to "search for
    what?" is the vocabulary itself. It also shows the vocabulary drifting:
    `two pointers` and `two-pointers` sit next to each other here, where in a
    filtered result you would never see both. Contest problems share the one
    vocabulary, so they are counted beside the topics rather than apart.
    """
    by_pattern: dict[str, list[Entry]] = defaultdict(list)
    for e in entries:
        for s in e.solutions:
            for p in s.patterns:
                if e not in by_pattern[p]:
                    by_pattern[p].append(e)
    in_contests: dict[str, list[Attempt]] = defaultdict(list)
    for a in attempts:
        for p in a.patterns:
            if a not in in_contests[p]:
                in_contests[p].append(a)

    out = ["# Patterns", "", GENERATED, "", nav(SEARCH), ""]
    patterns = set(by_pattern) | set(in_contests)
    if not patterns:
        return "\n".join(out + ["No solution carries a `@patterns` tag yet.", ""]), 0

    total = sum(len(s.patterns) > 0 for e in entries for s in e.solutions)
    tagged = sum(len(a.patterns) > 0 for a in attempts)
    out += [f"**{plural(len(patterns), 'pattern')}** across "
            f"{plural(total, 'solution')}"
            + (f" and {plural(tagged, 'contest problem')}" if tagged else "")
            + '. Narrow with `make search PATTERN="hashing"` — matching is by '
            "substring, so `sort` finds `sorting`, and terms are comma-separated.",
            ""]
    if in_contests:
        out += ["| Pattern | Problems | Topics | Contests |", "|---|---|---|---|"]
    else:
        out += ["| Pattern | Problems | |", "|---|---|---|"]

    def easiest(xs: list) -> list:
        return sorted(xs, key=lambda x: (RANK.get(x.difficulty, 9), x.id))

    count = lambda k: len(by_pattern.get(k, [])) + len(in_contests.get(k, []))
    for pat in sorted(patterns, key=lambda k: (-count(k), k)):
        links = ", ".join(f"[{e.title}]({e.href})" for e in easiest(by_pattern[pat]))
        if in_contests:
            more = ", ".join(f"[{a.title}]({a.href})" for a in easiest(in_contests[pat]))
            out.append(f"| `{pat}` | {count(pat)} | {links} | {more} |")
        else:
            out.append(f"| `{pat}` | {count(pat)} | {links} |")
    out.append("")
    return "\n".join(out), len(patterns)


def emit_search(entries: list[Entry], attempts: list[Attempt],
                query: str) -> tuple[str, int]:
    """Every solution whose @patterns match, easiest first; contests below."""
    terms = [x.strip().lower() for x in query.split(",") if x.strip()]
    if not terms:
        return emit_catalogue(entries, attempts)

    def matching(patterns: list[str]) -> list[str]:
        return [p for p in patterns if any(term in p.lower() for term in terms)]

    def bold(patterns: list[str], matched: list[str]) -> str:
        return ", ".join(f"**{p}**" if p in matched else p for p in patterns)

    hits: list[tuple[Entry, Solution, list[str]]] = []
    for e in entries:
        for s in e.solutions:
            if matched := matching(s.patterns):
                hits.append((e, s, matched))
    hits.sort(key=lambda h: (RANK.get(h[0].difficulty, 9), h[0].id))
    contest_hits = [(a, m) for a in attempts if (m := matching(a.patterns))]
    contest_hits.sort(key=lambda h: (RANK.get(h[0].difficulty, 9), h[0].id))

    out = [f"# Pattern: {query}", "", GENERATED, ""]
    if not hits and not contest_hits:
        known = sorted({p for e in entries for s in e.solutions for p in s.patterns}
                       | {p for a in attempts for p in a.patterns})
        out += [f"Nothing matches `{query}`.", "",
                "Patterns in use: " + (", ".join(f"`{p}`" for p in known) or "none"), ""]
        return "\n".join(out), 0

    found = [plural(len(hits), 'solution') + " across "
             + plural(len({e.handle for e, _, _ in hits}), 'problem')] if hits else []
    if contest_hits:
        found.append(plural(len(contest_hits), "contest problem"))
    out += [f"**{' and '.join(found)}**, easiest first.", "", nav(SEARCH), ""]
    if hits:
        out += ["| # | Problem | Diff | Approach | Time | Space |",
                "|---|---|---|---|---|---|"]
        for e, s, matched in hits:
            time, space = split_complexity(s.complexity)
            out.append(f"| {e.id} | [{e.title}]({e.href}) | {e.difficulty} "
                       f"| {bold(s.patterns, matched)} "
                       f"| `{time}` | {f'`{space}`' if space else ''} |")
        out.append("")
    if contest_hits:
        out += ["## Contests", "",
                "| # | Problem | Diff | Approach | Time | Space | Where |",
                "|---|---|---|---|---|---|---|"]
        for a, matched in contest_hits:
            time, space = split_complexity(a.complexity)
            out.append(f"| {a.id} | [{a.title}]({a.href}){' ⭐' if a.star else ''} "
                       f"| {a.difficulty} | {bold(a.patterns, matched)} "
                       f"| {f'`{time}`' if time else ''} "
                       f"| {f'`{space}`' if space else ''} | {a.where} |")
        out.append("")
    return "\n".join(out), len(hits) + len(contest_hits)


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

    # Only problems with no optimal solution at all. A `no` sitting beside a
    # `yes` is an alternative that was kept, not a debt that was left, and
    # SOLUTIONS.md is where approaches get compared.
    owed = [e for e in entries if e.solutions and not e.has_optimal]
    weak = [(e, s) for e in owed for s in e.solutions if not s.optimal.ok]
    kept = sum(1 for e in entries if e.has_optimal
               for s in e.solutions if not s.optimal.ok)
    aside = ("" if not kept else
             f" {plural(kept, 'other solution')} marked `no` "
             f"{'sits' if kept == 1 else 'sit'} beside an optimal one on the same "
             "problem — those were kept on purpose, and are in "
             "[SOLUTIONS.md](SOLUTIONS.md).")
    if not weak:
        clean = ("Every problem has an optimal solution." + aside) if entries \
            else "Nothing solved yet."
        return "\n".join(out + [clean, ""]), 0

    out += [f"**{plural(len(owed), 'problem')}** with no optimal solution yet. "
            "They work — this is what is still owed on them." + aside, ""]

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


def emit_contests(attempts: list[Attempt]) -> str:
    """A row per contest, newest first, then the standalone problems in misc/."""
    out = ["# Contests", "", GENERATED, ""]
    by_contest: dict[str, list[Attempt]] = defaultdict(list)
    for a in attempts:
        by_contest[a.contest].append(a)
    misc = by_contest.pop(MISC, [])
    if not attempts:
        return "\n".join(out + [nav(CONTESTS), "", "Nothing filed yet — `make contest` "
                                "lists the latest contests, and `make misc` files a "
                                "problem on its own.", ""])

    def sat(c: str) -> str:  # the day it was sat; any one file's @contest says
        return min((a.date for a in by_contest[c] if a.date), default="")

    def number(c: str) -> int:
        return int(CONTEST_DIR.match(c).group(2))

    order = sorted(by_contest, key=lambda c: (sat(c), number(c)), reverse=True)
    in_window = [a for c in order for a in by_contest[c]]
    passed = sum(1 for a in in_window if a.verdict and not a.verdict.error
                 and a.verdict.passed)
    owed = [a for a in attempts if a.owed]
    starred = [a for a in attempts if a.star]

    bits = []
    if by_contest:
        bits.append(f"**{plural(len(by_contest), 'contest')}** · {passed} of "
                    f"{plural(len(in_window), 'problem')} solved in the window")
    if misc:
        bits.append(f"**{plural(len(misc), 'standalone problem')}**")
    bits.append(f"{sum(a.upsolved for a in attempts)} upsolved")
    out += [" · ".join(bits), "", nav(CONTESTS), "",
            "✓ solved · `(2)` after that many wrong submissions · ✗ missed · "
            "↻ missed, and upsolved since · ⭐ starred", ""]

    if by_contest:
        width = max([4] + [a.q for a in in_window if a.q])
        qs = range(1, width + 1)
        out += ["| Contest | Date | " + " | ".join(f"Q{q}" for q in qs) + " | Solved |",
                "|---|---|" + "---|" * width + "---|"]
        for c in order:
            row = by_contest[c]
            cells = {a.q: a.cell for a in row if a.q}
            solved = sum(1 for a in row if a.verdict and not a.verdict.error
                         and a.verdict.passed)
            out.append(f"| [{contest_name(c)}]({contest_url(c)}) | {sat(c)} | "
                       + " | ".join(cells.get(q, "") for q in qs)
                       + f" | {solved}/{len(row)} |")
        out.append("")

    rank = {c: i for i, c in enumerate(order + [MISC])}

    def listing(rows: list[Attempt], starred: bool) -> list[str]:
        """The starred list drops the star it would print on every row, and
        gains the result, since that is half of why it was starred."""
        rows = sorted(rows, key=lambda a: (rank[a.contest], a.q or 0,
                                           RANK.get(a.difficulty, 9), a.id))
        head = ["| Where | Problem | Diff | Patterns |" + (" Result |" if starred else ""),
                "|---|---|---|---|" + ("---|" if starred else "")]
        return head + [
            f"| {a.where} | {f'[{a.title}]({a.link})' if starred else a.name} "
            f"| {a.difficulty} | {', '.join(a.patterns)} |"
            + (f" {a.result} |" if starred else "") for a in rows] + [""]

    if misc:
        out += [f"## Misc <sub>{len(misc)}</sub>", "",
                "Solved on their own rather than in a contest, easiest first.", "",
                "| # | Problem | Diff | Patterns | Result |", "|---|---|---|---|---|"]
        for a in sorted(misc, key=lambda a: (RANK.get(a.difficulty, 9), a.id)):
            out.append(f"| {a.id} | {a.name} | {a.difficulty} "
                       f"| {', '.join(a.patterns)} | {a.result} |")
        out.append("")
    if owed:
        out += [f"## Upsolve <sub>{len(owed)}</sub>", "",
                "Missed, and not solved since. Writing the solution into the file is "
                "the upsolve: its ✗ turns to ↻ and it leaves this list, while the "
                "verdict goes on saying what happened on the day.", ""]
        out += listing(owed, starred=False)
    if starred:
        out += [f"## Starred <sub>{len(starred)}</sub>", "",
                "Worth coming back to.", ""]
        out += listing(starred, starred=True)
    return "\n".join(out)


def search(query: str) -> int:
    entries, _ = collect()
    attempts, _ = collect_contests()
    text, n = emit_search(entries, attempts, query)
    SEARCH.write_text(text + "\n", encoding="utf-8", newline="\n")
    rel = f"./{SEARCH.relative_to(ROOT)}"
    if not [x for x in query.split(",") if x.strip()]:
        print(f"{plural(n, 'pattern')} -> {rel}")
    else:
        print(f"{n} match(es) -> {rel}" if n else f"no matches -> {rel}")
    return 0


def emit_issues(entries: list[Entry | Attempt], warnings: list[str],
                failures: list[str]) -> tuple[str, int]:
    """Everything that did not fully process, so it is not lost in scrollback.

    Topic files and contest files alike: both are checked against LeetCode's
    starter, and either can fail the tag rules.
    """
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
                "| # | Problem | Where |", "|---|---|---|"]
        for e in sorted(unchecked, key=lambda e: (RANK.get(e.difficulty, 9), e.id)):
            out.append(f"| {e.id} | [{e.title}]({e.href}) | {e.where} |")
        out.append("")

    if warnings:
        out += ["## Index warnings", ""] + [f"- {w}" for w in warnings] + [""]

    if pending:
        out += ["## Not yet checked", "",
                f"{plural(len(pending), 'problem')} whose signature has not been "
                "looked up yet; `make sync` resolves them.", ""]
        out += [f"- [{e.title}]({e.href}) ({e.id})" for e in
                sorted(pending, key=lambda e: e.id)] + [""]
    return "\n".join(out), count


def main(failures: list[str] | None = None) -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--search":
        return search(" ".join(sys.argv[2:]))
    entries, warnings = collect()
    attempts, more = collect_contests()
    warnings += more
    issues, n_issues = emit_issues(entries + attempts, warnings, failures or [])
    optimal, n_weak = emit_optimal(entries)
    for path, text in ((TOC, emit_toc(entries)), (STAR, emit_star(entries)),
                       (SOLUTIONS, emit_solutions(entries)),
                       (OPTIMAL, optimal), (CONTESTS, emit_contests(attempts)),
                       (ISSUES, issues)):
        path.write_text(text + "\n", encoding="utf-8", newline="\n")
    for msg in warnings:
        print(f"warning: {msg}", file=sys.stderr)
    contests = len({a.contest for a in attempts} - {MISC})
    print(f"wrote neetcode/{{TOC,STAR,SOLUTIONS,OPTIMAL}}.md, contests/CONTESTS.md, "
          f"ISSUES.md "
          f"({plural(len(entries), 'problem')} solved"
          + (f", {n_weak} not optimal" if n_weak else "")
          + (f", {plural(contests, 'contest')}" if contests else "")
          + (f", {n_issues} issue(s) -> ./ISSUES.md" if n_issues else "") + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
