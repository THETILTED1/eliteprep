# eliteprep

A place to keep LeetCode solutions while you prepare, organised well enough
that you can still find things at a hundred problems.

Solutions are annotated C++ source files. There is no parallel markdown — the
prose lives next to the code it describes — and every index is generated, so
the only thing you maintain is the code you wrote.

You enter a problem by its title, from LeetCode or from neetcode.io, whichever
you happen to be looking at. Everything else is derived: the id, the slug, the
difficulty, the filename and where it belongs. Nothing about a problem is typed
by hand and nothing is looked up twice.

**C++ only.** The validation that makes this worth using — that a solution
declares the class and methods the judge expects — reads LeetCode's own C++
starter snippet, so it has nothing to check against in another language.

## Two sections

Problems live in one of two trees, each with its own README and its own indexes
beside it. The tool at the root serves both.

| | |
|---|---|
| **[neetcode/](neetcode/README.md)** | the NeetCode 250 and nothing else, filed by NeetCode's eighteen topics, with several approaches to a problem kept side by side |
| **[contests/](contests/README.md)** | LeetCode contests, a directory each, and problems met anywhere else in `misc/` — one solution apiece, for volume |

    neetcode/   README.md  TOC.md  STAR.md  SOLUTIONS.md  OPTIMAL.md  01-arrays-hashing/ …
    contests/   README.md  CONTESTS.md  STAR.md  SOLUTIONS.md  biweekly-190/ …  misc/

The split is the point. The topics are a roadmap: a curated set, each problem
filed where it teaches something. Contest problems are whatever four LeetCode
set that week, and filing them among the topics would bury the roadmap under
volume. So `make insert` takes NeetCode's problems alone, and everything else
goes to `contests/`.

Three things cross both trees, and so live here at the root.

`make sync` re-validates and tidies every file in both, each by its own rules,
then rebuilds every index.

[ISSUES.md](ISSUES.md) is the one to check after a batch of work. It collects
files that failed validation, in either tree, index warnings, and — the case you
cannot see otherwise — problems whose class and method names **were never
verified**, because LeetCode publishes no C++ starter for its premium problems.
Seven of the NeetCode 150 are premium, so this is not a corner case. It says
"Nothing to report" when clean.

`make search` writes `search.md`. With no `PATTERN` it lists every pattern in
use, commonest first, with the problems under each — the answer to "search for
what?", and the quickest way to catch `two pointers` and `two-pointers` having
both crept in. With one (`make search PATTERN="hashing, two pointers"`) it
writes every solution whose `@patterns` match, with difficulty and complexity,
easiest first. Matching is case-insensitive and by substring, so `sort` finds
`sorting`, and the terms are a union. A miss lists every pattern you have
actually used, which is a quick way to catch your vocabulary drifting. Both
trees are searched, from the one shared `@patterns` vocabulary: NeetCode matches
first, contest matches beneath them in a section of their own. The file is
scratch and gitignored.

`neetcode/01-arrays-hashing/0217-contains-duplicate.cpp` is a worked example.
Delete it whenever you like; the tooling does not depend on it.

## Keeping your solutions private

The tool is worth publishing; your solutions probably are not. Keep two repos.

**Public** — this one: `tools/`, `Makefile`, `template.cpp`, `.clang-format`,
`.clangd`, `.vscode/`, the three READMEs and one example. Mark it a template
repository on GitHub so anyone can press *Use this template* and get their own
copy, private if they want.

**Private** — your solutions, made from the public one, which stays attached as
`upstream` so improvements to the tool keep flowing in:

    git clone https://github.com/<you>/eliteprep prep && cd prep
    git remote rename origin upstream
    git remote add origin <your private repo>
    git push -u origin main

Take later tool changes with `git pull upstream main`. This stays quiet because
the two sides occupy disjoint paths — the tool is `tools/`, `Makefile`,
`template.cpp`, `.clang-format`, `.clangd`, `.vscode/` and the READMEs; your
work is the problems under `neetcode/` and `contests/` — so there is nothing to
collide. The exception is the generated indexes, which both sides rewrite. They
are derived, so take yours and rebuild rather than merging:

    git checkout --ours neetcode/TOC.md neetcode/STAR.md neetcode/SOLUTIONS.md \
        neetcode/OPTIMAL.md contests/CONTESTS.md contests/STAR.md \
        contests/SOLUTIONS.md ISSUES.md
    make sync

Develop the tool in the public repo rather than the private one, and the flow
stays one-directional. `tools/signatures.json` is gitignored for the same
reason — it grows one entry per problem you file, so it would diverge
immediately, and it is refetched on demand.

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

## Editor support

Hover over `unordered_map` and be told what it is; jump from `push_back` into
the header it lives in; complete `nums.` — through a bare `using namespace std`
that is nowhere in the file, in a file that has no includes and three classes
called `Solution`. Set up once, runs in the background, and not a byte of any
solution changes.

