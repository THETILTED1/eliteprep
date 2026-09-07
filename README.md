# eliteprep

A place to keep LeetCode solutions while you prepare, organised well enough
that you can still find things at a hundred problems.

Solutions are annotated C++ source files. There is no parallel markdown — the
prose lives next to the code it describes — and every index is generated, so
the only thing you maintain is the code you wrote.

You enter a problem by its title, from LeetCode or from neetcode.io, whichever
you happen to be looking at. Everything else is derived: the id, the slug, the
difficulty, the filename and the topic it belongs under. Nothing about a
problem is typed by hand and nothing is looked up twice.

`src/01-arrays-hashing/0217-contains-duplicate.cpp` is a worked example. Delete it
whenever you like; the tooling does not depend on it.

**C++ only.** The validation that makes this worth using — that a solution
declares the class and methods the judge expects — reads LeetCode's own C++
starter snippet, so it has nothing to check against in another language.

Three generated indexes, all built from the solved files alone:

| | |
|---|---|
| **[TOC.md](TOC.md)** | every solved problem, broken down by topic |
| **[STAR.md](STAR.md)** | the starred subset, same breakdown |
| **[SOLUTIONS.md](SOLUTIONS.md)** | problems that earned more than one approach, side by side |

TOC.md is the cover-all and carries nothing but the topic breakdown, so it stays
readable at a hundred problems. Neither it nor STAR.md lists solutions — that
comparison is the whole content of SOLUTIONS.md, where each approach gets its
complexity split into aligned Time and Space columns. None of this is a
checklist of the 150; NeetCode's own site is the better roadmap for what is
left.

## Keeping your solutions private

The tool is worth publishing; your solutions probably are not. Keep two repos.

**Public** — this one: `tools/`, `Makefile`, `template.cpp`, `.clang-format`,
the README and one example. Mark it a template repository on GitHub so anyone
can press *Use this template* and get their own copy, private if they want.

**Private** — your solutions, made from the public one, which stays attached as
`upstream` so improvements to the tool keep flowing in:

    git clone https://github.com/<you>/eliteprep prep && cd prep
    git remote rename origin upstream
    git remote add origin <your private repo>
    git push -u origin main

Take later tool changes with `git pull upstream main`. This stays quiet because
the two sides occupy disjoint paths — the tool is `tools/`, `Makefile`,
`template.cpp` and `.clang-format`; your work is `src/` — so there is
nothing to collide. The exception is the three generated indexes, which both
sides rewrite. They are derived, so take yours and rebuild rather than merging:

    git checkout --ours TOC.md STAR.md SOLUTIONS.md && make sync

Develop the tool in the public repo rather than the private one, and the flow
stays one-directional. `tools/signatures.json` is gitignored for the same
reason — it grows one entry per problem you file, so it would diverge
immediately, and it is refetched on demand.

## Workflow

    make new                          # input.cpp, from template.cpp
    $EDITOR input.cpp                 # fill in @title and the rest
    make insert

Editing a file that is already filed — correcting a complexity, adding a third
solution — needs `make sync`. It re-validates every filed problem against the
same rules, then tidies the ones that pass where they sit: `@title` and
`@related` restamped to handles, the code clang-formatted. A file that fails
validation is reported and left untouched, so nothing is rewritten out from
under a mistake. Nothing moves between topics either — that is `insert`'s job,
with `TOPIC=`. The indexes are only ever generated, so nothing hand-written
survives in them.

`SRC` defaults to `input.cpp`. `TOPIC` is required only for problems outside
the NeetCode 250; within it the topic is inferred:

    make insert SRC=other.cpp TOPIC=arrays-hashing

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

The file then moves to `src/01-arrays-hashing/0217-contains-duplicate.cpp` and
`TOC.md` is regenerated. `template.cpp` carries a second solution block; fill
it in or delete it, and if you leave it untouched `insert` drops it for you.
Re-running `insert` on an already-filed problem is safe — the canonical header
resolves to itself — so it doubles as a reformatter.

Re-inserting a problem overwrites whatever was filed under that handle before,
including moving it if you corrected `TOPIC`.

### Every tag must be filled

A draft is rejected unless all of these hold, and **every** failure is reported
at once rather than one at a time:

- exactly one `@title`, naming a problem that resolves, not still `{{problem}}`
- exactly one `@star`, reading `yes` or `no`
- exactly one `@related`, comma-separated; each entry must resolve, and an
  empty list is fine
