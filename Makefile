# make new                                      start input.cpp from template.cpp
# make sync                                     tidy filed files, rebuild indexes
# make search                                  list every pattern in use
# make search PATTERN="hashing, sorting"        narrow to matching solutions
# make insert                                   file input.cpp under neetcode/
# make insert SRC=other.cpp
# make contest                                  list the latest contests
# make contest C=biweekly-190                   a draft per question, under contests/
# make contest C=weekly-470 DATE=2026-10-04     ... sat on some other day
# make misc TITLE="two sum"                     one problem on its own, contests/misc/
#
# SRC defaults to input.cpp. neetcode/ takes NeetCode's problems alone, each in
# NeetCode's own topic; anything else is make misc.

SRC ?= input.cpp

# Everything the tools use is in the standard library, so there is no venv to
# activate and nothing to install — only an interpreter to find.
# `command -v` needs a POSIX shell; where there is none the plain name is used
# and PATH resolves it. Override with `make PY=/path/to/python`.
PY := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
PY := $(if $(PY),$(PY),python3)

.PHONY: new insert sync search contest misc

new:
	@$(PY) tools/insert.py --new $(SRC)

insert:
	@$(PY) tools/insert.py $(SRC)

sync:
	@$(PY) tools/insert.py --sync

search:
	@$(PY) tools/gen_toc.py --search "$(PATTERN)"

contest:
	@$(PY) tools/contest.py $(C) $(if $(DATE),--date $(DATE))

misc:
	@$(PY) tools/contest.py misc --title "$(TITLE)"
