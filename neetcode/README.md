# NeetCode

The NeetCode 250 — which contains the 150 — and nothing else, filed under
NeetCode's own eighteen topics. A problem from anywhere else is refused by
`make insert`, and belongs in [contests/](../contests/README.md) through
`make misc`. The tool that serves both is described in the
[root README](../README.md).

| | |
|---|---|
| **[TOC.md](TOC.md)** | every solved problem, broken down by topic |
| **[STAR.md](STAR.md)** | the starred subset, same breakdown |
| **[SOLUTIONS.md](SOLUTIONS.md)** | problems that earned more than one approach, side by side |
| **[OPTIMAL.md](OPTIMAL.md)** | what is not optimal, grouped by the axis it falls short on |

All four are ordered by ascending difficulty, then by problem number.

TOC.md is the cover-all and carries nothing but the topic breakdown, so it stays
readable at a hundred problems. Neither it nor STAR.md lists solutions — that
comparison is the whole content of SOLUTIONS.md, where each approach gets its
complexity split into aligned Time and Space columns. None of this is a
checklist of the 150; NeetCode's own site is the better roadmap for what is
left.

## Workflow

    make new                          # input.cpp, from template.cpp
    $EDITOR input.cpp                 # fill in @title and the rest
    make insert

Editing a file that is already filed — correcting a complexity, adding a third
solution — needs `make sync`. It re-validates every filed problem against the
same rules, then tidies the ones that pass where they sit: `@title` and
`@related` restamped to handles, the code clang-formatted. A file that fails
validation is reported and left untouched, so nothing is rewritten out from
under a mistake. Nothing moves between topics either: a file sitting outside
the topic NeetCode gives it is reported, and `make insert SRC=` on it moves it.
The indexes are only ever generated, so nothing hand-written survives in them.

`SRC` defaults to `input.cpp`:

    make insert SRC=other.cpp

The topic is never asked for. This tree holds NeetCode's problems alone, so the
topic is always NeetCode's own, and a problem outside the 250 is refused — with
the `make misc` line that files it under [contests/](../contests/README.md)
instead.

`@title` takes the problem's **title**, as displayed on either site — the
heading, or the entry in the left sidebar. So does `@related`, comma-separated.
Nothing else is expected of you: `insert` resolves what you typed and stamps
the canonical handle back down, so what ends up stored never depends on which
site you happened to be reading.

    // @title contains duplicate         ->  // @title 0217-contains-duplicate [Easy]
    // @related valid anagram, two sum   ->  // @related 0242-valid-anagram, 0001-two-sum

You type titles; the file keeps handles. Reading a handle back is a structural
decomposition of a field insert wrote — the slug half still goes through the
one transform, and the id half is checked against what that returns rather than
trusted, so `0242-contains-duplicate` is rejected as inconsistent.

The file then moves to `neetcode/01-arrays-hashing/0217-contains-duplicate.cpp`
and `TOC.md` is regenerated. `template.cpp` carries a second solution block; fill
it in or delete it, and if you leave it untouched `insert` drops it for you.
Re-running `insert` on an already-filed problem is safe — the canonical header
resolves to itself — so it doubles as a reformatter.

Re-inserting a problem overwrites whatever was filed under that handle before.

### Every tag must be filled

A draft is rejected unless all of these hold, and **every** failure is reported
at once rather than one at a time:

- exactly one `@title`, naming a problem that resolves, not still `{{problem}}`
- exactly one `@star`, reading `yes` or `no`
- exactly one `@related`, comma-separated; each entry must resolve, and an
  empty list is fine
- at least one solution block
- every solution has exactly one `@optimal`, reading `yes` or `no` plus the
  axis that beats it, `@patterns`
  (comma-separated), a complexity on `@solution`, and a class body
- exactly one `@primary` across the file
- every solution declares LeetCode's own class name and defines all of its
  methods, so the file is a drop-in paste back into the judge

The one exception is a second solution block left exactly as the template wrote
it — that is dropped rather than rejected, so an unused block costs nothing.
Fill in any part of it and it must then be complete.

A problem outside the NeetCode 250 is likewise an error. Nothing moves unless
every check passes.

Every problem must live in the topic directory NeetCode gives it — there is no
default bucket and no fallback. A source file anywhere else in the repository,
outside these and `contests/`, is reported by `make sync`, since it would
otherwise be indexed nowhere.

## Layout

    neetcode/NN-topic-name/LLLL-problem-slug.cpp