- at least one solution block
- every solution has `@patterns`, a complexity on `@solution`, and a class body
- exactly one `@primary` across the file
- every solution declares LeetCode's own class name and defines all of its
  methods, so the file is a drop-in paste back into the judge

The one exception is a second solution block left exactly as the template wrote
it — that is dropped rather than rejected, so an unused block costs nothing.
Fill in any part of it and it must then be complete.

An unknown `TOPIC`, or a problem outside the 250 with no `TOPIC`, are likewise
errors. Nothing moves unless every check passes.

Every problem must live in one of the 18 topic directories — there is no
default bucket and no fallback. A source file anywhere else is reported by
`make sync`, since it would otherwise be indexed nowhere.

## Layout

    src/NN-topic-name/LLLL-problem-slug.cpp

The eighteen topic directories live under `src/`, which keeps the repository
front page to the tool and the indexes. They are NeetCode's roadmap topics,
prefixed `01`–`18` in its order, which is pedagogical rather than alphabetical. The 18 topics are kept because they are a
*single-label* partition — every problem has exactly one home — which is what a
directory tree needs. LeetCode's own tags are not: across the NeetCode 250 they
average 3.7 tags per problem, only 6 problems carry a single tag, and the most
common tag (`array`, on 141 of 250) partitions nothing. Those tags are a
cross-cutting label, which is all `@patterns` claims to be. Files are named by zero-padded LeetCode
id plus LeetCode title slug. LeetCode ids are permanent — never changed, never
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

// @patterns hashing             <- space-separated; labels this solution
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
`0217-contains-duplicate, 0049-group-anagrams`. Solutions are labelled by their `@patterns`, not by class name, so every class
in a file carries the *same* name — LeetCode's — and that is enforced. Nothing
is compiled, so the redefinition only matters to a future runner script, which
can rename as it stitches.

The class and method names come from LeetCode's own C++ starter snippet,
fetched once per problem and cached in `tools/signatures.json`. A solution
pasted from LeetCode passes by construction; one written on neetcode.io has to
be translated, because NeetCode renames methods — `hasDuplicate` there is
`containsDuplicate` on LeetCode. Design problems must implement the whole
interface: `min-stack` requires `class MinStack` with `push`, `pop`, `top` and
`getMin`.

Multiple approaches live in one file so a problem stays one unit. `@solution`
count is what surfaces a problem in [SOLUTIONS.md](SOLUTIONS.md), so that index
builds itself.

`@patterns` labels an approach rather than filing it: it is what names the row
in SOLUTIONS.md. There is deliberately no index of every problem by pattern —
the labels overlap the topics unevenly (`hashing` is a subset of Arrays &
Hashing, `sorting` corresponds to no topic at all), so such a list would sort
poorly and read worse than the topic breakdown it duplicates.

Files are paste-ready — no includes, no `using namespace std` — matching what
the judge expects.

## Formatting

`insert` runs the repo's [`.clang-format`](.clang-format) over every file it
writes, so nothing depends on how the code looked when you pasted it. The
notable setting is `RemoveBracesLLVM`, which drops the braces from
single-statement `if` / `for` / `while` bodies — LeetCode solutions are short
enough that the braces are mostly noise:

```cpp
for (size_t i = 1; i < nums.size(); ++i)      // instead of three lines
    if (nums[i] == nums[i - 1])               // of closing braces
        return true;
```

The rest tracks LeetCode's own C++ starter, so a pasted solution keeps its
shape: `public:` at column zero, `vector<int>& nums` rather than `&nums`, four
spaces, an 88-column limit. Tag comments are never reflowed.

`make sync` reformats filed files in place, so hand edits get tidied without
re-inserting. If `clang-format` is not on PATH, both commands say so and leave
the code unchanged rather than failing — formatting is cosmetic and never
blocks.

## Requirements

Python 3.9 or newer. **There is no virtualenv and nothing to install** — every
import is standard library, so there is nothing to activate before running
anything. The Makefile finds an interpreter itself and says so plainly if there
is none; the tools refuse to run on a version too old rather than failing
obscurely partway through.

`clang-format` 14 or newer is optional, and is looked for rather than assumed,
since it ships by default almost nowhere. In order:

1. `$CLANG_FORMAT`, if you want to name one explicitly
2. `clang-format` on `PATH`
3. **VS Code's C/C++ extension**, which bundles its own under
   `~/.vscode-server/extensions/ms-vscode.cpptools-*/LLVM/bin/` — often the only
   copy on a machine that has never installed LLVM
4. versioned names, `clang-format-40` down to `clang-format-14`
5. usual LLVM install roots on Linux, Homebrew and Windows

