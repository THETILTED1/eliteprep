"""Rewrite a filed solution into something a C++ parser will accept.

A filed solution is not a translation unit. It holds one `class Solution` per
approach — all with the same name, because that is the name the judge expects —
and the helper types the judge supplies (`ListNode`, `TreeNode`, the several
unrelated shapes of `Node`, `Interval`) sit in it as comments, exactly as
LeetCode ships them. Parsed as it stands, the second approach is a redefinition
of the first and every helper type is undeclared. Clang does not recover from
either: it drops the redefined class outright, so an editor backed by it goes
blind from the second `@solution` onwards.

So the text is rewritten on the way to the parser, and the file is left alone —
it stays the paste-ready thing it is meant to be.

Two edits, and a rule that governs both. Each `@solution`/`@end` pair becomes a
namespace, which makes the approaches distinct without renaming anything. Each
commented-out helper definition becomes real code. The rule is that every edit
lands on a line that carries no code — a marker comment, or the decoration down
the left edge of a block comment — and replaces exactly as many characters as it
removes.

Line count and the column of every character of real code therefore survive. A
position in the rewritten text is the same position in the file on disk, in both
directions, so nothing has to be mapped and nothing can drift out of step.
"""

from __future__ import annotations

import re
import sys

SOLUTION = re.compile(r"^\s*//\s*@solution\b")
END = re.compile(r"^\s*//\s*@end\s*$")
# The decoration down the left edge of a block comment: an opening /* or /**,
# a closing */, or the * that continues one.
DECORATION = re.compile(r"^\s*(?:/\*+|\*+/|\*)")
DEFINITION = re.compile(r"^\s*(?:class|struct)\s+\w+\b")
OPENS = re.compile(r"^\s*(/\*)")
CLOSES = re.compile(r"\*/")


def undecorate(line: str) -> str:
    """The line with its comment decoration blanked out, same length.

    ``  * int val;`` becomes ``    int val;``. Nothing shifts, so a column in
    the result is the same column in the original.
    """
    m = DECORATION.match(line)
    if not m:
        return line
    return " " * m.end() + line[m.end():]


def _comment_spans(lines: list[str]) -> list[tuple[int, int]]:
    """Block comments that start a line, as [start, end) line ranges."""
    spans, open_at = [], None
    for i, line in enumerate(lines):
        if open_at is None:
            if OPENS.match(line):
                open_at = i
                if CLOSES.search(line, OPENS.match(line).end()):
                    spans.append((i, i + 1))
                    open_at = None
        elif CLOSES.search(line):
            spans.append((open_at, i + 1))
            open_at = None
    return spans


def _definition_span(body: list[str]) -> tuple[int, int] | None:
    """The class or struct definition inside one comment, as a line range.

    Found by brace depth rather than by looking for the closing line, so a
    definition with methods in it is measured correctly.
    """
    for i, line in enumerate(body):
        if not DEFINITION.match(line):
            continue
        depth = 0
        for j in range(i, len(body)):
            depth += body[j].count("{") - body[j].count("}")
            if depth == 0 and "{" in "".join(body[i:j + 1]):
                return i, j + 1
        return None  # unbalanced: leave the comment alone
    return None


def _uncomment(lines: list[str], span: tuple[int, int]) -> None:
    """Turn a commented-out helper definition into code, in place.

    Only the definition itself is uncommented. Everything else in the comment —
    the `Definition for a Node.` line above it, the delimiters — is blanked,
    because it is prose and would not parse. A blank line is valid anywhere and
    costs no line number.
    """
    start, end = span
    body = [undecorate(line) for line in lines[start:end]]
    found = _definition_span(body)
    if found is None:
        return
    first, last = found
    for i in range(start, end):
        k = i - start
        lines[i] = body[k] if first <= k < last else ""
    # LeetCode's own text for the premium Interval omits the semicolon that
    # ends the class. Adding one at the end of a line shifts nothing.
    closing = start + last - 1
    if not lines[closing].rstrip().endswith(";"):
        lines[closing] = lines[closing].rstrip() + ";"


def stitch(text: str) -> str:
    """The text as a parser should see it. Same lines, same columns."""
    lines = text.split("\n")

    opens = [i for i, line in enumerate(lines) if SOLUTION.match(line)]
    ends = [i for i, line in enumerate(lines) if END.match(line)]
    # A draft mid-edit can be unbalanced. Wrapping it would leave a namespace
    # open and bury the real diagnostics under a cascade, so leave it be: the
    # file behaves as it would with no rewrite at all, which is what the author
    # is already looking at.
    if len(opens) == len(ends) and all(o < e for o, e in zip(opens, ends)):
        for n, (open_at, end_at) in enumerate(zip(opens, ends), 1):
            lines[open_at] = f"namespace __tp{n} {{"
            lines[end_at] = "}"

    for span in _comment_spans(lines):
        _uncomment(lines, span)

    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python3 tools/stitch.py <file.cpp>", file=sys.stderr)
        print("prints the file as clangd sees it", file=sys.stderr)
        return 2
    with open(argv[0], encoding="utf-8") as f:
        sys.stdout.write(stitch(f.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
