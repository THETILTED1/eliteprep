#!/usr/bin/env python3
"""File a drafted solution into the repository.

    make new                          # input.cpp, from template.cpp
    $EDITOR input.cpp                 # fill in @title and the rest
    make insert                       # or: make insert SRC=other.cpp

@title takes the problem's title as displayed on either site — the heading, or
the entry in the left sidebar. That is the one string both sites show you.
Insert resolves it and stamps the canonical handle back down, so what is stored
never depends on which site you were reading:

    // @title contains duplicate      ->   // @title 0217-contains-duplicate [Easy]
    // @related valid anagram, two sum ->  // @related 0242-valid-anagram, 0001-two-sum

You type titles; the file keeps handles. Reading a handle back is a structural
decomposition of a field insert wrote, not a second accepted input format —
see manifest.resolve_ref.

Every tag must be filled before a draft is accepted; the checks are listed in
validate() below and all failures are reported at once. The one exception is a
second solution block left exactly as the template wrote it, which is dropped
rather than rejected — so an unused block costs nothing.

The topic is inferred for anything in the NeetCode 250, otherwise pass TOPIC=.
Re-inserting a problem overwrites whatever was filed under that handle before.
"""

from __future__ import annotations

import argparse
import functools
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_toc  # noqa: E402
import manifest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

COMMENT = re.compile(r"^\s*//\s?(.*)$")
TAG = re.compile(r"^@(\w+)\s*(.*)$")
TRAILING_BRACKET = re.compile(r"\s*\[[^\]]*\]\s*$")
DECL = re.compile(r"^[ \t]*(?:class|struct)\s+(\w+)", re.M)
DECL_ONLY = re.compile(r"^(?:class|struct)\s+\w+\s*\{?$")
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
ACCESS = re.compile(r"^(?:public|private|protected)\s*:\s*$")


class InsertError(Exception):
    pass


def has_code(body: str) -> bool:
    """True if a body holds anything but scaffolding.

    Scaffolding is blanks, comments of either kind, access labels, a bare class
    or struct declaration and its closing brace — exactly what template.cpp
    ships. Anything else means you started writing.
    """
    for line in BLOCK_COMMENT.sub("", body).splitlines():
        line = line.strip()
        if (not line or line.startswith("//") or ACCESS.match(line)
                or DECL_ONLY.match(line) or line in ("{", "}", "};", ";")):
            continue
        return True
    return False


@dataclass
class Block:
    """One @solution ... @end region, and everything between the two."""

    start: int
    end: int  # exclusive; past the @end line
    patterns: str = ""
    complexity: str = ""
    primary: bool = False
    body: str = ""

    @property
    def classes(self) -> list[str]:
        return DECL.findall(BLOCK_COMMENT.sub("", self.body))

    @property
    def untouched(self) -> bool:
        """Left exactly as template.cpp wrote it."""
        return not self.patterns and not self.complexity and not has_code(self.body)


@dataclass
class Draft:
    lines: list[str]
    title: list[str] = field(default_factory=list)
    title_lines: list[int] = field(default_factory=list)
    star: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    related_lines: list[int] = field(default_factory=list)
    blocks: list[Block] = field(default_factory=list)
    unclosed: list[int] = field(default_factory=list)
    stray_ends: list[int] = field(default_factory=list)
    stray_tags: list[tuple[int, str]] = field(default_factory=list)