The version floor is real rather than cautious: `RemoveBracesLLVM` arrived in
14, and clang-format rejects a config containing a key it does not know instead
of ignoring it, so an older binary would fail on every file. Candidates that
are too old are skipped and named in the warning.

If nothing suitable turns up, both `insert` and `sync` say so and file the code
unchanged — formatting never blocks. The quickest fix on a machine with neither
LLVM nor VS Code is `pip install clang-format`, which ships the binary as a
wheel and so needs no compiler.

### Portability

The tools are OS-agnostic: `pathlib` throughout, `shutil.which` for lookups
(which honours `PATHEXT`, so it finds `clang-format.exe`), and the clang-format
search covers Linux, Homebrew and `C:/Program Files/LLVM` alike, plus VS Code's
bundle under either `.vscode-server` or `.vscode`.

Files are read and written as UTF-8 with LF endings explicitly, never at the
platform's discretion. That matters here: the generated indexes contain `·`,
`—` and `⭐`, which a Windows default of cp1252 would refuse to write. `sync`
compares bytes rather than decoded text, so a file saved with CRLF is
normalised rather than being mistaken for clean.

The one genuinely Unix-flavoured piece is the Makefile, which wants `make` and
a POSIX shell for its interpreter lookup. Every recipe is now a bare call into
`tools/insert.py`, so on a machine without `make` — Windows without WSL or Git
Bash — the same three commands are:

    python tools\insert.py --new input.cpp
    python tools\insert.py input.cpp
    python tools\insert.py --sync

## Manifests

`make new`, `make insert` and `make sync` are the only make targets. The two
scripts they use run standalone if you need them:


    python3 tools/manifest.py            # refresh both caches, then verify
    python3 tools/manifest.py <query>    # resolve one string
    python3 tools/gen_toc.py             # rewrite the three indexes

`manifest.resolve()` takes one string, sourceable from either site. All of
these land on `0217-contains-duplicate`:

**Enter the title**, as displayed on either site. That is the only input, and
there is only one code path serving it.

A query is reduced to its letters and digits before matching, and so is every
title in the manifests. Case, spacing, hyphens and punctuation therefore never
reach the lookup, which means all of these land on the same key without any of
them being a second supported format:

    Contains Duplicate    contains duplicate    contains-duplicate    ContainsDuplicate

The same reduction is what makes the genuinely awkward titles work with no
special handling: `Capital Gain/Loss` and `capital-gainloss` reduce alike, as
do `The Knight's Tour` and `the-knights-tour`. Across all 4046 LeetCode
problems it produces zero mismatches and zero collisions, so it can never send
you to the wrong problem.

Nothing but titles is indexed. A bare `217`, a `0217-contains-duplicate`
handle, and NeetCode's renamed slug `duplicate-integer` all fail — none of them
is a title with different punctuation, and none is special-cased into working.
A URL fails too, with a message telling you to use the title instead; that is a
diagnostic, not a resolution path.

Both sites' displayed titles are indexed, since both are front-facing spellings
rather than alternate encodings. That covers the single problem in the 250
where the two disagree: NeetCode's *Sum of All Subsets XOR Total* against
LeetCode's *Sum of All Subset XOR Totals*.

### Where the data comes from

neetcode.io is a single-page app with no API — every URL returns the same HTML
shell — but its main bundle ships the whole problem table inline, including
both slugs, the roadmap topic and the difficulty. `tools/manifest.py` scrapes
it, resolving the hashed bundle name from the shell each run so it survives
redeploys, and caches the NeetCode 250 (the 150 is a subset, and both share the
same 18 topics). LeetCode's `api/problems/all/` supplies the full catalogue for
supplementary problems. Neither needs authentication, and every scraped id is
cross-checked against LeetCode's own list on refresh.

Neither site is static: LeetCode adds problems continuously, and NeetCode
revises its lists and redeploys under a new bundle hash. So the bundle name is
resolved from the shell on every refresh, and `insert` treats a cache miss as
staleness rather than an error — it refreshes both manifests once and retries
before giving up. That is what lets a problem newer than the cache resolve on
the first attempt. `python3 tools/manifest.py` forces the same refresh by hand.

`tools/neetcode.json` and `tools/leetcode.json` are committed, so a fresh clone
works offline; refresh them when NeetCode changes its lists. If a `git pull`
ever conflicts on one, do not merge it — regenerate with `python3
tools/manifest.py`. `tools/signatures.json` is gitignored and refetched per
problem.
