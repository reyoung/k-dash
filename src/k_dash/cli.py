"""k-dash command line interface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .builder import DEFAULT_BUILDER_IMAGE
from .cache import Cache
from .errors import KDashError
from .project import load_project
from .publish import local_build, publish_build, publish_release
from .templates import init_project


def _path(value: str) -> Path:
    return Path(value).expanduser()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="k-dash", description="Build and distribute TVM-FFI CUDA kernels")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init = subcommands.add_parser("init", help="create a kernel project")
    init.add_argument("kernel")
    init.add_argument("path", nargs="?", type=_path)
    init.add_argument("--template", choices=("cpp", "cutedsl"), default="cpp")
    init.add_argument("--license")

    build = subcommands.add_parser("build", help="materialize current source into local cache")
    build.add_argument("--version", required=True)
    build.add_argument("--cuda-version", required=True)
    build.add_argument("--cc", required=True)
    build.add_argument("--args", action="append", default=[], type=_path)
    build.add_argument("--builder-image", default=DEFAULT_BUILDER_IMAGE)
    build.add_argument(
        "--local-jit",
        action="store_true",
        help="build with the host Nix daemon instead of a Docker builder",
    )

    publish = subcommands.add_parser("publish", help="publish source and optional AOT builds")
    publish.add_argument("--version", required=True)
    publish.add_argument("--cuda-version")
    publish.add_argument("--cc")
    publish.add_argument("--aot-args", action="append", default=[], type=_path)
    publish.add_argument("--builder-image", default=DEFAULT_BUILDER_IMAGE)

    addition = subcommands.add_parser("publish-build", help="append a build from published source")
    addition.add_argument("--version", required=True)
    addition.add_argument("--cuda-version", required=True)
    addition.add_argument("--cc", required=True)
    addition.add_argument("--aot-args", required=True, type=_path)
    addition.add_argument("--builder-image", default=DEFAULT_BUILDER_IMAGE)

    cache = subcommands.add_parser("cache", help="inspect or maintain local cache")
    cache_subcommands = cache.add_subparsers(dest="cache_command", required=True)
    cache_subcommands.add_parser("info")
    cache_subcommands.add_parser("clean")
    prune = cache_subcommands.add_parser("prune")
    prune.add_argument("--max-size", required=True)
    return parser


def _size(value: str) -> int:
    units = {"B": 1, "KIB": 1 << 10, "MIB": 1 << 20, "GIB": 1 << 30, "TIB": 1 << 40}
    value = value.strip().upper()
    for unit in sorted(units, key=len, reverse=True):
        if value.endswith(unit):
            return int(float(value[: -len(unit)]) * units[unit])
    raise KDashError("size must use B/KiB/MiB/GiB/TiB", stage="cache")


def _prune(cache: Cache, maximum: int) -> None:
    entries = sorted(
        (path for group in (cache.root / "builds", cache.root / "releases") for path in group.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
    )
    import shutil

    while cache.size() > maximum and entries:
        shutil.rmtree(entries.pop(0))


def _run(args: argparse.Namespace) -> Any:
    if args.command == "init":
        destination = args.path or Path(args.kernel.split("/")[-1])
        return {"path": str(init_project(args.kernel, destination, args.template, args.license))}
    if args.command == "build":
        load_project(Path.cwd())
        results = local_build(
            Path.cwd(), version=args.version, cuda=args.cuda_version, cc=args.cc,
            args_files=args.args, builder_image=args.builder_image,
            use_local_jit=args.local_jit,
        )
        return {
            "builds": [
                {
                    "build_key": key,
                    "release_digest": release_digest,
                    "path": str(path),
                    "cache_hit": hit,
                    "provenance": provenance,
                }
                for key, path, hit, release_digest, provenance in results
            ]
        }
    if args.command == "publish":
        return publish_release(
            Path.cwd(), version=args.version, cuda=args.cuda_version, cc=args.cc,
            args_files=args.aot_args, builder_image=args.builder_image,
        )
    if args.command == "publish-build":
        return publish_build(
            Path.cwd(), version=args.version, cuda=args.cuda_version, cc=args.cc,
            args_file=args.aot_args, builder_image=args.builder_image,
        )
    cache = Cache()
    if args.cache_command == "info":
        return {"path": str(cache.root), "size": cache.size()}
    if args.cache_command == "clean":
        cache.clean()
        return {"path": str(cache.root), "cleaned": True}
    maximum = _size(args.max_size)
    _prune(cache, maximum)
    return {"path": str(cache.root), "size": cache.size(), "max_size": maximum}


def main(argv: list[str] | None = None) -> int:
    try:
        result = _run(_parser().parse_args(argv))
    except KDashError as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