def parse(lines: list[str]) -> Draft:
    """Split a draft into its file-level tags and its @solution regions.

    A solution runs from its @solution tag to the matching @end. Everything in
    between is carried through untouched — block comments, helper structs,
    several classes — because the delimiters say where it ends rather than the
    parser guessing from the next declaration.
    """
    draft = Draft(lines=lines)
    open_at: int | None = None
    tags: dict[str, list[str]] = {}
    body_start: int | None = None

    for i, line in enumerate(lines):
        m = COMMENT.match(line)
        if not m:
            if open_at is not None and body_start is None and line.strip():
                body_start = i
            continue

        tag = TAG.match(m.group(1).strip())
        if not tag:
            continue
        name, value = tag.group(1), tag.group(2).strip()

        if name == "title":  # file-level tags are file-level wherever they sit
            draft.title_lines.append(i)
            draft.title.append(TRAILING_BRACKET.sub("", value).strip())
        elif name == "star":
            draft.star.append(value)
        elif name == "related":
            draft.related_lines.append(i)
            draft.related.extend(x.strip() for x in value.split(",") if x.strip())
        elif name == "solution":
            if open_at is not None:
                draft.unclosed.append(open_at)
            open_at, tags, body_start = i, {"solution": [value]}, None
        elif name == "end":
            if open_at is None:
                draft.stray_ends.append(i)
                continue
            body = "\n".join(lines[body_start:i]) if body_start is not None else ""
            draft.blocks.append(
                Block(open_at, i + 1,
                      ", ".join(gen_toc.split_patterns(tags.get("patterns", []))),
                      " ".join(tags["solution"]).strip(),
                      "primary" in tags,
                      body)
            )
            open_at, tags, body_start = None, {}, None
        elif open_at is not None and body_start is None:
            tags.setdefault(name, []).append(value)
        else:
            draft.stray_tags.append((i, name))

    if open_at is not None:
        draft.unclosed.append(open_at)
    return draft


def drop_untouched(lines: list[str]) -> tuple[list[str], int]:
    """Remove solution blocks left exactly as the template wrote them."""
    dead = [b for b in parse(lines).blocks if b.untouched]
    if not dead:
        return lines, 0
    cut: set[int] = set()
    for b in dead:
        cut.update(range(b.start, b.end))
        j = b.end  # swallow the blank lines the block leaves behind
        while j < len(lines) and not lines[j].strip():
            cut.add(j)
            j += 1
    return [l for i, l in enumerate(lines) if i not in cut], len(dead)


def validate(draft: Draft, sig: dict | None) -> list[str]:
    """Every reason the draft is not ready. Empty means it is."""
    bad: list[str] = []

    if len(draft.title) != 1:
        bad.append(f"expected exactly one @title line, found {len(draft.title)}")
    elif not draft.title[0] or draft.title[0] == "{{problem}}":
        bad.append("@title is still the template placeholder — put the problem's "
                   "title there, as shown on either site")
    else:
        try:
            manifest.resolve_ref(draft.title[0])
        except manifest.Unresolved as e:
            bad.append(f"@title {e}")

    if len(draft.star) != 1:
        bad.append(
            "expected exactly one @star line, found "
            f"{len(draft.star)} — use '@star yes' or '@star no'"
        )
    elif draft.star[0].lower() not in ("yes", "no"):
        bad.append(f"@star must be 'yes' or 'no', not {draft.star[0]!r}")

    if len(draft.related_lines) != 1:
        bad.append(
            f"expected exactly one @related line, found {len(draft.related_lines)}"
            " — leave it empty if there is nothing to link"
        )
    for ref in draft.related:
        try:
            manifest.resolve_ref(ref)
        except manifest.Unresolved as e:
            bad.append(f"@related {e}")

    for line in draft.unclosed:
        bad.append(f"@solution on line {line + 1} has no matching @end")
    for line in draft.stray_ends:
        bad.append(f"@end on line {line + 1} closes nothing")
    for line, name in draft.stray_tags:
        bad.append(f"@{name} on line {line + 1} is outside any @solution block")

    if not draft.blocks:
        bad.append("no @solution block — every draft needs at least one solution")
    for n, b in enumerate(draft.blocks, 1):
        if not b.patterns:
            bad.append(f"solution {n} has no @patterns")
        if not b.complexity:
            bad.append(f"solution {n} has no complexity on @solution")
        if not has_code(b.body):
            bad.append(f"solution {n} has an empty class body")

    primary = sum(b.primary for b in draft.blocks)
    if draft.blocks and primary != 1:
        bad.append(f"expected exactly one @primary, found {primary}")

    # Every solution must use LeetCode's own class and method names, so a file
    # is a drop-in paste back into the judge. This is the one thing that has to
    # be translated when a solution was written against neetcode.io, which
    # renames methods (hasDuplicate there, containsDuplicate on LeetCode).
    if sig:
        for n, b in enumerate(draft.blocks, 1):
            if sig["cls"] not in b.classes:
                found = ", ".join(b.classes) or "none"
                bad.append(
                    f"solution {n} declares no 'class " + sig["cls"] +
                    f"' — LeetCode expects one (found: {found})"
                )
            for method in sig["methods"]:
                if not re.search(rf"\b{re.escape(method)}\s*\(", b.body):
                    bad.append(f"solution {n} does not define {method}()")

    return bad