The eighteen topic directories are NeetCode's roadmap topics, prefixed `01`–`18`
in its order, which is pedagogical rather than alphabetical. They are kept
because they are a *single-label* partition — every problem has exactly one home — which is what a
directory tree needs. LeetCode's own tags are not: across the NeetCode 250 they
average 3.7 tags per problem, only 6 problems carry a single tag, and the most
common tag (`array`, on 141 of 250) partitions nothing. Those tags are a
cross-cutting label, which is all `@patterns` claims to be. Files are named by
zero-padded LeetCode id plus LeetCode title slug. LeetCode ids are permanent — never changed, never
reused — so the handle is stable, sorts correctly, and reads as a name:
`0217-contains-duplicate`. That is also how `@related` refers to problems.

## Annotations

Identity is never typed by hand. Title, difficulty and topic come from the
manifest; id and slug come from the filename. A source file carries only what
is yours:

```cpp
// 0217-contains-duplicate [Easy]  <- written by insert

// @title 0217-contains-duplicate [Easy]   <- stamped by insert from a title
// @star yes                     <- yes or no; flags it as interesting

// @optimal no time O(N)         <- yes, or no and what beats it
// @patterns hashing, sorting    <- comma-separated; labels this solution
// @solution O(N) time O(N) space
// @primary                      <- bare; at most one per file
//
class Solution { ... };

// @related 0242-valid-anagram, 0049-group-anagrams   <- stamped likewise
```

Comment blocks are grouped by blank lines. A group containing `@solution`
describes the class beneath it; `@star` and `@related` are file-level wherever
they appear, and the template puts `@related` at the foot of the file, where a
"see also" belongs. Both `@title` and `@related` are entered as titles and
stored as handles, so `contains-duplicate, GROUP ANAGRAMS` is filed as
`0217-contains-duplicate, 0049-group-anagrams`. Solutions are labelled by their
`@patterns`, not by class name, so every class in a file carries the *same* name — LeetCode's — and that is enforced. Nothing
is compiled, so the redefinition costs nothing here; it is
[the editor](../README.md#editor-support) that has to be told what to make of it.

The class and method names come from LeetCode's own C++ starter snippet,
fetched once per problem and cached in `tools/signatures.json`. A solution
pasted from LeetCode passes by construction; one written on neetcode.io has to
be translated, because NeetCode renames methods — `hasDuplicate` there is
`containsDuplicate` on LeetCode. Design problems must implement the whole
interface: `min-stack` requires `class MinStack` with `push`, `pop`, `top` and
`getMin`.

`@optimal` sits just below every `@solution` and is required like the rest.
Tag order inside a block is not enforced, so it still parses if you write it
above. It reads `yes`, or `no` followed by the axis it falls short on:

    // @optimal yes
    // @optimal no time O(N)          <- a better bound exists, and this is it
    // @optimal no style              <- complexity is optimal; the writing is not
    // @optimal no space O(1) style   <- more than one axis is owed

`time` and `space` carry the bound that beats them; `style` carries nothing,
because there is no notation for "shorter than this". Naming the axis is the
same rule that made `@optimal` mandatory in the first place: a bare `no` records
that you were unhappy without recording what would fix it, which is the half
worth keeping. So a bare `no` is rejected.

[OPTIMAL.md](OPTIMAL.md) collects the problems where **no** solution is marked
`yes`, one section per axis, with the bound it has beside the bound that beats
it. A solution owing two axes appears under both — the time debt and the style
debt are different jobs, done on different days.

Any, not every. A `no` sitting beside a `yes` on the same problem is an
alternative that was kept — the O(N log N) sort next to the O(N) hash set,
there because it teaches something or trades time for space — and it does not
put the problem back in the queue. Once the best answer is written down the
problem is done, and comparing the approaches is what
[SOLUTIONS.md](SOLUTIONS.md) is for. So TOC.md's `Opt` column reads `✓` when an
optimal solution is present and `·` when there is not one yet.

It is deliberately your call. Neither site publishes the optimal complexity in
any form a script can read: NeetCode's bundle carries none, its API is behind
authentication, and LeetCode keeps complexity in the editorial, which is
`paidOnly`. Judging your own is the only honest option.

Multiple approaches live in one file so a problem stays one unit. `@solution`
count is what surfaces a problem in [SOLUTIONS.md](SOLUTIONS.md), so that index
builds itself.

`@patterns` labels an approach rather than filing it: it is what names the row
in SOLUTIONS.md. There is deliberately no index of every problem by pattern —
the labels overlap the topics unevenly (`hashing` is a subset of Arrays &
Hashing, `sorting` corresponds to no topic at all), so such a list would sort
poorly and read worse than the topic breakdown it duplicates.

Files are paste-ready — no includes, no `using namespace std`, and no `std::`
qualification — matching what the judge hands you.
