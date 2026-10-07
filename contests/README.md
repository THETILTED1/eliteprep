# Contests

LeetCode contests, a directory each, and problems met anywhere else in `misc/`.
One solution apiece: after the roadmap in [neetcode/](../neetcode/README.md),
the point is volume. The tool that serves both is described in the
[root README](../README.md).

| | |
|---|---|
| **[CONTESTS.md](CONTESTS.md)** | a row per contest, newest first, then the problems in `misc/` and what is still to upsolve |
| **[STAR.md](STAR.md)** | the starred problems, contest and standalone alike |
| **[SOLUTIONS.md](SOLUTIONS.md)** | every solution written, its approach and complexity, easiest first |

    make contest                          # the latest contests, and which are done
    make contest C=biweekly-190           # a draft per question
    $EDITOR contests/biweekly-190/*.cpp   # paste, then fill in four tags
    make sync

    make misc TITLE="last visited integers"   # one problem, into misc/

## Starting a contest

`C=` is the contest as LeetCode numbers it, `weekly-N` or `biweekly-N`. The
question list comes from LeetCode's GraphQL endpoint, which answers without
logging in, and each title then goes through the same manifest as everything
else, so the files are named and stamped as a filed solution would be — down to
LeetCode's own C++ starter as the body, ready to write in or paste over:

```cpp
// @title 4036-lexicographically-largest-string-after-pair-transformations [Medium]
// @contest biweekly-190 Q3 2026-10-05            <- these two written for you

// @verdict subs 3 pass
// @solution O(N) time O(N) space
// @star yes
// @patterns bits

class Solution { ... };
```

`DATE=` sets the day on `@contest` when it is not today. A file that already
exists is never touched, so `make contest` can be rerun safely.

## Problems on their own

`make misc TITLE=` is the same for a problem met anywhere but a contest: one
draft, in `misc/`, with `@contest misc` and the same four tags to fill. The
title is entered as on either site, exactly as `@title` is. A NeetCode problem
is refused — it belongs in [neetcode/](../neetcode/README.md), through
`make new` and `make insert`.

## Tags

**One solution per file.** `@solution` is a tag like the others, carrying the
complexity, with no `@end` to close it. There is no `@optimal`, `@primary` or
`@related` either: a contest file carries six tags and nothing else, and
`make sync` says so if one from a NeetCode file finds its way in. It is
otherwise held to the same bargain — every tag filled, all failures reported at
once, LeetCode's class and methods present and declared once.

Nothing is asked about optimality, because the question is a different one. A
pass in the window is as good as the judge needed, and an upsolve is written
from the best approach there is — studying a slower one would be strange.

**`@verdict` is whether you solved it yourself**, in LeetCode's own terms: in
the window, for a contest; unaided, for a problem on its own.

    // @verdict subs 1 pass             accepted first time
    // @verdict subs 3 pass             two wrong answers, then accepted
    // @verdict subs 1 fail             submitted, never accepted
    // @verdict subs 0 fail             never submitted

`subs` counts every submission, the accepted one included. There is no clock:
the count is what you remember afterwards, and a time nobody noted down when it
happened is one that gets made up later.

**A fail stays a fail, and its solution is the upsolve.** Every miss gets
studied and written up, so code in a file marked fail means it has been
upsolved; nothing is added to the verdict, which goes on saying what happened
on the day. The failed attempt itself is not kept. Until the upsolve is
written, the body stays LeetCode's empty starter and `@solution` and
`@patterns` may stay blank — that is what puts a problem on the upsolve list
rather than in ISSUES.md. Once there is code, all of it is owed.

**`@solution`** gives both bounds, as in the NeetCode files:
`O(N log N) time O(1) space`.

## CONTESTS.md

One row per contest, newest first, with a cell per question — `✓` solved in the
window, `✓ (2)` after two wrong answers, `✗` missed, `↻` missed and upsolved
since — and how many fell inside the 90 minutes. Below the table: the problems
in `misc/`, and the upsolve list.

STAR.md and SOLUTIONS.md are this tree's own, not the NeetCode ones. With one
solution to a problem there is nothing to set side by side, so SOLUTIONS.md is
the approaches themselves: every problem with code in it, its `@patterns` and
both bounds, easiest first — the way to find how something was done without
opening each file.

`make search` covers these files too, from the one `@patterns` vocabulary the
NeetCode files use.