# RemoveBracesLLVM landed in clang-format 14, and an unknown key makes it
# reject the whole config rather than skip the option, so an older binary is
# useless to us and is passed over rather than tried.
CLANG_FORMAT_MIN = 14
VERSION = re.compile(r"version\s+(\d+)")

INSTALL_HINT = (
    "install one with 'pip install clang-format', or apt/brew install "
    "clang-format; VS Code's C/C++ extension also bundles a copy"
)


def _clang_format_candidates() -> list[str]:
    """Everywhere a clang-format might plausibly be, best guess first."""
    found: list[str] = []

    def add(path: object) -> None:
        if path and str(path) not in found:
            found.append(str(path))

    add(os.environ.get("CLANG_FORMAT"))  # explicit override wins
    add(shutil.which("clang-format"))

    # VS Code's C/C++ extension ships its own, which is often the only one on
    # a machine that has never installed LLVM.
    for base in (".vscode-server", ".vscode", ".vscode-insiders"):
        root = Path.home() / base / "extensions"
        if root.is_dir():
            for exe in sorted(root.glob("ms-vscode.cpptools-*/LLVM/bin/clang-format*"),
                              reverse=True):
                add(exe)

    for version in range(40, CLANG_FORMAT_MIN - 1, -1):
        add(shutil.which(f"clang-format-{version}"))

    for pattern in ("/usr/lib/llvm-*/bin/clang-format",
                    "/opt/homebrew/opt/llvm*/bin/clang-format",
                    "/usr/local/opt/llvm*/bin/clang-format",
                    "/opt/homebrew/bin/clang-format",
                    "C:/Program Files/LLVM/bin/clang-format.exe"):
        head, _, tail = pattern.partition("*")
        parent = Path(head).parent
        if parent.is_dir():
            for exe in sorted(parent.glob(Path(head).name + "*" + tail), reverse=True):
                add(exe)
    return found


@functools.lru_cache(maxsize=1)
def find_clang_format() -> tuple[str | None, str | None]:
    """Locate a clang-format new enough for this config. (path, complaint)."""
    seen: list[str] = []
    for exe in _clang_format_candidates():
        try:
            out = subprocess.run([exe, "--version"], capture_output=True,
                                 text=True, timeout=15)
        except Exception:
            continue
        m = VERSION.search(out.stdout)
        if not m:
            continue
        if int(m.group(1)) >= CLANG_FORMAT_MIN:
            return exe, None
        seen.append(f"{exe} (v{m.group(1)})")
    if seen:
        return None, (f"clang-format {CLANG_FORMAT_MIN}+ needed, found only "
                      + ", ".join(seen) + f" — {INSTALL_HINT}")
    return None, f"no clang-format found — {INSTALL_HINT}"


