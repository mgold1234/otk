import argparse
import logging
import pathlib
import sys

from .constant import PREFIX_TARGET
from .context import CommonContext
from .context import registry as context_registry
from .document import Omnifest
from .help.log import JSONSequenceHandler
from .target import CommonTarget
from .target import registry as target_registry
from .transform import process_include, resolve
from .traversal import State

log = logging.getLogger(__name__)


def root() -> int:
    argv = sys.argv[1:]

    parser = parser_create()
    arguments = parser.parse_args(argv)

    # turn on logging as *soon* as possible, so it can be used early
    logging.basicConfig(
        level=logging.WARNING - (10 * arguments.verbose),
        handlers=[
            (
                JSONSequenceHandler(arguments.identifier, stream=sys.stderr)
                if arguments.json
                else logging.StreamHandler()
            ),
        ],
    )

    # some arguments need to be handled before continuing with
    # subcommands
    if arguments.identifier and not arguments.json:
        parser.print_help()
        parser.exit()

    if arguments.command == "compile":
        return compile(arguments)
    elif arguments.command == "validate":
        return validate(arguments)

    raise RuntimeError("Unknown subcommand")


def _process(arguments: argparse.Namespace, dry_run: bool) -> int:
    src = sys.stdin if arguments.input is None else open(arguments.input)
    if not dry_run:
        dst = sys.stdout if arguments.output is None else open(arguments.output, "w")

    # the working directory is either the current directory for stdin or the
    # directory the omnifest is located in
    cwd = pathlib.Path.cwd() if arguments.input is None else pathlib.Path(src.name).parent

    if arguments.input is None:
        path = pathlib.Path(f"/proc/self/fd/{sys.stdin.fileno()}")
    else:
        path = pathlib.Path(arguments.input)

    ctx = CommonContext(cwd)
    state = State(path=path, defines=ctx.defines)
    doc = Omnifest(process_include(ctx, state, path))

    # let's peek at the tree to validate some things necessary for compilation
    # we might want to move this into a separate place once this gets shared
    # across multiple command
    target_available = {
        key.removeprefix(PREFIX_TARGET): val for key, val in doc.tree.items() if key.startswith(PREFIX_TARGET)
    }

    if not target_available:
        log.fatal("INPUT does not contain any targets")
        return 1

    target_requested = arguments.target

    if len(target_available) > 1 and not target_requested:
        log.fatal("INPUT contains multiple targets, `-t` is required")
        return 1

    # set the requested target to the default case now that we know that
    # there aren't multiple targets available and none are requested
    target_requested = list(target_available.keys())[0]

    if target_requested not in target_available:
        log.fatal("requested target %r does not exist in INPUT", target_requested)
        return 1

    # and also for the specific target
    try:
        kind, name = target_requested.split(".")
    except ValueError:
        # TODO handle earlier
        log.fatal(
            "malformed target name %r. We need a format of '<TARGET_KIND>.<TARGET_NAME>'.",
            target_requested,
        )
        return 1

    # re-resolve the specific target with the specific context and target if
    # applicable
    spec = context_registry.get(kind, CommonContext)(ctx)
    state = State(path=path, defines=ctx.defines)
    tree = resolve(spec, state, doc.tree[f"{PREFIX_TARGET}{kind}.{name}"])

    # and then output by writing to the output
    if not dry_run:
        dst.write(target_registry.get(kind, CommonTarget)().as_string(spec, tree))

    return 0


def compile(arguments: argparse.Namespace) -> int:
    return _process(arguments, dry_run=False)


def validate(arguments: argparse.Namespace) -> int:
    return _process(arguments, dry_run=True)


def parser_create() -> argparse.Namespace:
    # set up the main parser arguments
    parser = argparse.ArgumentParser(
        prog="otk",
        description="`otk` is the omnifest toolkit. A program to work with omnifest inputs and translate them into the native formats for image build tooling.",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=False,
        help="Sets output format to JSONseq. Output on stderr will be JSONseq records with ASCII record separators.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Sets verbosity. Can be passed multiple times to be more verbose.",
    )
    parser.add_argument(
        "-i",
        "--identifier",
        default=None,
        help="An identifier to include in all log records generated by `otk -j`. Can only be used together with `-j`.",
    )
    parser.add_argument(
        "-w",
        "--warn",
        default=None,
        help="Enable warnings, can be passed multiple times.",
    )

    # get a subparser action
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="command")

    parser_compile = subparsers.add_parser("compile", help="Compile an omnifest.")
    parser_compile.add_argument(
        "input",
        metavar="INPUT",
        nargs="?",
        default=None,
        help="Omnifest to compile to or none for STDIN.",
    )
    parser_compile.add_argument(
        "-o",
        "--output",
        default=None,
        help="File to output to or none for STDOUT.",
    )
    parser_compile.add_argument(
        "-t",
        "--target",
        default=None,
        help="Target to output, required if more than one target exists in an omnifest.",
    )

    parser_validate = subparsers.add_parser("validate", help="Validate an omnifest.")
    parser_validate.add_argument(
        "input",
        metavar="INPUT",
        nargs="?",
        default=None,
        help="Omnifest to validate to or none for STDIN.",
    )
    parser_validate.add_argument(
        "-t",
        "--target",
        default=None,
        help="Target to validate, required if more than one target exists in an omnifest.",
    )

    return parser
