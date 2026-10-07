# make new                                      start input.cpp from template.cpp
# make sync                                     tidy filed files, rebuild indexes
# make search                                  list every pattern in use
# make search PATTERN="hashing, sorting"        narrow to matching solutions
# make insert                                   file input.cpp
# make insert SRC=other.cpp TOPIC=arrays-hashing
# make contest                                  list the latest contests
# make contest C=biweekly-190                   a draft per question, under contests/
# make contest C=weekly-470 DATE=2026-10-04     ... sat on some other day
#
# SRC defaults to input.cpp. TOPIC is required only for problems outside the
# NeetCode 250; within it the topic is inferred.

SRC ?= input.cpp

# Everything the tools use is in the standard library, so there is no venv to
# activate and nothing to install — only an interpreter to find.
# `command -v` needs a POSIX shell; where there is none the plain name is used
# and PATH resolves it. Override with `make PY=/path/to/python`.
PY := $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
PY := $(if $(PY),$(PY),python3)

.PHONY: new insert sync search contest

new:
	@$(PY) tools/insert.py --new $(SRC)

insert:
	@$(PY) tools/insert.py $(SRC) $(if $(TOPIC),--topic $(TOPIC))

sync:
	@$(PY) tools/insert.py --sync

search:
	@$(PY) tools/gen_toc.py --search "$(PATTERN)"

contest:
	@$(PY) tools/contest.py $(C) $(if $(DATE),--date $(DATE))
