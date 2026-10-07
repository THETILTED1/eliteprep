#!/usr/bin/env python3
"""Start a contest: one draft per question, already named, titled and stubbed.

    make contest                          # the latest contests, and which are done
    make contest C=biweekly-190           # contests/biweekly-190/, a draft apiece
    make contest C=weekly-470 DATE=2026-10-04

C= is the contest as LeetCode numbers it, weekly-N or biweekly-N. Its question
list comes from LeetCode's GraphQL endpoint, which answers without logging in,
and each title then goes through the same manifest as every other problem, so a
contest file is named and stamped exactly as a filed solution would be:

    contests/biweekly-190/3xxx-minimum-bishop-moves-to-reach-target.cpp

    // @title 3xxx-minimum-bishop-moves-to-reach-target [Medium]
    // @contest biweekly-190 Q1 2026-10-05

    // @verdict
    // @star
    // @patterns

    class Solution { ... LeetCode's own C++ starter ... };

@title and @contest are written for you. The three below them are yours, and
`make sync` holds them to the same every-tag-filled rule as a topic file:

    // @verdict subs 1 pass             accepted first time
    // @verdict subs 3 pass             two wrong, then accepted
    // @verdict subs 1 fail             not solved in the window
    // @verdict subs 0 fail upsolved    not even submitted, but solved since

DATE= is the day the contest was sat, today unless given. A file that already
exists is never touched, so running it again only fills in what is missing.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_toc  # noqa: E402
import manifest  # noqa: E402

CONTEST = ("query q($slug:String!){contest(titleSlug:$slug)"
           "{title startTime questions{title titleSlug}}}")
PAST = ("query q($n:Int!){pastContests(pageNo:1,numPerPage:$n)"
        "{data{titleSlug startTime}}}")
LC_CONTEST = re.compile(r"^(weekly|biweekly)-contest-(\d+)$")

DRAFT = """\
// @title {handle} [{difficulty}]
// @contest {contest} Q{q} {sat}

// @verdict
// @star
// @patterns

{code}
"""

# LeetCode publishes a C++ starter for every contest problem. This is for the
# day it does not, so the draft is still something `make sync` can read.
NO_STARTER = "class Solution {\npublic:\n};"


class ContestError(Exception):
    pass


def questions(contest: str) -> list[dict]:
    """The contest's questions, Q1 first, as LeetCode lists them."""
    kind, n = gen_toc.CONTEST_DIR.match(contest).groups()
    slug = f"{kind}-contest-{n}"
    try:
        found = manifest.graphql(CONTEST, {"slug": slug}).get("contest")
    except Exception as e:
        raise ContestError(f"could not reach LeetCode for {slug} ({e})") from e
    if not found:
        raise ContestError(f"LeetCode has no {slug} — `make contest` lists the latest")
    if found["startTime"] > time.time():
        raise ContestError(f"{found['title']} has not happened yet")
    if not found.get("questions"):
        raise ContestError(f"LeetCode lists no questions for {found['title']}")
    return found["questions"]


def starter(slug: str) -> str:
    code = manifest.snippet(slug) or NO_STARTER
    lines = code.replace("\r\n", "\n").strip("\n").split("\n")
    return "\n".join(line.rstrip() for line in lines)


def start(contest: str, sat: str) -> int:
    folder = gen_toc.CONTEST_SRC / contest
    written = 0
    for q, question in enumerate(questions(contest), 1):
        # sync=True: a contest is usually newer than the cached catalogue, and
        # a miss refreshes it once and retries, as insert does
        problem = manifest.resolve(question["title"], sync=True)
        if problem["slug"] != question["titleSlug"]:
            raise ContestError(
                f"Q{q} {question['title']!r} resolved to {manifest.handle(problem)}, "
                f"but LeetCode's slug for it is {question['titleSlug']!r}"
            )
        dest = folder / f"{manifest.handle(problem)}.cpp"
        shown = dest.relative_to(gen_toc.ROOT)
        if dest.exists():
            print(f"  Q{q} kept     {shown}")
            continue
        text = DRAFT.format(handle=manifest.handle(problem),
                            difficulty=problem["difficulty"], contest=contest,
                            q=q, sat=sat, code=starter(problem["slug"]))
        folder.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8", newline="\n")
        print(f"  Q{q} {problem['difficulty']:<8} {shown}")
        written += 1

    if written:
        print(f"wrote {gen_toc.plural(written, 'draft')} — fill in @verdict, @star "
              "and @patterns, then: make sync")
    else:
        print(f"nothing to do — every question of {contest} is already filed")
    return 0


def latest(n: int = 12) -> int:
    """What C= can be, and which of those are already under contests/."""
    try:
        past = (manifest.graphql(PAST, {"n": n}).get("pastContests") or {}).get("data")
    except Exception as e:
        print(f"error: could not reach LeetCode ({e})", file=sys.stderr)
        return 1
    print("latest contests — start one with: make contest C=<name>")
    for c in past or []:
        m = LC_CONTEST.match(c["titleSlug"])
        if not m:
            continue
        name = f"{m.group(1)}-{m.group(2)}"
        done = "   (in contests/)" if (gen_toc.CONTEST_SRC / name).is_dir() else ""
        print(f"  {name:<14} {date.fromtimestamp(c['startTime']).isoformat()}{done}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("contest", nargs="?", help="weekly-N or biweekly-N")
    ap.add_argument("--date", help="the day it was sat, YYYY-MM-DD; today by default")
    args = ap.parse_args()

    if not args.contest:
        return latest()
    if not gen_toc.CONTEST_DIR.match(args.contest):
        print(f"error: C= takes weekly-N or biweekly-N, e.g. biweekly-190 — "
              f"not {args.contest!r}", file=sys.stderr)
        return 1
    try:
        sat = date.fromisoformat(args.date) if args.date else date.today()
    except ValueError:
        print(f"error: DATE= takes YYYY-MM-DD, not {args.date!r}", file=sys.stderr)
        return 1
    try:
        return start(args.contest, sat.isoformat())
    except (ContestError, manifest.Unresolved) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