def clang_format(text: str, dest: Path) -> tuple[str, str | None]:
    """Run the repo's .clang-format over a file. Cosmetic, so never fatal.

    RemoveBracesLLVM drops the braces from single-statement if/for/while
    bodies, which is what keeps these solutions as short on the page as they
    are on the judge.
    """
    exe, complaint = find_clang_format()
    if exe is None:
        return text, f"{complaint} — filed unformatted"
    try:
        run = subprocess.run(
            [exe, "--style=file", f"--assume-filename={dest}"],
            input=text, capture_output=True, text=True, timeout=30, cwd=ROOT,
        )
    except Exception as e:  # hung, vanished, anything
        return text, f"clang-format did not run ({e}) — filed unformatted"
    if run.returncode != 0:
        detail = " ".join(run.stderr.strip().splitlines()[:2])
        return text, f"clang-format failed — filed unformatted: {detail}"
    return run.stdout, None


def leetcode_signature(problem: dict) -> dict | None:
    """The class and methods to check against, or None if there are none.

    Premium problems expose no C++ starter, and a network failure is not the
    draft's fault, so neither blocks a file — the check is simply skipped and
    said out loud.
    """
    try:
        sig = manifest.signature(problem["slug"])
    except manifest.Unresolved as e:
        print(f"  warning: {e}", file=sys.stderr)
        return None
    if sig is None:
        print(f"  warning: LeetCode publishes no C++ starter for "
              f"{manifest.handle(problem)} (premium) — class and method names "
              "not checked", file=sys.stderr)
    return sig


def canonicalize(lines: list[str], draft: Draft, problem: dict) -> list[str]:
    """Stamp @title and @related down to handles. You type titles; files keep
    handles, so what is stored never depends on which site you were reading."""
    lines = list(lines)
    lines[draft.title_lines[0]] = (
        f"// @title {manifest.handle(problem)} [{problem['difficulty']}]"
    )
    if draft.related_lines:
        refs = ", ".join(
            manifest.handle(manifest.resolve_ref(r)) for r in draft.related
        )
        lines[draft.related_lines[0]] = f"// @related {refs}".rstrip()
    return lines


def pick_topic(given: str | None, problem: dict) -> str:
    known = manifest.topics()
    if given:
        for d in known:
            if given in (d, d.split("-", 1)[1]):
                return d
        raise InsertError(
            f"unknown topic {given!r}\n  choose one of: "
            + ", ".join(d.split("-", 1)[1] for d in known)
        )
    if problem["topic"]:
        return problem["topic"]
    raise InsertError(
        f"{problem['title']!r} ({problem['id']}) is not in the NeetCode 250, so "
        "it has no roadmap topic.\n  Re-run with TOPIC=, e.g. TOPIC=binary-search"
    )


def insert(src: Path, topic: str | None) -> None:
    if not src.exists():
        raise InsertError(f"{src} does not exist — run 'make new' first")

    lines = src.read_text(encoding="utf-8").splitlines()
    lines, dropped = drop_untouched(lines)  # before validating, so an unused
    draft = parse(lines)                    # template block costs nothing

    if len(draft.title) != 1:
        raise InsertError(f"expected exactly one @title line, found {len(draft.title)}")
    if not draft.title[0] or draft.title[0] == "{{problem}}":
        # caught before resolving, so an untouched draft cannot trigger a refresh
        raise InsertError("@title is still the template placeholder — put the "
                          "problem's title there, as shown on either site")
    try:
        problem = manifest.resolve_ref(draft.title[0], sync=True)
    except manifest.Unresolved as e:
        raise InsertError(f"@title {e}") from e

    sig = leetcode_signature(problem)

    bad = validate(draft, sig)
    if bad:
        raise InsertError(
            f"{src} is not ready to insert:\n"
            + "\n".join("  - " + b.replace("\n", "\n  ") for b in bad)
        )

    dest_topic = pick_topic(topic, problem)
    handle = manifest.handle(problem)
    dest = gen_toc.SRC / dest_topic / f"{handle}{src.suffix}"
    replacing = dest.exists() and dest.resolve() != src.resolve()

    lines = canonicalize(lines, draft, problem)

    if dropped:
        print(f"  dropped {dropped} untouched solution block(s)")
    if replacing:
        print(f"  replacing {dest.relative_to(ROOT)}")
    text, note = clang_format("\n".join(lines) + "\n", dest)
    if note:
        print(f"  warning: {note}", file=sys.stderr)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8", newline="\n")
    if src.resolve() != dest.resolve():
        src.unlink()
    for stale in gen_toc.SRC.glob(f"*/{handle}.*"):  # e.g. a corrected TOPIC
        if stale.resolve() != dest.resolve():
            stale.unlink()
            print(f"  removed {stale.relative_to(ROOT)}")
    print(f"  {draft.title[0]!r} -> {dest.relative_to(ROOT)}  ({problem['difficulty']})")