Open the repository in VS Code with the
[clangd extension](https://marketplace.visualstudio.com/items?itemName=llvm-vs-code-extensions.vscode-clangd)
installed and it works; [`.vscode/settings.json`](.vscode/settings.json) is
committed. Any other editor wants the same server command:

    python3 tools/clangd_proxy.py --background-index

On Windows that is `python`, in `clangd.path` as much as anywhere else; the
Makefile's interpreter lookup does not reach here, because the editor starts
this one.

If the extension offers to download a clangd for you, that is not this repo
asking: it prompts whenever `clangd.path` names something that is not there,
and its default is a bare `clangd`, which plenty of machines do not have even
with LLVM installed — the packages are often called `clangd-18`, `clangd-22`
and so on. Installing one on PATH is the fix, and it is worth doing whatever
this repo needs, since the download it offers instead is invisible to every
other tool you own. The settings here point `clangd.path` at an interpreter, so
the prompt does not arise; they also pin `clangd.checkUpdates` off, because the
update check probes that path with `--version` and would read the interpreter's
version rather than a clangd's. The proxy answers `--version` with the clangd
it resolved, for anything that asks it directly.

Two things stand between a filed solution and a C++ parser, and they are
handled in different places.

The includes and the `using` are missing, and that is the easy half.
[`.clangd`](.clangd) forces [`tools/prelude.hpp`](tools/prelude.hpp) in front of
the first line, which is what the judge has effectively already included by the
time it compiles you. It names the headers one by one rather than reaching for
`<bits/stdc++.h>`, which is a libstdc++ extension and absent on libc++ and
MSVC. The file on disk stays paste-ready.

The classes are the hard half. Clang does not recover from a redefinition — it
drops the second `class Solution` outright — so an editor reading the file as it
stands goes blind from the second `@solution` onwards, which is exactly where a
file with two approaches is interesting. `tools/clangd_proxy.py` sits between the
editor and clangd and rewrites the text on its way past, leaving the file alone.
Each `@solution`/`@end` pair becomes a namespace, which makes the approaches
distinct without renaming anything you wrote.

The same pass turns the judge's helper types into real code. `ListNode`,
`TreeNode`, the several unrelated shapes of `Node` and the premium `Interval`
are all *already in the files that use them*, commented out exactly as LeetCode
ships them, so there is no table of them to keep anywhere and no request to
make: `Node` means the graph node in `0133-clone-graph` and the random-pointer
node in `0138-copy-list-with-random-pointer` because each file is read on its
own and each says so itself.

Every edit the rewrite makes lands on a line that carries no code — a marker
comment, or the decoration down the left edge of a block comment — and replaces
exactly as many characters as it removes. So the line count and the column of
every character of real code survive, and a position in what clangd read is the
same position in the file on disk. Nothing is mapped and nothing can drift.
`python3 tools/stitch.py neetcode/11-graphs/0127-word-ladder.cpp` prints what clangd
sees, if you want to look at it.

**Nothing that can write to a file is offered.** clangd is reasoning about text
that is not on disk, so an edit it produced could land anywhere. Rename,
format, quick-fix and execute-command are withdrawn from the capabilities the
editor is told about, before it ever learns they existed, and the server runs
with `--header-insertion=never` so a completion cannot add an include. What is
left — hover, go to definition, find references, completion, signature help,
document symbols, diagnostics, inlay hints — is read-only, and is the whole of
what a repository of solved problems wants from a language server. Formatting
stays where it already was, in `make insert` and `make sync`.

A draft whose `@solution` and `@end` markers do not yet balance is passed
through unrewritten rather than half-wrapped, so a file being edited behaves as
it would with no proxy at all instead of burying the real diagnostics under a
cascade. Diagnostics are otherwise the compiler's own, and quiet.

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

`clangd` is optional too, and wanted only by [editor support](#editor-support)
— nothing in `make` goes near it. Any version will do, since the rewrite that
makes these files parseable is done before clangd sees them. It is found the
same way: `$CLANGD`, then `clangd` on `PATH`, then the copy the VS Code clangd
extension downloads for itself, then versioned names and the usual install
roots.

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

Every make target is a bare call into a script, and the scripts run standalone
if you need them:


    python3 tools/manifest.py            # refresh both caches, then verify
    python3 tools/manifest.py <query>    # resolve one string
    python3 tools/gen_toc.py             # rewrite the indexes
    python3 tools/contest.py [<contest>] # make contest

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

Every displayed title is indexed, since each is a front-facing spelling rather
than an alternate encoding. LeetCode displays one per problem. NeetCode
displays two — the roadmap entry and the heading of the problem's own page —
and they are not the same. The roadmap disagrees with LeetCode once in the
250, *Sum of All Subsets XOR Total* against *Sum of All Subset XOR Totals*; the
page heading disagrees 19 times. Some drop a word (*Longest Increasing Path in
Matrix*), some rename the problem outright (*Rotting Fruit* for Rotting
Oranges, *Non-Cyclical Number* for Happy Number). All of them land on the same
problem, topic included.

### Where the data comes from

neetcode.io is a single-page app — every URL returns the same HTML shell — but
its main bundle ships the whole problem table inline, including both slugs, the
roadmap title and topic, and the difficulty. `tools/manifest.py` scrapes it,
resolving the hashed bundle name from the shell each run so it survives
redeploys, and caches the NeetCode 250 (the 150 is a subset, and both share the
same 18 topics). The problem page's heading is not in the bundle: the page
fetches it from a Firebase function as it loads, and a refresh asks that
function once per problem, eight at a time. It is undocumented, so if it stops
answering the refresh warns and carries on, and those problems resolve by their
roadmap title alone. LeetCode's `api/problems/all/` supplies the full catalogue
for supplementary problems. None of it needs authentication. Every scraped id
is cross-checked against LeetCode's own list on refresh, and every page title
against the titles of other problems.

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
