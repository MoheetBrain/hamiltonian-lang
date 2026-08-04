"""Command-line interface: ``hml``.

Subcommands
-----------
``check``      parse, resolve, type-check; print diagnostics
``render``     emit a chosen backend view
``canonical``  print the canonical JSON form
``hash``       print the content hash
``graph``      print the semantic graph as triples
``obligations``list the proof obligations the program generates
``views``      print every available view of the same object side by side
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .. import __version__, compile_source
from ..backends import available, render


def _read(path: str) -> tuple[str, str]:
    if path == "-":
        return sys.stdin.read(), "<stdin>"
    p = Path(path)
    if not p.exists():
        print(f"error: no such file: {path}", file=sys.stderr)
        raise SystemExit(2)
    return p.read_text(encoding="utf-8"), str(p)


def _compile(path: str, *, require_ok: bool = True):
    source, name = _read(path)
    result = compile_source(source, name)
    if result.diagnostics.items:
        print(result.diagnostics.render(), file=sys.stderr)
        print("", file=sys.stderr)
    if require_ok and not result.ok():
        n = len(result.diagnostics.errors)
        print(f"error: {n} error(s); aborting", file=sys.stderr)
        raise SystemExit(1)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="hml",
        description="Hamiltonian Lang v0 — private research prototype",
        epilog="No superiority claim over any existing language is made by this tool.",
    )
    ap.add_argument("--version", action="version", version=f"hamiltonian-lang {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="parse, resolve and type-check")
    p_check.add_argument("file")
    p_check.add_argument("--quiet", action="store_true")

    p_render = sub.add_parser("render", help="emit a backend view")
    p_render.add_argument("file")
    p_render.add_argument(
        "-t", "--target", default="english", choices=available(),
        help=f"one of: {', '.join(available())}",
    )
    p_render.add_argument(
        "--no-report", action="store_true",
        help="suppress the translation-loss header (not recommended)",
    )

    for name, helptext in (
        ("canonical", "print the canonical JSON form"),
        ("hash", "print the content hash"),
        ("graph", "print the semantic graph as triples"),
        ("obligations", "list generated proof obligations"),
        ("views", "print every view of the same object"),
    ):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("file")

    args = ap.parse_args(argv)

    if args.command == "check":
        result = _compile(args.file, require_ok=False)
        if result.ok():
            if not args.quiet:
                n = len(result.symbols.all) if result.symbols else 0
                print(
                    f"ok: {result.module.name} "
                    f"({len(result.module.statements)} statements, {n} symbols, "
                    f"{len(result.obligations)} proof obligation(s))"
                )
                w = len(result.diagnostics.warnings)
                if w:
                    print(f"     {w} warning(s)")
            return 0
        return 1

    if args.command == "render":
        result = _compile(args.file)
        out = render(args.target, result.module, result.symbols)
        if args.no_report or out.faithful:
            print(out.text)
        else:
            comment = {"latex": "%", "english": "#", "lean": "--", "stan": "//"}.get(
                args.target, "#"
            )
            print(out.with_report(comment))
        return 0

    if args.command == "canonical":
        result = _compile(args.file)
        print(json.dumps(json.loads(result.canonical()), indent=2, sort_keys=True))
        return 0

    if args.command == "hash":
        result = _compile(args.file)
        print(result.hash())
        return 0

    if args.command == "graph":
        result = _compile(args.file)
        print(result.graph().render_triples())
        return 0

    if args.command == "obligations":
        result = _compile(args.file)
        if not result.obligations:
            print("no proof obligations generated")
            return 0
        print(f"{len(result.obligations)} proof obligation(s):")
        for o in result.obligations:
            state = o.discharged_by or "NOT DISCHARGED"
            print(f"  [{o.kind:<22}] line {o.span.line:>3}  {o.description}")
            print(f"  {'':<24} status: {state}")
        return 0

    if args.command == "views":
        result = _compile(args.file)
        for target in ("hml", "english", "latex", "triples"):
            out = render(target, result.module, result.symbols)
            print(f"===== {target} =====")
            print(out.text.rstrip())
            if not out.faithful:
                print(out.report())
            print()
        print("===== canonical hash =====")
        print(result.hash())
        return 0

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