def check_all() -> int:
    """Re-validate every filed problem, tidy it, then rebuild the indexes.

    For when a file was edited in place — a complexity corrected, a third
    solution added. A file that validates is canonicalised and clang-formatted
    where it sits; one that does not is reported and left alone. Nothing ever
    moves between topics here — that is insert's job, with TOPIC=.
    """
    failed = 0
    failures: list[str] = []
    for d in sorted(gen_toc.SRC.iterdir()) if gen_toc.SRC.is_dir() else []:
        if not (d.is_dir() and gen_toc.TOPIC_DIR.match(d.name)):
            continue
        for f in sorted(d.iterdir()):
            if not f.is_file() or not gen_toc.FILENAME.match(f.name):
                continue
            rel = f.relative_to(ROOT)
            try:
                lines = f.read_text(encoding="utf-8").splitlines()
                draft = parse(lines)
                if len(draft.title) != 1:
                    raise InsertError(
                        f"expected exactly one @title line, found {len(draft.title)}"
                    )
                problem = manifest.resolve_ref(draft.title[0])
                bad = validate(draft, leetcode_signature(problem))
            except (InsertError, manifest.Unresolved) as e:
                print(f"{rel}: {e}", file=sys.stderr)
                failures.append(f"`{rel}` — {str(e).splitlines()[0]}")
                failed += 1
                continue
            if bad:
                print(f"{rel}:", file=sys.stderr)
                for b in bad:
                    print(f"  - {b}", file=sys.stderr)
                failures.append(f"`{rel}` — " + "; ".join(
                    b.splitlines()[0] for b in bad))
                failed += 1
                continue

            text, note = clang_format(
                "\n".join(canonicalize(lines, draft, problem)) + "\n", f
            )
            if note:
                print(f"  warning: {rel}: {note}", file=sys.stderr)
            # bytes, not text: reading decodes CRLF to \n, so a comparison on
            # strings would call a CRLF file clean and never normalise it
            if text.encode("utf-8") != f.read_bytes():
                f.write_text(text, encoding="utf-8", newline="\n")
                print(f"  tidied {rel}")

    gen_toc.main(failures)
    if failed:
        print(f"{failed} file(s) need fixing", file=sys.stderr)
    return 1 if failed else 0


def start_draft(dest: Path) -> int:
    """`make new`, but in Python so it needs no shell, cp or test."""
    if dest.exists():
        print(f"error: {dest} already exists — delete it first", file=sys.stderr)
        return 1
    dest.write_text((ROOT / "template.cpp").read_text(encoding="utf-8"),
                    encoding="utf-8", newline="\n")
    print(f"wrote {dest} — fill in @title, then: make insert")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", nargs="?", default="input.cpp")
    ap.add_argument("--topic", help="one of the 18 topics; inferred within the NeetCode 250")
    ap.add_argument("--sync", action="store_true",
                    help="re-validate every filed problem and rebuild the indexes")
    ap.add_argument("--new", action="store_true",
                    help="start a draft from template.cpp")
    args = ap.parse_args()

    if args.new:
        return start_draft(Path(args.src))
    if args.sync:
        return check_all()
    try:
        insert(Path(args.src), args.topic)
    except InsertError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    gen_toc.main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
