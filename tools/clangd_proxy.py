"""A clangd that understands this repo's files. Point your editor at it.

clangd is an excellent reader of C++ and these files are not C++ — they are
paste-ready judge submissions, several same-named classes to a file, with the
judge's helper types present only as comments. Rather than give that up, the
text is rewritten on its way to clangd by tools/stitch.py, which preserves every
line and column, so positions need no translation in either direction: what
clangd says about line 70 is true of line 70 on disk.

This sits between the editor and a real clangd and speaks LSP to both. It
touches three things and passes everything else through byte for byte:

  * didOpen and didChange carry the file's text, so that text is stitched
  * the reply to initialize has incremental sync turned off, because a whole
    document is what there is to stitch — clangd is as happy either way
  * the same reply has every capability that can edit a file removed

That last one is the point of the exercise. clangd would be reasoning about text
that does not exist on disk, so an edit it produced could land anywhere. Rename,
format and quick-fix are withdrawn before the editor ever learns they existed,
and the child is run with --header-insertion=never so completion cannot add an
include. What is left — hover, go to definition, find references, completion,
signature help, document symbols, diagnostics, inlay hints — is read-only, and
is the whole of what a repository of solved problems wants.

Usage: the editor runs `python3 tools/clangd_proxy.py`. Arguments are handed to
the real clangd. $CLANGD names one explicitly; otherwise PATH is searched, then
versioned names, then the usual install roots.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stitch  # noqa: E402

# Capabilities that let a language server write to a file. Withdrawn, because
# clangd is looking at text that is not what is on disk.
EDITING = (
    "documentFormattingProvider",
    "documentRangeFormattingProvider",
    "documentOnTypeFormattingProvider",
    "renameProvider",
    "codeActionProvider",
    "executeCommandProvider",
)

INSTALL_HINT = (
    "install one with apt/brew install clangd, or let the VS Code clangd "
    "extension download one for you"
)


def add_extension_install(storage: Path, add) -> None:
    """Any clangd the VS Code extension unpacked under this globalStorage.

    It lands at install/<version>/clangd_<version>/bin/clangd, newest first.
    """
    root = storage / "llvm-vs-code-extensions.vscode-clangd" / "install"
    if not root.is_dir():
        return
    for exe in sorted(root.glob("*/*/bin/clangd*"), reverse=True):
        add(exe)


def find_clangd() -> str | None:
    """Locate a clangd, best guess first. Any version will do."""
    found: list[str] = []

    def add(path: object) -> None:
        if path and str(path) not in found:
            found.append(str(path))

    add(os.environ.get("CLANGD"))  # explicit override wins
    add(shutil.which("clangd"))

    for version in range(40, 13, -1):  # newest first
        add(shutil.which(f"clangd-{version}"))

    for pattern in ("/usr/lib/llvm-*/bin/clangd",
                    "/opt/homebrew/opt/llvm*/bin/clangd",
                    "/usr/local/opt/llvm*/bin/clangd",
                    "/opt/homebrew/bin/clangd",
                    "C:/Program Files/LLVM/bin/clangd.exe"):
        head, _, tail = pattern.partition("*")
        parent = Path(head).parent
        if parent.is_dir():
            for exe in sorted(parent.glob(Path(head).name + "*" + tail), reverse=True):
                add(exe)

    # Last, because it is the fallback rather than the choice: the VS Code
    # clangd extension downloads its own copy into its global storage when it
    # finds none on PATH, and that copy tracks the latest release rather than
    # whatever you installed on purpose. It is often the only clangd on a
    # machine that has never installed LLVM, which is the case worth covering.
    for editor in ("Code", "Code - Insiders", "VSCodium"):
        for data in (Path.home() / ".config" / editor,
                     Path.home() / "Library/Application Support" / editor,
                     Path.home() / "AppData/Roaming" / editor):
            add_extension_install(data / "User/globalStorage", add)
    for server in (".vscode-server", ".vscode-server-insiders"):
        add_extension_install(Path.home() / server / "data/User/globalStorage", add)

    return found[0] if found else None


def read_message(stream) -> tuple[dict | None, bytes]:
    """One LSP frame: the parsed body, and the raw bytes it arrived as.

    The raw bytes are kept so anything not being rewritten is forwarded exactly
    as it came, rather than re-encoded into a subtly different JSON.
    """
    length = 0
    while True:
        line = stream.readline()
        if not line:
            return None, b""
        if line in (b"\r\n", b"\n"):
            break
        name, _, value = line.partition(b":")
        if name.strip().lower() == b"content-length":
            length = int(value)
    body = stream.read(length)
    if len(body) != length:
        return None, b""
    try:
        return json.loads(body), body
    except ValueError:
        return None, body


def write_message(stream, body: bytes) -> None:
    stream.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    stream.flush()


def encode(message: dict) -> bytes:
    return json.dumps(message).encode("utf-8")


def stitched(text: str) -> str:
    """Stitch a filed solution; leave anything else alone.

    The marker is the guard: a file with no @solution in it is not one of ours,
    and a stray commented-out class in some other C++ file should stay
    commented out. A rewrite that throws is not worth failing the editor over —
    the original text still parses as well as it ever did.
    """
    if "@solution" not in text:
        return text
    try:
        return stitch.stitch(text)
    except Exception as e:  # a rewrite is a convenience, never a dependency
        print(f"clangd_proxy: stitch failed, passing through ({e})",
              file=sys.stderr, flush=True)
        return text


def to_server(message: dict) -> dict:
    """Rewrite the text in the notifications that carry it."""
    method = message.get("method")
    params = message.get("params") or {}
    if method == "textDocument/didOpen":
        doc = params.get("textDocument") or {}
        if isinstance(doc.get("text"), str):
            doc["text"] = stitched(doc["text"])
    elif method == "textDocument/didChange":
        for change in params.get("contentChanges") or []:
            # Sync was forced to full, so every change is a whole document.
            # A ranged one would mean the editor ignored that, and a range
            # cannot be stitched in isolation — pass it through and let the
            # diagnostics say so rather than corrupting the document.
            if "range" not in change and isinstance(change.get("text"), str):
                change["text"] = stitched(change["text"])
    return message


def to_client(message: dict) -> dict:
    """Withdraw what would let clangd edit a file, and force full sync."""
    result = message.get("result")
    if not isinstance(result, dict):
        return message
    caps = result.get("capabilities")
    if not isinstance(caps, dict):
        return message
    for name in EDITING:
        caps.pop(name, None)
    sync = caps.get("textDocumentSync")
    if isinstance(sync, dict):
        sync["change"] = 1
    else:
        caps["textDocumentSync"] = {"openClose": True, "change": 1}
    return message


def pump(source, sink, transform, name: str) -> None:
    while True:
        message, raw = read_message(source)
        if not raw:
            break
        if message is None:
            write_message(sink, raw)
            continue
        try:
            changed = transform(message)
        except Exception as e:
            print(f"clangd_proxy: {name} passthrough after {e}",
                  file=sys.stderr, flush=True)
            write_message(sink, raw)
            continue
        write_message(sink, encode(changed))
    try:
        sink.close()
    except Exception:
        pass


def main(argv: list[str]) -> int:
    exe = find_clangd()
    if exe is None:
        print(f"clangd_proxy: no clangd found — {INSTALL_HINT}", file=sys.stderr)
        return 1

    # Being asked what this is rather than spoken to. Editors probe a language
    # server with --version before they will use it, and the honest answer is
    # the clangd underneath, not the interpreter that happens to run this.
    if any(a in ("--version", "--help") for a in argv):
        return subprocess.run([exe, *argv]).returncode

    child = subprocess.Popen(
        [exe, "--header-insertion=never", *argv],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    upstream = threading.Thread(
        target=pump,
        args=(sys.stdin.buffer, child.stdin, to_server, "editor"),
        daemon=True,
    )
    upstream.start()
    pump(child.stdout, sys.stdout.buffer, to_client, "clangd")
    return child.wait()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
