from __future__ import annotations

import ast
from bisect import bisect_right
import builtins
from collections import defaultdict
from collections.abc import Sequence, Set as AbstractSet
from dataclasses import dataclass, field as dataclass_field, replace
from html import escape as html_escape
import json
import keyword
import os
import re
import stat
import symtable
import sys
import token
import tokenize
from . import __version__
from io import StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TextIO

from .rulesets import LoadedRule, RulesetError, filter_rules, load_rulesets

METHOD_LENGTH_RULE_NAME = "ExcessiveMethodLength"
CYCLOMATIC_COMPLEXITY_RULE_NAME = "CyclomaticComplexity"
NPATH_COMPLEXITY_RULE_NAME = "NPathComplexity"
EXCESSIVE_PARAMETER_LIST_RULE_NAME = "ExcessiveParameterList"
EXCESSIVE_CLASS_LENGTH_RULE_NAME = "ExcessiveClassLength"
EXCESSIVE_PUBLIC_COUNT_RULE_NAME = "ExcessivePublicCount"
TOO_MANY_FIELDS_RULE_NAME = "TooManyFields"
TOO_MANY_METHODS_RULE_NAME = "TooManyMethods"
TOO_MANY_PUBLIC_METHODS_RULE_NAME = "TooManyPublicMethods"
EXCESSIVE_CLASS_COMPLEXITY_RULE_NAME = "ExcessiveClassComplexity"
SHORT_CLASS_NAME_RULE_NAME = "ShortClassName"
LONG_CLASS_NAME_RULE_NAME = "LongClassName"
SHORT_VARIABLE_RULE_NAME = "ShortVariable"
LONG_VARIABLE_RULE_NAME = "LongVariable"
SHORT_METHOD_NAME_RULE_NAME = "ShortMethodName"
CONSTANT_NAMING_CONVENTIONS_RULE_NAME = "ConstantNamingConventions"
BOOLEAN_GET_METHOD_NAME_RULE_NAME = "BooleanGetMethodName"
UNUSED_LOCAL_VARIABLE_RULE_NAME = "UnusedLocalVariable"
UNUSED_FORMAL_PARAMETER_RULE_NAME = "UnusedFormalParameter"
UNUSED_PRIVATE_FIELD_RULE_NAME = "UnusedPrivateField"
UNUSED_PRIVATE_METHOD_RULE_NAME = "UnusedPrivateMethod"
BOOLEAN_ARGUMENT_FLAG_RULE_NAME = "BooleanArgumentFlag"
ELSE_EXPRESSION_RULE_NAME = "ElseExpression"
STATIC_ACCESS_RULE_NAME = "StaticAccess"
IF_STATEMENT_ASSIGNMENT_RULE_NAME = "IfStatementAssignment"
DUPLICATED_ARRAY_KEY_RULE_NAME = "DuplicatedArrayKey"
EXIT_EXPRESSION_RULE_NAME = "ExitExpression"
EXIT_CALL_NAMES = frozenset(
    {"sys.exit", "os._exit", "builtins.exit", "builtins.quit", "exit", "quit"}
)
COUNT_IN_LOOP_EXPRESSION_RULE_NAME = "CountInLoopExpression"
DEVELOPMENT_CODE_FRAGMENT_RULE_NAME = "DevelopmentCodeFragment"
DEVELOPMENT_CALL_NAMES = frozenset({"breakpoint", "builtins.breakpoint", "pdb.set_trace"})
EMPTY_CATCH_BLOCK_RULE_NAME = "EmptyCatchBlock"
COUPLING_BETWEEN_OBJECTS_RULE_NAME = "CouplingBetweenObjects"
GLOBAL_VARIABLE_RULE_NAME = "GlobalVariable"
LACK_OF_COHESION_RULE_NAME = "LackOfCohesionOfMethods"
CAMEL_CASE_CLASS_RULE_NAME = "CamelCaseClassName"
CAMEL_CASE_METHOD_RULE_NAME = "CamelCaseMethodName"
CAMEL_CASE_PROPERTY_RULE_NAME = "CamelCasePropertyName"
CAMEL_CASE_PARAMETER_RULE_NAME = "CamelCaseParameterName"
CAMEL_CASE_VARIABLE_RULE_NAME = "CamelCaseVariableName"
REPORT_FORMATS = frozenset(
    {"text", "xml", "json", "html", "ansi", "github", "gitlab", "checkstyle", "sarif"}
)
DEFAULT_IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".cache",
        ".git",
        ".hg",
        ".hypothesis",
        ".mypy_cache",
        ".nox",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "cache",
        "coverage",
        "dist",
        "env",
        "generated",
        "htmlcov",
        "out",
        "output",
        "site-packages",
        "tmp",
        "venv",
    }
)
TEST_DIRECTORY_NAMES = frozenset({"test", "tests", "__test__", "__tests__"})
REQUIRED_ARGUMENTS = "<paths> <format> <ruleset[,ruleset...]>"
VALUE_OPTIONS = frozenset(
    {
        "--exclude",
        "--maximum-priority",
        "--maximumpriority",
        "--minimum-priority",
        "--minimumpriority",
        "--only",
        "--enable",
        "--disable",
        "--report-file",
        "--reportfile",
        "--suffixes",
        "--color",
    }
)
BOOLEAN_OPTIONS = frozenset(
    {
        "--ignore-errors-on-exit",
        "--ignore-tests",
        "--ignore-violations-on-exit",
        "--strict",
        "--verbose",
    }
)
DIRECTIVE_PATTERN = re.compile(
    r"^messpy-(disable-next-line|disable|enable)(?:\s+(.+?))?$", re.IGNORECASE
)
RULE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CODE_SIZE_RULE_NAMES = frozenset(
    {
        CYCLOMATIC_COMPLEXITY_RULE_NAME,
        NPATH_COMPLEXITY_RULE_NAME,
        METHOD_LENGTH_RULE_NAME,
        EXCESSIVE_PARAMETER_LIST_RULE_NAME,
        EXCESSIVE_CLASS_LENGTH_RULE_NAME,
        EXCESSIVE_PUBLIC_COUNT_RULE_NAME,
        TOO_MANY_FIELDS_RULE_NAME,
        TOO_MANY_METHODS_RULE_NAME,
        TOO_MANY_PUBLIC_METHODS_RULE_NAME,
        EXCESSIVE_CLASS_COMPLEXITY_RULE_NAME,
    }
)
CLASS_CODE_SIZE_RULE_NAMES = frozenset(
    {
        EXCESSIVE_CLASS_LENGTH_RULE_NAME,
        EXCESSIVE_PUBLIC_COUNT_RULE_NAME,
        TOO_MANY_FIELDS_RULE_NAME,
        TOO_MANY_METHODS_RULE_NAME,
        TOO_MANY_PUBLIC_METHODS_RULE_NAME,
        EXCESSIVE_CLASS_COMPLEXITY_RULE_NAME,
    }
)
NAMING_RULE_NAMES = frozenset(
    {
        SHORT_CLASS_NAME_RULE_NAME,
        LONG_CLASS_NAME_RULE_NAME,
        SHORT_VARIABLE_RULE_NAME,
        LONG_VARIABLE_RULE_NAME,
        SHORT_METHOD_NAME_RULE_NAME,
        CONSTANT_NAMING_CONVENTIONS_RULE_NAME,
        BOOLEAN_GET_METHOD_NAME_RULE_NAME,
        CAMEL_CASE_CLASS_RULE_NAME,
        CAMEL_CASE_METHOD_RULE_NAME,
        CAMEL_CASE_PROPERTY_RULE_NAME,
        CAMEL_CASE_PARAMETER_RULE_NAME,
        CAMEL_CASE_VARIABLE_RULE_NAME,
    }
)
UNUSED_CODE_RULE_NAMES = frozenset(
    {
        UNUSED_LOCAL_VARIABLE_RULE_NAME,
        UNUSED_FORMAL_PARAMETER_RULE_NAME,
        UNUSED_PRIVATE_FIELD_RULE_NAME,
        UNUSED_PRIVATE_METHOD_RULE_NAME,
    }
)
CLEAN_CODE_RULE_NAMES = frozenset(
    {
        BOOLEAN_ARGUMENT_FLAG_RULE_NAME,
        ELSE_EXPRESSION_RULE_NAME,
        STATIC_ACCESS_RULE_NAME,
        IF_STATEMENT_ASSIGNMENT_RULE_NAME,
        DUPLICATED_ARRAY_KEY_RULE_NAME,
    }
)
DESIGN_RULE_NAMES = frozenset(
    {
        EXIT_EXPRESSION_RULE_NAME,
        COUNT_IN_LOOP_EXPRESSION_RULE_NAME,
        DEVELOPMENT_CODE_FRAGMENT_RULE_NAME,
        EMPTY_CATCH_BLOCK_RULE_NAME,
        COUPLING_BETWEEN_OBJECTS_RULE_NAME,
        GLOBAL_VARIABLE_RULE_NAME,
        LACK_OF_COHESION_RULE_NAME,
    }
)


@dataclass(frozen=True)
class RuleSelection:
    rulesets: tuple[str, ...]
    only: tuple[str, ...]
    enable: tuple[str, ...]
    disable: tuple[str, ...]
    minimum_priority: int
    maximum_priority: int


@dataclass(frozen=True)
class ExitPolicy:
    ignore_errors_on_exit: bool
    ignore_violations_on_exit: bool


@dataclass(frozen=True)
class ParsedArguments:
    paths: tuple[str, ...]
    report_format: str
    suffixes: frozenset[str]
    exclusions: tuple[str, ...]
    ignore_tests: bool
    report_file: Path | None
    strict: bool
    verbose: bool
    color: str
    show_help: bool
    show_version: bool
    rule_selection: RuleSelection
    exit_policy: ExitPolicy


class CliError(Exception):
    def __init__(self, message: str, ignore_errors_on_exit: bool = False) -> None:
        super().__init__(message)
        self.ignore_errors_on_exit = ignore_errors_on_exit


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    rule_name: str
    priority: int
    message: str
    suppressed: bool = False
    context: str = ""


@dataclass(frozen=True)
class ProcessingError:
    path: Path
    line: int
    message: str


@dataclass(frozen=True)
class CallableInfo:
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
    name: str
    kind: str
    parameter_count: int


@dataclass(frozen=True)
class ClassInfo:
    node: ast.ClassDef
    name: str
    fields: tuple[str, ...]
    methods: tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]
    is_ast_visitor: bool
    has_unresolved_base: bool


@dataclass(frozen=True)
class NamingTarget:
    name: str
    line: int
    role: str
    contract: bool = False


@dataclass(frozen=True)
class NamingCallable:
    node: ast.FunctionDef | ast.AsyncFunctionDef
    role: str


@dataclass(frozen=True)
class ScopeUsage:
    used_names: frozenset[str]
    free_names: frozenset[str]


@dataclass(frozen=True)
class PrivateMemberUsage:
    accessed_names: frozenset[str]
    exported_names: frozenset[str]
    requires_conservative_handling: bool


@dataclass(frozen=True)
class CleanCodeCallable:
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
    owner_name: str | None


def run(arguments: Sequence[str], stdout: TextIO, stderr: TextIO) -> int:
    parsed_arguments: ParsedArguments | None = None
    try:
        parsed_arguments = _parse_arguments(arguments)
        early_exit_status = _handle_help_or_version(parsed_arguments, stdout)
        if early_exit_status is not None:
            return early_exit_status
        return _run_analysis(parsed_arguments, stdout, stderr)
    except (CliError, RulesetError) as error:
        stderr.write(f"Error: {error}\n")
        if (parsed_arguments and parsed_arguments.exit_policy.ignore_errors_on_exit) or getattr(
            error, "ignore_errors_on_exit", False
        ):
            return 0
        return 1
    except (OSError, ValueError) as error:
        stderr.write(f"Error: {error}\n")
        return 0 if parsed_arguments and parsed_arguments.exit_policy.ignore_errors_on_exit else 1


def _handle_help_or_version(parsed_arguments: ParsedArguments, stdout: TextIO) -> int | None:
    if parsed_arguments.show_help:
        stdout.write(_help_text())
        return 0
    if parsed_arguments.show_version:
        stdout.write(f"{_messpy_version()}\n")
        return 0
    return None


def _run_analysis(parsed_arguments: ParsedArguments, stdout: TextIO, stderr: TextIO) -> int:
    if parsed_arguments.report_format.lower() not in REPORT_FORMATS:
        raise CliError(f"Unknown format: {parsed_arguments.report_format}")
    selection = parsed_arguments.rule_selection
    rules = filter_rules(
        load_rulesets(selection.rulesets),
        selection.only,
        selection.enable,
        selection.disable,
        selection.minimum_priority,
        selection.maximum_priority,
    )
    if parsed_arguments.verbose:
        stderr.write(f"Loaded rules: {', '.join(rule.name for rule in rules)}\n")

    input_paths = [Path(value).resolve() for value in parsed_arguments.paths]
    source_files = _source_files(
        input_paths,
        parsed_arguments.suffixes,
        parsed_arguments.exclusions,
        parsed_arguments.ignore_tests,
    )
    findings, processing_errors = _analyze(source_files, rules)
    reported_findings = findings if parsed_arguments.strict else _unsuppressed(findings)
    report = _render_report(
        parsed_arguments.report_format,
        reported_findings,
        processing_errors,
        _use_color(parsed_arguments, stdout),
    )
    if parsed_arguments.report_file is None:
        stdout.write(report)
    else:
        _write_report(parsed_arguments.report_file, report)
    return _exit_status(
        reported_findings,
        processing_errors,
        parsed_arguments.exit_policy.ignore_errors_on_exit,
        parsed_arguments.exit_policy.ignore_violations_on_exit,
    )


def main() -> None:
    raise SystemExit(run(sys.argv[1:], sys.stdout, sys.stderr))


def _messpy_version() -> str:
    return __version__


@dataclass
class _RuleSelectionState:
    only: list[str] = dataclass_field(default_factory=list)
    enable: list[str] = dataclass_field(default_factory=list)
    disable: list[str] = dataclass_field(default_factory=list)
    minimum_priority: int = 1
    maximum_priority: int = 5


@dataclass
class _ArgumentParseState:
    positionals: list[str] = dataclass_field(default_factory=list)
    suffixes: set[str] = dataclass_field(default_factory=lambda: {".py", ".pyi"})
    suffixes_provided: bool = False
    exclusions: list[str] = dataclass_field(default_factory=list)
    report_file: Path | None = None
    ignore_tests: bool = False
    ignore_errors_on_exit: bool = False
    ignore_violations_on_exit: bool = False
    strict: bool = False
    verbose: bool = False
    color: str = "auto"
    rules: _RuleSelectionState = dataclass_field(default_factory=_RuleSelectionState)
    show_help: bool = False
    show_version: bool = False


def _parse_arguments(arguments: Sequence[str]) -> ParsedArguments:
    state = _ArgumentParseState()
    index = 0
    argument_count = len(arguments)
    while index < argument_count:
        argument = arguments[index]
        if argument in {"-h", "--help"}:
            state.show_help = True
            index += 1
            continue
        if argument in {"-v", "--version"}:
            state.show_version = True
            index += 1
            continue
        if not argument.startswith("-"):
            state.positionals.append(argument)
            index += 1
            continue

        option_name, option_value = _split_option(argument)
        if option_name in VALUE_OPTIONS:
            index = _apply_value_option(state, arguments, index, option_name, option_value)
            continue
        if option_name in BOOLEAN_OPTIONS:
            _apply_boolean_option(state, option_name, option_value)
            index += 1
            continue
        raise CliError(f"Unknown option: {option_name}", state.ignore_errors_on_exit)

    if state.show_help or state.show_version:
        return _finish_help_or_version_parsing(state)
    return _finish_analysis_parsing(state)


def _apply_value_option(
    state: _ArgumentParseState, arguments: Sequence[str], index: int, option_name: str, option_value: str | None
) -> int:
    if option_value is None:
        if index + 1 == len(arguments) or arguments[index + 1].startswith("-"):
            raise CliError(f"Missing value for option: {option_name}", state.ignore_errors_on_exit)
        option_value = arguments[index + 1]
        index += 1
    _dispatch_value_option(state, option_name, option_value)
    return index + 1


def _dispatch_value_option(state: _ArgumentParseState, option_name: str, option_value: str) -> None:
    if option_name in {"--report-file", "--reportfile"}:
        state.report_file = Path(option_value)
    elif option_name == "--suffixes":
        state.suffixes = _merged_suffixes(state, option_value)
        state.suffixes_provided = True
    elif option_name == "--exclude":
        state.exclusions.extend(_split_nonempty(option_value))
    elif option_name == "--color":
        state.color = _parse_color(option_value, state.ignore_errors_on_exit)
    elif option_name in {"--only", "--enable", "--disable"}:
        _apply_rule_selection_option(state, option_name, option_value)
    elif option_name in {"--minimum-priority", "--minimumpriority"}:
        state.rules.minimum_priority = _parse_priority(option_name, option_value, state.ignore_errors_on_exit)
    else:
        state.rules.maximum_priority = _parse_priority(option_name, option_value, state.ignore_errors_on_exit)


def _merged_suffixes(state: _ArgumentParseState, option_value: str) -> set[str]:
    normalized_suffixes = _normalized_suffixes(option_value)
    if not state.suffixes_provided:
        return normalized_suffixes
    return state.suffixes | normalized_suffixes


def _apply_rule_selection_option(state: _ArgumentParseState, option_name: str, option_value: str) -> None:
    values = _split_nonempty(option_value)
    if option_name == "--only":
        state.rules.only.extend(values)
    elif option_name == "--enable":
        state.rules.enable.extend(values)
    else:
        state.rules.disable.extend(values)


def _apply_boolean_option(state: _ArgumentParseState, option_name: str, option_value: str | None) -> None:
    if option_value is not None:
        raise CliError(f"Option does not accept a value: {option_name}", state.ignore_errors_on_exit)
    if option_name == "--ignore-tests":
        state.ignore_tests = True
    elif option_name == "--ignore-errors-on-exit":
        state.ignore_errors_on_exit = True
    elif option_name == "--verbose":
        state.verbose = True
    elif option_name == "--strict":
        state.strict = True
    else:
        state.ignore_violations_on_exit = True


def _finish_help_or_version_parsing(state: _ArgumentParseState) -> ParsedArguments:
    if state.positionals:
        raise CliError(f"Unexpected positional argument: {state.positionals[0]}", state.ignore_errors_on_exit)
    return ParsedArguments(
        paths=(),
        report_format="",
        suffixes=frozenset(state.suffixes),
        exclusions=tuple(state.exclusions),
        ignore_tests=state.ignore_tests,
        report_file=state.report_file,
        strict=state.strict,
        verbose=state.verbose,
        color=state.color,
        show_help=state.show_help,
        show_version=state.show_version,
        rule_selection=_rule_selection(state, rulesets=[]),
        exit_policy=_exit_policy(state),
    )


def _finish_analysis_parsing(state: _ArgumentParseState) -> ParsedArguments:
    if len(state.positionals) < 3:
        raise CliError(f"Missing required arguments: {REQUIRED_ARGUMENTS}", state.ignore_errors_on_exit)
    if len(state.positionals) > 3:
        raise CliError(f"Unexpected positional argument: {state.positionals[3]}", state.ignore_errors_on_exit)

    paths = _split_nonempty(state.positionals[0])
    if not paths:
        raise CliError("At least one input path is required", state.ignore_errors_on_exit)
    rulesets = _split_nonempty(state.positionals[2])
    if not rulesets:
        raise CliError("At least one ruleset is required", state.ignore_errors_on_exit)
    if state.rules.minimum_priority > state.rules.maximum_priority:
        raise CliError("Minimum priority must not exceed maximum priority.", state.ignore_errors_on_exit)
    return ParsedArguments(
        paths=tuple(paths),
        report_format=state.positionals[1],
        suffixes=frozenset(state.suffixes),
        exclusions=tuple(state.exclusions),
        ignore_tests=state.ignore_tests,
        report_file=state.report_file,
        strict=state.strict,
        verbose=state.verbose,
        color=state.color,
        show_help=False,
        show_version=False,
        rule_selection=_rule_selection(state, rulesets),
        exit_policy=_exit_policy(state),
    )


def _rule_selection(state: _ArgumentParseState, rulesets: list[str]) -> RuleSelection:
    return RuleSelection(
        rulesets=tuple(rulesets),
        only=tuple(state.rules.only),
        enable=tuple(state.rules.enable),
        disable=tuple(state.rules.disable),
        minimum_priority=state.rules.minimum_priority,
        maximum_priority=state.rules.maximum_priority,
    )


def _exit_policy(state: _ArgumentParseState) -> ExitPolicy:
    return ExitPolicy(
        ignore_errors_on_exit=state.ignore_errors_on_exit,
        ignore_violations_on_exit=state.ignore_violations_on_exit,
    )


def _split_option(argument: str) -> tuple[str, str | None]:
    option_name, separator, option_value = argument.partition("=")
    return option_name, option_value if separator else None


def _parse_priority(option_name: str, value: str, ignore_errors_on_exit: bool) -> int:
    try:
        priority = int(value)
    except ValueError as error:
        raise CliError(
            f"{option_name} expects a priority between 1 and 5, received '{value}'.",
            ignore_errors_on_exit,
        ) from error
    if not 1 <= priority <= 5:
        raise CliError(
            f"{option_name} expects a priority between 1 and 5, received '{value}'.",
            ignore_errors_on_exit,
        )
    return priority


def _parse_color(value: str, ignore_errors_on_exit: bool) -> str:
    color = value.casefold()
    if color in {"auto", "always", "never"}:
        return color
    raise CliError(
        f"--color expects auto, always, or never, received '{value}'.", ignore_errors_on_exit
    )


def _analyze(
    source_files: Sequence[Path], rules: Sequence[LoadedRule]
) -> tuple[list[Finding], list[ProcessingError]]:
    findings: list[Finding] = []
    processing_errors: list[ProcessingError] = []
    for source_file in source_files:
        try:
            with tokenize.open(source_file) as source_handle:
                source = source_handle.read()
            tree = ast.parse(source, filename=str(source_file))
        except SyntaxError as error:
            line = error.lineno or 1
            processing_errors.append(
                ProcessingError(source_file, line, f"Could not parse {source_file}: {error.msg}")
            )
            continue
        except (RecursionError, OSError, UnicodeError) as error:
            processing_errors.append(ProcessingError(source_file, 1, f"Could not process {source_file}: {error}"))
            continue
        try:
            findings.extend(_apply_suppressions(source, tree, _findings(source_file, source, tree, rules)))
        except SyntaxError as error:
            # ast.parse() above accepts some sources (e.g. duplicate parameter
            # names) that symtable.symtable() rejects; rules that build symbol
            # tables can hit this second, stricter parse.
            line = error.lineno or 1
            processing_errors.append(
                ProcessingError(source_file, line, f"Could not analyze {source_file}: {error.msg}")
            )
        except (RecursionError, tokenize.TokenError, ValueError, OSError, UnicodeError) as error:
            processing_errors.append(
                ProcessingError(source_file, 1, f"Could not process {source_file}: {error}")
            )
    return findings, processing_errors


def _render_report(
    report_format: str,
    findings: Sequence[Finding],
    processing_errors: Sequence[ProcessingError],
    color: bool,
) -> str:
    renderer = {
        "text": lambda: _text_report_with_color(findings, processing_errors, color),
        "xml": lambda: _xml_report(findings, processing_errors),
        "json": lambda: _json_report(findings, processing_errors),
        "html": lambda: _html_report(findings, processing_errors),
        "ansi": lambda: _text_report_with_color(findings, processing_errors, True),
        "github": lambda: _github_report(findings, processing_errors),
        "gitlab": lambda: _gitlab_report(findings, processing_errors),
        "checkstyle": lambda: _checkstyle_report(findings, processing_errors),
        "sarif": lambda: _sarif_report(findings, processing_errors),
    }
    return renderer[report_format.casefold()]()


def _ordered_findings(findings: Sequence[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda finding: (
            _report_path(finding.path),
            finding.line,
            finding.rule_name,
            finding.message,
            finding.context,
            finding.priority,
        ),
    )


def _ordered_errors(errors: Sequence[ProcessingError]) -> list[ProcessingError]:
    return sorted(errors, key=lambda error: (_report_path(error.path), error.line, error.message))


def _report_path(path: Path) -> str:
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def _finding_record(finding: Finding) -> dict[str, str | int | bool]:
    return {
        "path": _report_path(finding.path),
        "line": finding.line,
        "column": 1,
        "ruleName": finding.rule_name,
        "priority": finding.priority,
        "message": finding.message,
        "context": finding.context,
        "suppressed": finding.suppressed,
    }


def _error_record(error: ProcessingError) -> dict[str, str | int | bool]:
    return {
        "path": _report_path(error.path),
        "line": error.line,
        "column": 1,
        "ruleName": "ProcessingError",
        "priority": 1,
        "message": error.message,
        "context": "",
        "suppressed": False,
    }


def _json_report(findings: Sequence[Finding], processing_errors: Sequence[ProcessingError]) -> str:
    return json.dumps(
        {
            "tool": {"name": "messpy", "version": _messpy_version()},
            "findings": [_finding_record(finding) for finding in _ordered_findings(findings)],
            "errors": [_error_record(error) for error in _ordered_errors(processing_errors)],
        },
        indent=2,
    ) + "\n"


XML_ILLEGAL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _xml_safe_text(value: str) -> str:
    # XML does not allow most control characters, even when escaped.
    # Replace each one with a printable "\xHH" form.
    return XML_ILLEGAL_CHARACTERS.sub(lambda match: f"\\x{ord(match.group()):02x}", value)


def _xml_attribute_value(value: str | int | bool) -> str:
    return html_escape(_xml_safe_text(str(value)), quote=True)


def _xml_attributes(values: dict[str, str | int | bool]) -> str:
    return "".join(f' {name}="{_xml_attribute_value(value)}"' for name, value in values.items())


def _xml_report(findings: Sequence[Finding], processing_errors: Sequence[ProcessingError]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<messpy version="{_messpy_version()}">',
        f'  <tool name="messpy" version="{_messpy_version()}" />',
        "  <findings>",
    ]
    lines.extend(f"    <finding{_xml_attributes(_finding_record(finding))} />" for finding in _ordered_findings(findings))
    lines.extend(["  </findings>", "  <errors>"])
    lines.extend(f"    <error{_xml_attributes(_error_record(error))} />" for error in _ordered_errors(processing_errors))
    lines.extend(["  </errors>", "</messpy>"])
    return "\n".join(lines) + "\n"


def _html_report(findings: Sequence[Finding], processing_errors: Sequence[ProcessingError]) -> str:
    lines = [
        "<!DOCTYPE html>",
        '<html><head><meta charset="utf-8"><title>messpy report</title></head><body>',
        "<h1>messpy report</h1>",
        "<table><tr><th>Path</th><th>Line</th><th>Rule</th><th>Priority</th><th>Message</th><th>Context</th><th>State</th></tr>",
    ]
    for finding in _ordered_findings(findings):
        record = _finding_record(finding)
        lines.append(
            "<tr>"
            f"<td>{html_escape(str(record['path']))}</td><td>{record['line']}</td>"
            f"<td>{html_escape(str(record['ruleName']))}</td><td>{record['priority']}</td>"
            f"<td>{html_escape(str(record['message']))}</td><td>{html_escape(str(record['context']))}</td>"
            f"<td>{'suppressed' if record['suppressed'] else ''}</td></tr>"
        )
    lines.append("</table>")
    if processing_errors:
        lines.extend(
            [
                "<h2>Processing errors</h2>",
                "<table><tr><th>Path</th><th>Line</th><th>Rule</th><th>Message</th></tr>",
            ]
        )
        for error in _ordered_errors(processing_errors):
            record = _error_record(error)
            lines.append(
                f"<tr><td>{html_escape(str(record['path']))}</td><td>{record['line']}</td><td>ProcessingError</td>"
                f"<td>{html_escape(str(record['message']))}</td></tr>"
            )
        lines.append("</table>")
    lines.append("</body></html>")
    return "\n".join(lines) + "\n"


def _text_report_with_color(
    findings: Sequence[Finding], processing_errors: Sequence[ProcessingError], color: bool
) -> str:
    entries = [_colored_finding(finding, color) for finding in _ordered_findings(findings)]
    entries.extend(_colored_error(error, color) for error in _ordered_errors(processing_errors))
    return "" if not entries else "\n".join(entries) + "\n"


def _colored_finding(finding: Finding, color: bool) -> str:
    label = f"{finding.rule_name} [priority {finding.priority}]"
    if finding.suppressed:
        label += " [suppressed]"
    if color:
        label = f"\x1b[33m{label}\x1b[0m"
        message = f"\x1b[31m{finding.message}\x1b[0m"
    else:
        message = finding.message
    return f"{_report_path(finding.path)}:{finding.line}: {label} {message}"


def _colored_error(error: ProcessingError, color: bool) -> str:
    message = f"ProcessingError {error.message}"
    if color:
        message = f"\x1b[31m{message}\x1b[0m"
    return f"{_report_path(error.path)}:{error.line}: {message}"


def _github_escape(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C")


def _github_report(findings: Sequence[Finding], processing_errors: Sequence[ProcessingError]) -> str:
    lines = []
    for finding in _ordered_findings(findings):
        record = _finding_record(finding)
        title = _github_escape(f"{record['ruleName']} [priority {record['priority']}]")
        message = _github_escape(
            f"{record['message']} (context: {record['context']})"
            f"{' [suppressed]' if record['suppressed'] else ''}"
        )
        lines.append(
            f"::warning file={_github_escape(str(record['path']))},line={record['line']},col=1,title={title}::{message}"
        )
    for error in _ordered_errors(processing_errors):
        record = _error_record(error)
        lines.append(
            f"::error file={_github_escape(str(record['path']))},line={record['line']},col=1,title=ProcessingError::{_github_escape(str(record['message']))}"
        )
    return "" if not lines else "\n".join(lines) + "\n"


def _gitlab_severity(priority: int) -> str:
    return {1: "blocker", 2: "critical", 3: "major", 4: "minor", 5: "info"}[priority]


def _gitlab_entry(record: dict[str, str | int | bool]) -> dict[str, object]:
    path = str(record["path"])
    line = int(record["line"])
    rule_name = str(record["ruleName"])
    message = str(record["message"])
    fingerprint_input = f"{path}:{line}:1:{rule_name}:{message}".encode("utf-8")
    return {
        "type": "issue",
        "tool": {"name": "messpy", "version": _messpy_version()},
        "check_name": rule_name,
        "description": f"{message} (context: {record['context']})"
        f"{' [suppressed]' if record['suppressed'] else ''}",
        "fingerprint": fingerprint_input.hex(),
        "severity": _gitlab_severity(int(record["priority"])),
        "location": {"path": path, "lines": {"begin": line}},
        "priority": record["priority"],
        "context": record["context"],
        "suppressed": record["suppressed"],
    }


def _gitlab_report(findings: Sequence[Finding], processing_errors: Sequence[ProcessingError]) -> str:
    entries = [_gitlab_entry(_finding_record(finding)) for finding in _ordered_findings(findings)]
    entries.extend(_gitlab_entry(_error_record(error)) for error in _ordered_errors(processing_errors))
    return json.dumps(entries, indent=2) + "\n"


def _checkstyle_report(findings: Sequence[Finding], processing_errors: Sequence[ProcessingError]) -> str:
    records = [*(_finding_record(finding) for finding in _ordered_findings(findings))]
    records.extend(_error_record(error) for error in _ordered_errors(processing_errors))
    by_path: dict[str, list[dict[str, str | int | bool]]] = defaultdict(list)
    for record in records:
        by_path[str(record["path"])].append(record)
    lines = [f'<checkstyle tool="messpy" version="{_messpy_version()}">']
    for path in sorted(by_path):
        lines.append(f'  <file name="{_xml_attribute_value(path)}">')
        for record in by_path[path]:
            severity = "error" if int(record["priority"]) <= 2 else "warning"
            source = f"messpy.{record['ruleName']}"
            lines.append(
                "    <error"
                f' line="{record["line"]}" column="1" severity="{severity}"'
                f' message="{_xml_attribute_value(record["message"])}"'
                f' source="{_xml_attribute_value(source)}"'
                f' context="{_xml_attribute_value(record["context"])}"'
                f' priority="{record["priority"]}" suppressed="{str(record["suppressed"]).lower()}" />'
            )
        lines.append("  </file>")
    lines.append("</checkstyle>")
    return "\n".join(lines) + "\n"


def _sarif_level(priority: int) -> str:
    return "error" if priority <= 2 else "warning"


def _sarif_location(record: dict[str, str | int | bool]) -> dict[str, object]:
    return {
        "physicalLocation": {
            "artifactLocation": {"uri": record["path"]},
            "region": {"startLine": record["line"], "startColumn": 1},
        }
    }


def _sarif_report(findings: Sequence[Finding], processing_errors: Sequence[ProcessingError]) -> str:
    ordered_findings = _ordered_findings(findings)
    rules = sorted({finding.rule_name for finding in ordered_findings})
    results = []
    for finding in ordered_findings:
        record = _finding_record(finding)
        result: dict[str, object] = {
            "ruleId": record["ruleName"],
            "level": _sarif_level(int(record["priority"])),
            "message": {"text": record["message"]},
            "locations": [_sarif_location(record)],
            "properties": {
                "priority": record["priority"],
                "context": record["context"],
                "suppressed": record["suppressed"],
            },
        }
        if record["suppressed"]:
            result["suppressions"] = [{"kind": "inSource"}]
        results.append(result)
    notifications = []
    for error in _ordered_errors(processing_errors):
        record = _error_record(error)
        notifications.append(
            {
                "level": "error",
                "message": {"text": f"{record['path']}:{record['line']}:1: {record['message']}"},
                "locations": [_sarif_location(record)],
            }
        )
    invocation: dict[str, object] = {"executionSuccessful": not processing_errors}
    if notifications:
        invocation["toolExecutionNotifications"] = notifications
    report = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "messpy",
                        "version": _messpy_version(),
                        "rules": [
                            {"id": name, "name": name, "shortDescription": {"text": name}}
                            for name in rules
                        ],
                    }
                },
                "results": results,
                "invocations": [invocation],
            }
        ],
    }
    return json.dumps(report, indent=2) + "\n"


def _use_color(parsed_arguments: ParsedArguments, stdout: TextIO) -> bool:
    if parsed_arguments.report_format.casefold() == "ansi":
        return True
    if parsed_arguments.report_format.casefold() != "text" or parsed_arguments.report_file is not None:
        return False
    if parsed_arguments.color == "always":
        return True
    if parsed_arguments.color == "never":
        return False
    return bool(getattr(stdout, "isatty", lambda: False)())


def _destination_file_mode(report_file: Path) -> int:
    try:
        return stat.S_IMODE(report_file.stat().st_mode)
    except OSError:
        current_umask = os.umask(0)
        try:
            return 0o666 & ~current_umask
        finally:
            os.umask(current_umask)


def _write_report(report_file: Path, report: str) -> None:
    temporary_file: Path | None = None
    try:
        target_mode = _destination_file_mode(report_file)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=report_file.parent,
            prefix=f".{report_file.name}.",
            delete=False,
        ) as output:
            temporary_file = Path(output.name)
            output.write(report)
        temporary_file.chmod(target_mode)
        temporary_file.replace(report_file)
    except OSError as error:
        if temporary_file is not None:
            temporary_file.unlink(missing_ok=True)
        raise CliError(f"Unable to write report {report_file}: {error}") from error


def _exit_status(
    findings: Sequence[Finding],
    processing_errors: Sequence[str],
    ignore_errors_on_exit: bool,
    ignore_violations_on_exit: bool,
) -> int:
    if processing_errors and not ignore_errors_on_exit:
        return 1
    if findings and not ignore_violations_on_exit:
        return 2
    return 0


def _findings(path: Path, source: str, tree: ast.Module, rules: Sequence[LoadedRule]) -> list[Finding]:
    rule_names = frozenset(rule.name for rule in rules)
    classes = _selected_classes(tree, rule_names)
    callables = _selected_callables(tree, rule_names)
    function_scopes = _selected_function_scopes(source, tree, rule_names)
    protocol_method_ids = _selected_protocol_method_ids(tree, rule_names)
    comprehension_scopes = _selected_comprehension_scopes(source, tree, rule_names)
    private_member_usage = _selected_private_member_usage(tree, rule_names)
    clean_code_callables = _selected_clean_code_callables(tree, rule_names)
    return [
        *_cyclomatic_complexity_findings(path, callables, rules),
        *_npath_complexity_findings(path, callables, rules),
        *_excessive_method_length_findings(path, callables, rules),
        *_excessive_parameter_list_findings(path, callables, rules),
        *_selected_class_findings(path, source, classes, rules, rule_names),
        *_selected_naming_findings(path, tree, rules, rule_names),
        *_unused_local_variable_findings(path, rules, function_scopes, comprehension_scopes, protocol_method_ids),
        *_unused_formal_parameter_findings(path, tree, rules, function_scopes, protocol_method_ids),
        *_unused_private_field_findings(path, tree, classes, rules, private_member_usage),
        *_unused_private_method_findings(path, classes, rules, private_member_usage),
        *_selected_clean_code_findings(path, source, tree, rules, rule_names, clean_code_callables),
        *_selected_design_findings(path, source, tree, classes, rules, rule_names, clean_code_callables),
    ]


def _selected_classes(tree: ast.Module, rule_names: AbstractSet[str]) -> list[ClassInfo]:
    class_rules = CLASS_CODE_SIZE_RULE_NAMES | {
        UNUSED_PRIVATE_FIELD_RULE_NAME,
        UNUSED_PRIVATE_METHOD_RULE_NAME,
        COUPLING_BETWEEN_OBJECTS_RULE_NAME,
        LACK_OF_COHESION_RULE_NAME,
    }
    if not _has_any_rule(rule_names, class_rules):
        return []
    return _classes(tree)


def _selected_callables(tree: ast.Module, rule_names: AbstractSet[str]) -> list[CallableInfo]:
    callable_rules = {
        CYCLOMATIC_COMPLEXITY_RULE_NAME,
        NPATH_COMPLEXITY_RULE_NAME,
        METHOD_LENGTH_RULE_NAME,
        EXCESSIVE_PARAMETER_LIST_RULE_NAME,
    }
    if not _has_any_rule(rule_names, callable_rules):
        return []
    return _callables(tree)


def _selected_function_scopes(
    source: str, tree: ast.Module, rule_names: AbstractSet[str]
) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda, symtable.SymbolTable, frozenset[str]]]:
    if not _has_any_rule(rule_names, {UNUSED_LOCAL_VARIABLE_RULE_NAME, UNUSED_FORMAL_PARAMETER_RULE_NAME}):
        return []
    return _function_scopes(source, tree)


def _selected_protocol_method_ids(tree: ast.Module, rule_names: AbstractSet[str]) -> set[int]:
    if not _has_any_rule(rule_names, {UNUSED_LOCAL_VARIABLE_RULE_NAME, UNUSED_FORMAL_PARAMETER_RULE_NAME}):
        return set()
    return _protocol_method_ids(tree)


def _selected_comprehension_scopes(
    source: str, tree: ast.Module, rule_names: AbstractSet[str]
) -> list[
    tuple[
        ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
        symtable.SymbolTable | None,
    ]
]:
    if UNUSED_LOCAL_VARIABLE_RULE_NAME not in rule_names:
        return []
    return _comprehension_scopes(source, tree)


def _selected_private_member_usage(
    tree: ast.Module, rule_names: AbstractSet[str]
) -> PrivateMemberUsage | None:
    private_member_rules = {UNUSED_PRIVATE_FIELD_RULE_NAME, UNUSED_PRIVATE_METHOD_RULE_NAME}
    if not _has_any_rule(rule_names, private_member_rules):
        return None
    return _private_member_usage(tree)


def _selected_clean_code_callables(
    tree: ast.Module, rule_names: AbstractSet[str]
) -> list[CleanCodeCallable]:
    callable_rules = {
        BOOLEAN_ARGUMENT_FLAG_RULE_NAME,
        ELSE_EXPRESSION_RULE_NAME,
        STATIC_ACCESS_RULE_NAME,
        EXIT_EXPRESSION_RULE_NAME,
        COUNT_IN_LOOP_EXPRESSION_RULE_NAME,
        DEVELOPMENT_CODE_FRAGMENT_RULE_NAME,
        EMPTY_CATCH_BLOCK_RULE_NAME,
    }
    if not _has_any_rule(rule_names, callable_rules):
        return []
    return _clean_code_callables(tree)


def _selected_class_findings(
    path: Path,
    source: str,
    classes: Sequence[ClassInfo],
    rules: Sequence[LoadedRule],
    rule_names: AbstractSet[str],
) -> list[Finding]:
    if not _has_any_rule(rule_names, CLASS_CODE_SIZE_RULE_NAMES):
        return []
    return _class_findings(path, source.splitlines(), classes, rules)


def _selected_naming_findings(
    path: Path,
    tree: ast.Module,
    rules: Sequence[LoadedRule],
    rule_names: AbstractSet[str],
) -> list[Finding]:
    if not _has_any_rule(rule_names, NAMING_RULE_NAMES):
        return []
    return _naming_findings(path, tree, rules)


def _selected_clean_code_findings(
    path: Path,
    source: str,
    tree: ast.Module,
    rules: Sequence[LoadedRule],
    rule_names: AbstractSet[str],
    clean_code_callables: Sequence[CleanCodeCallable],
) -> list[Finding]:
    if not _has_any_rule(rule_names, CLEAN_CODE_RULE_NAMES):
        return []
    return _clean_code_findings(path, source, tree, rules, clean_code_callables)


def _selected_design_findings(
    path: Path,
    source: str,
    tree: ast.Module,
    classes: Sequence[ClassInfo],
    rules: Sequence[LoadedRule],
    rule_names: AbstractSet[str],
    clean_code_callables: Sequence[CleanCodeCallable],
) -> list[Finding]:
    if not _has_any_rule(rule_names, DESIGN_RULE_NAMES):
        return []
    return _design_findings(path, source, tree, classes, rules, rule_names, clean_code_callables)


def _design_findings(
    path: Path,
    source: str,
    tree: ast.Module,
    classes: Sequence[ClassInfo],
    rules: Sequence[LoadedRule],
    rule_names: AbstractSet[str],
    clean_code_callables: Sequence[CleanCodeCallable],
) -> list[Finding]:
    parents = _selected_design_parents(tree, rule_names)
    contexts = _selected_design_contexts(clean_code_callables, rule_names)
    bindings = _selected_design_bindings(tree, rule_names)
    return [
        *_exit_expression_findings(path, tree, rules, parents, contexts, bindings),
        *_count_in_loop_findings(path, tree, rules, parents, contexts, bindings),
        *_development_fragment_findings(path, source, tree, rules, parents, contexts, bindings),
        *_empty_catch_findings(path, tree, rules, parents, contexts),
        *_coupling_findings(path, tree, classes, rules),
        *_global_variable_findings(path, tree, rules, parents, bindings),
        *_cohesion_findings(path, classes, rules),
    ]


def _selected_design_parents(tree: ast.Module, rule_names: AbstractSet[str]) -> dict[int, ast.AST]:
    parent_rules = {
        EXIT_EXPRESSION_RULE_NAME,
        COUNT_IN_LOOP_EXPRESSION_RULE_NAME,
        DEVELOPMENT_CODE_FRAGMENT_RULE_NAME,
        EMPTY_CATCH_BLOCK_RULE_NAME,
        GLOBAL_VARIABLE_RULE_NAME,
    }
    if not _has_any_rule(rule_names, parent_rules):
        return {}
    return {id(child): parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _selected_design_contexts(
    clean_code_callables: Sequence[CleanCodeCallable], rule_names: AbstractSet[str]
) -> dict[int, str]:
    context_rules = {
        EXIT_EXPRESSION_RULE_NAME,
        COUNT_IN_LOOP_EXPRESSION_RULE_NAME,
        DEVELOPMENT_CODE_FRAGMENT_RULE_NAME,
        EMPTY_CATCH_BLOCK_RULE_NAME,
    }
    if not _has_any_rule(rule_names, context_rules):
        return {}
    return {
        id(callable_info.node): _clean_code_context(callable_info)
        for callable_info in clean_code_callables
    }


def _selected_design_bindings(tree: ast.Module, rule_names: AbstractSet[str]) -> dict[int, set[str]]:
    binding_rules = {
        EXIT_EXPRESSION_RULE_NAME,
        COUNT_IN_LOOP_EXPRESSION_RULE_NAME,
        DEVELOPMENT_CODE_FRAGMENT_RULE_NAME,
        GLOBAL_VARIABLE_RULE_NAME,
    }
    if not _has_any_rule(rule_names, binding_rules):
        return {}
    return _scope_bindings(tree)


_BindingScope = ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda


@dataclass(frozen=True)
class _ScopeCallImports:
    """The call-relevant imports and the other name bindings of one scope."""

    call_modules: dict[str, str]
    rebound: set[str]


def _exit_expression_findings(
    path: Path,
    tree: ast.Module,
    rules: Sequence[LoadedRule],
    parents: dict[int, ast.AST],
    contexts: dict[int, str],
    bindings: dict[int, set[str]],
) -> list[Finding]:
    rule = _rule(rules, EXIT_EXPRESSION_RULE_NAME)
    if rule is None:
        return []
    aliases = _imported_call_aliases(tree)
    reported_scopes: set[int] = set()
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_exit_call(node, tree, aliases, parents, bindings):
            continue
        scope, context = _design_scope(node, parents, contexts)
        if id(scope) in reported_scopes:
            continue
        reported_scopes.add(id(scope))
        findings.append(
            Finding(
                path,
                node.lineno,
                rule.name,
                rule.priority,
                f"The {context} contains an exit expression.",
                context=context,
            )
        )
    return findings


def _is_exit_call(
    node: ast.Call,
    tree: ast.Module,
    aliases: dict[int, _ScopeCallImports],
    parents: dict[int, ast.AST],
    bindings: dict[int, set[str]],
) -> bool:
    name = _resolved_call_name(node, tree, aliases, parents, bindings)
    return name in EXIT_CALL_NAMES


def _resolved_call_name(
    node: ast.Call,
    tree: ast.Module,
    aliases: dict[int, _ScopeCallImports],
    parents: dict[int, ast.AST],
    bindings: dict[int, set[str]],
) -> str:
    original_name = _dotted_name(node.func)
    root_name = original_name.split(".", 1)[0]
    attributes = original_name[len(root_name):]
    for scope in _enclosing_scopes(node, tree, parents):
        imports = aliases[id(scope)]
        if root_name in imports.rebound:
            return ""
        if root_name in imports.call_modules:
            return f"{imports.call_modules[root_name]}{attributes}"
        if root_name in bindings[id(scope)]:
            return ""
    return original_name


def _enclosing_scopes(
    node: ast.AST, tree: ast.Module, parents: dict[int, ast.AST]
) -> list[ast.AST]:
    # The scopes that hold the call, from the innermost function out to the module.
    scopes: list[ast.AST] = []
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            scopes.append(current)
    scopes.append(tree)
    return scopes


def _count_in_loop_findings(
    path: Path,
    tree: ast.Module,
    rules: Sequence[LoadedRule],
    parents: dict[int, ast.AST],
    contexts: dict[int, str],
    bindings: dict[int, set[str]],
) -> list[Finding]:
    rule = _rule(rules, COUNT_IN_LOOP_EXPRESSION_RULE_NAME)
    if rule is None:
        return []
    findings: list[Finding] = []
    for loop in ast.walk(tree):
        if not isinstance(loop, ast.While):
            continue
        calls = _expression_calls(loop.test)
        length_call = next(
            (call for call in calls if isinstance(call.func, ast.Name) and call.func.id == "len"),
            None,
        )
        if length_call is None or _is_shadowed("len", length_call, tree, parents, bindings):
            continue
        _, context = _design_scope(loop, parents, contexts)
        findings.append(
            Finding(
                path,
                length_call.lineno,
                rule.name,
                rule.priority,
                "Avoid using len() in while loops.",
                context=context,
            )
        )
    return findings


def _development_fragment_findings(
    path: Path,
    source: str,
    tree: ast.Module,
    rules: Sequence[LoadedRule],
    parents: dict[int, ast.AST],
    contexts: dict[int, str],
    bindings: dict[int, set[str]],
) -> list[Finding]:
    rule = _rule(rules, DEVELOPMENT_CODE_FRAGMENT_RULE_NAME)
    if rule is None:
        return []
    unwanted = DEVELOPMENT_CALL_NAMES | {
        name.strip()
        for name in rule.properties.get("unwanted-functions", "").split(",")
        if name.strip()
    }
    findings = _development_call_findings(path, tree, rule, unwanted, parents, contexts, bindings)
    findings.extend(_development_marker_findings(path, source, rule))
    return findings


def _development_call_findings(
    path: Path,
    tree: ast.Module,
    rule: LoadedRule,
    unwanted: set[str],
    parents: dict[int, ast.AST],
    contexts: dict[int, str],
    bindings: dict[int, set[str]],
) -> list[Finding]:
    findings: list[Finding] = []
    aliases = _imported_call_aliases(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _dotted_name(node.func)
        resolved = _resolved_call_name(node, tree, aliases, parents, bindings)
        if resolved in DEVELOPMENT_CALL_NAMES:
            name = resolved
        elif name not in unwanted or name == "breakpoint":
            # A bare `breakpoint` that resolution could not pin on the builtins
            # module is a user-defined or rebound name, so it stays quiet.
            continue
        _, context = _design_scope(node, parents, contexts)
        subject = "The module" if context == "module" else f"The {context}"
        findings.append(
            Finding(
                path,
                node.lineno,
                rule.name,
                rule.priority,
                f"{subject} calls the typical debug function {name}() which is mostly only used during development.",
                context=context,
            )
        )
    return findings


def _development_marker_findings(path: Path, source: str, rule: LoadedRule) -> list[Finding]:
    markers = [
        marker.strip().casefold()
        for marker in rule.properties.get("markers", "TODO,FIXME,HACK").split(",")
        if marker.strip()
    ]
    if not markers:
        return []
    marker_pattern = re.compile(
        "|".join(rf"\b{re.escape(marker)}\b" for marker in markers),
        re.IGNORECASE,
    )
    return [
        Finding(
            path,
            item.start[0],
            rule.name,
            rule.priority,
            "Development-only marker found in production source.",
            context="module",
        )
        for item in tokenize.generate_tokens(StringIO(source).readline)
        if item.type == token.COMMENT and marker_pattern.search(item.string)
    ]


def _empty_catch_findings(
    path: Path,
    tree: ast.Module,
    rules: Sequence[LoadedRule],
    parents: dict[int, ast.AST],
    contexts: dict[int, str],
) -> list[Finding]:
    rule = _rule(rules, EMPTY_CATCH_BLOCK_RULE_NAME)
    if rule is None:
        return []
    findings: list[Finding] = []
    for handler in ast.walk(tree):
        if not isinstance(handler, ast.ExceptHandler) or not _is_empty_handler(handler):
            continue
        _, context = _design_scope(handler, parents, contexts)
        findings.append(
            Finding(
                path,
                handler.lineno,
                rule.name,
                rule.priority,
                f"Avoid using empty exception handlers in {context}.",
                context=context,
            )
        )
    return findings


def _is_empty_handler(handler: ast.ExceptHandler) -> bool:
    if len(handler.body) != 1:
        return False
    statement = handler.body[0]
    return isinstance(statement, ast.Pass) or (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and statement.value.value is Ellipsis
    )


def _coupling_findings(
    path: Path,
    tree: ast.Module,
    classes: Sequence[ClassInfo],
    rules: Sequence[LoadedRule],
) -> list[Finding]:
    rule = _rule(rules, COUPLING_BETWEEN_OBJECTS_RULE_NAME)
    if rule is None:
        return []
    maximum = _integer_property(rule, "maximum")
    aliases = _module_import_aliases(tree)
    module_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    findings: list[Finding] = []
    for class_info in classes:
        count = len(_class_dependencies(class_info, aliases, module_names))
        if count < maximum:
            continue
        findings.append(
            _class_finding(
                path,
                class_info,
                rule,
                f"The class {class_info.name} has a coupling between objects value of {count}. "
                f"Consider to reduce the number of dependencies under {maximum}.",
            )
        )
    return findings


def _class_dependencies(
    class_info: ClassInfo,
    aliases: dict[str, tuple[str, bool]],
    module_names: set[str],
) -> set[str]:
    local_names = {
        class_info.name,
        *module_names,
        *class_info.fields,
        *(method.name for method in class_info.methods),
    }
    collector = _DependencyCollector(aliases, local_names)
    for expression in [*class_info.node.bases, *class_info.node.decorator_list]:
        collector.visit(expression)
    for statement in class_info.node.body:
        if not isinstance(statement, ast.ClassDef):
            collector.visit(statement)
    dependencies = collector.dependencies
    if class_info.is_ast_visitor:
        dependencies = {dependency for dependency in dependencies if not dependency.startswith("ast.")}
    return dependencies


def _module_import_aliases(tree: ast.Module) -> dict[str, tuple[str, bool]]:
    aliases: dict[str, tuple[str, bool]] = {}
    for statement in tree.body:
        if isinstance(statement, ast.Import):
            for item in statement.names:
                binding = item.asname or item.name.split(".", 1)[0]
                target = item.name if item.asname else binding
                aliases[binding] = (target, False)
        elif isinstance(statement, ast.ImportFrom):
            module = _import_from_module(statement)
            for item in statement.names:
                aliases[item.asname or item.name] = (_imported_name(module, item.name), True)
    return aliases


def _import_from_module(node: ast.ImportFrom) -> str:
    return f"{'.' * node.level}{node.module or ''}"


def _imported_name(module: str, name: str) -> str:
    separator = "" if module.endswith(".") else "."
    return f"{module}{separator}{name}"


class _DependencyCollector(ast.NodeVisitor):
    def __init__(self, aliases: dict[str, tuple[str, bool]], local_names: set[str]) -> None:
        self.aliases = dict(aliases)
        self.local_names = local_names
        self.dependencies: set[str] = set()

    def visit_arg(self, node: ast.arg) -> None:
        self._visit_annotation(node.annotation)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._visit_annotation(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def _visit_annotation(self, annotation: ast.expr | None) -> None:
        expression = _annotation_expression(annotation)
        if expression is not None:
            self.visit(expression)
    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self._add(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            binding = item.asname or item.name.split(".", 1)[0]
            target = item.name if item.asname else binding
            self.aliases[binding] = (target, False)
            self.local_names.discard(binding)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = _import_from_module(node)
        for item in node.names:
            dependency = _imported_name(module, item.name)
            binding = item.asname or item.name
            self.aliases[binding] = (dependency, True)
            self.local_names.discard(binding)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        name = _dotted_name(node)
        if name:
            self._add(name)
        else:
            self.generic_visit(node)

    def visit_ClassDef(self, _node: ast.ClassDef) -> None:
        return

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        outer_names = self.local_names
        outer_aliases = self.aliases
        scope_names = {
            *(argument.arg for argument in _arguments(node.args)),
            *_direct_bindings(node),
        }
        self.local_names = outer_names | scope_names
        self.aliases = {
            name: alias for name, alias in outer_aliases.items() if name not in scope_names
        }
        try:
            for decorator in node.decorator_list:
                self.visit(decorator)
            for argument in _arguments(node.args):
                self.visit_arg(argument)
            for default in [*node.args.defaults, *node.args.kw_defaults]:
                if default is not None:
                    self.visit(default)
            self._visit_annotation(node.returns)
            for statement in node.body:
                self.visit(statement)
        finally:
            self.local_names = outer_names
            self.aliases = outer_aliases

    def _add(self, name: str) -> None:
        root, *tail = name.split(".")
        if root in self.local_names or root in dir(builtins) or root == "typing":
            return
        if root in self.aliases:
            imported, is_symbol = self.aliases[root]
            dependency = imported if is_symbol else ".".join([imported, *tail[:1]])
        elif tail:
            dependency = ".".join([root, *tail[:1]])
        elif root[:1].isupper():
            dependency = root
        else:
            return
        if not dependency.startswith(("typing.", "collections.abc.")):
            self.dependencies.add(dependency)


def _annotation_expression(annotation: ast.expr | None) -> ast.expr | None:
    if not isinstance(annotation, ast.Constant) or not isinstance(annotation.value, str):
        return annotation
    try:
        return ast.parse(annotation.value, mode="eval").body
    except (SyntaxError, RecursionError):
        return None


def _global_variable_findings(
    path: Path,
    tree: ast.Module,
    rules: Sequence[LoadedRule],
    parents: dict[int, ast.AST],
    bindings: dict[int, set[str]],
) -> list[Finding]:
    rule = _rule(rules, GLOBAL_VARIABLE_RULE_NAME)
    if rule is None:
        return []
    candidates, immutable_candidates, initial_targets = _global_candidates(tree)
    mutated = _mutated_global_names(tree, candidates, initial_targets, parents, bindings)
    selected = set(candidates) if _boolean_property(rule, "report-immutable") else mutated - immutable_candidates
    return [
        Finding(
            path,
            candidates[name].lineno,
            rule.name,
            rule.priority,
            f"Avoid using static mutable state: {name}.",
            context=name,
        )
        for name in sorted(selected, key=lambda item: candidates[item].lineno)
    ]


def _global_candidates(tree: ast.Module) -> tuple[dict[str, ast.Name], set[str], set[int]]:
    candidates: dict[str, ast.Name] = {}
    immutable_candidates: set[str] = set()
    initial_targets: set[int] = set()
    collector = _ModuleBindingCollector()
    collector.visit(tree)
    for target, annotation in collector.bindings:
        for name in _target_names(target):
            if name.id in candidates:
                continue
            candidates[name.id] = name
            initial_targets.add(id(name))
            if annotation is not None and _is_final_annotation(annotation):
                immutable_candidates.add(name.id)
    return candidates, immutable_candidates, initial_targets


def _mutated_global_names(
    tree: ast.Module,
    candidates: dict[str, ast.Name],
    initial_targets: set[int],
    parents: dict[int, ast.AST],
    bindings: dict[int, set[str]],
) -> set[str]:
    mutators = {"add", "append", "clear", "discard", "extend", "insert", "pop", "remove", "reverse", "sort", "update"}
    return {
        name
        for node in ast.walk(tree)
        if (name := _mutated_global_name(node, candidates, initial_targets, parents, bindings, mutators))
    }


def _mutated_global_name(
    node: ast.AST,
    candidates: dict[str, ast.Name],
    initial_targets: set[int],
    parents: dict[int, ast.AST],
    bindings: dict[int, set[str]],
    mutators: set[str],
) -> str:
    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        return node.id if _is_mutated_module_name(node, candidates, initial_targets, parents) else ""
    if isinstance(node, (ast.Attribute, ast.Subscript)) and isinstance(node.ctx, (ast.Store, ast.Del)):
        return _unshadowed_candidate_root(node, candidates, parents, bindings)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in mutators:
        return _unshadowed_candidate_root(node.func.value, candidates, parents, bindings)
    return ""


def _is_mutated_module_name(
    node: ast.Name,
    candidates: dict[str, ast.Name],
    initial_targets: set[int],
    parents: dict[int, ast.AST],
) -> bool:
    return id(node) not in initial_targets and node.id in candidates and _is_module_assignment(node, parents)


def _unshadowed_candidate_root(
    node: ast.AST,
    candidates: dict[str, ast.Name],
    parents: dict[int, ast.AST],
    bindings: dict[int, set[str]],
) -> str:
    root = _root_name(node)
    return root if root in candidates and not _is_function_shadowed(root, node, parents, bindings) else ""


class _ModuleBindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.bindings: list[tuple[ast.AST, ast.expr | None]] = []

    def visit_Assign(self, node: ast.Assign) -> None:
        self.bindings.extend((target, None) for target in node.targets)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.bindings.append((node.target, node.annotation))
            self.visit(node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.bindings.append((node.target, None))
        self.visit(node.value)

    def visit_FunctionDef(self, _node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, _node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, _node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return


def _is_module_assignment(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return _scope_declares_global(node, current, parents)
    return True


def _scope_declares_global(node: ast.AST, scope: ast.AST, parents: dict[int, ast.AST]) -> bool:
    return isinstance(node, ast.Name) and any(
        isinstance(statement, ast.Global)
        and node.id in statement.names
        and _same_scope(statement, scope, parents)
        for statement in ast.walk(scope)
    )


def _same_scope(node: ast.AST, scope: ast.AST, parents: dict[int, ast.AST]) -> bool:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if current is scope:
            return True
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            return False
    return False


def _root_name(node: ast.AST) -> str:
    current = node
    while isinstance(current, (ast.Attribute, ast.Subscript)):
        current = current.value
    return current.id if isinstance(current, ast.Name) else ""


def _cohesion_findings(
    path: Path, classes: Sequence[ClassInfo], rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, LACK_OF_COHESION_RULE_NAME)
    if rule is None:
        return []
    maximum = _integer_property(rule, "maximum")
    findings: list[Finding] = []
    for class_info in classes:
        lcom = _lcom4(class_info)
        if lcom <= maximum:
            continue
        findings.append(
            _class_finding(
                path,
                class_info,
                rule,
                f"The class {class_info.name} has a Lack of Cohesion Of Methods (LCOM4) value of {lcom}. "
                f"Consider to split this class into {lcom} smaller classes.",
            )
        )
    return findings


def _lcom4(class_info: ClassInfo) -> int:
    accessor_fields = _accessor_fields(class_info)
    methods = _method_relationships(class_info, accessor_fields)
    active = _active_methods(methods)
    if not active:
        return 1
    return _relationship_component_count(methods, active)


def _method_relationships(
    class_info: ClassInfo, accessor_fields: dict[str, str]
) -> dict[str, _MethodRelationships]:
    methods: dict[str, _MethodRelationships] = {}
    for method in class_info.methods:
        if _excluded_from_cohesion(method, accessor_fields):
            continue
        receiver = _instance_receiver(method)
        if receiver is None:
            continue
        collector = _MethodRelationshipCollector(receiver, accessor_fields)
        for statement in method.body:
            collector.visit(statement)
        methods[method.name] = _MethodRelationships(collector.fields, collector.calls)
    return methods


def _excluded_from_cohesion(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
    accessor_fields: dict[str, str],
) -> bool:
    return (
        method.name.startswith("__")
        or _has_property_decorator(method)
        or _has_decorator(method, "staticmethod")
        or _has_decorator(method, "classmethod")
        or _is_contract_method(method)
        or _has_decorator(method, "abstractmethod")
        or method.name in accessor_fields
    )


def _active_methods(methods: dict[str, _MethodRelationships]) -> set[str]:
    active = {
        name
        for name, relationships in methods.items()
        if relationships.fields or relationships.calls & methods.keys()
    }
    active.update(
        called
        for relationships in methods.values()
        for called in relationships.calls
        if called in methods
    )
    return active


def _relationship_component_count(
    methods: dict[str, _MethodRelationships], active: set[str]
) -> int:
    connected = {name: name for name in active}
    methods_by_field: defaultdict[str, list[str]] = defaultdict(list)
    for name in active:
        for field in methods[name].fields:
            methods_by_field[field].append(name)
    for names in methods_by_field.values():
        first, *connected_names = names
        for name in connected_names:
            _union_components(connected, first, name)
    names = sorted(active)
    for name in names:
        for called in methods[name].calls & active:
            _union_components(connected, name, called)
    return len({_find_component(connected, name) for name in active})


def _find_component(connected: dict[str, str], name: str) -> str:
    while connected[name] != name:
        connected[name] = connected[connected[name]]
        name = connected[name]
    return name


def _union_components(connected: dict[str, str], left: str, right: str) -> None:
    connected[_find_component(connected, left)] = _find_component(connected, right)


@dataclass(frozen=True)
class _MethodRelationships:
    fields: frozenset[str]
    calls: frozenset[str]


class _MethodRelationshipCollector(ast.NodeVisitor):
    def __init__(self, receiver: str, accessor_fields: dict[str, str]) -> None:
        self.receiver = receiver
        self.accessor_fields = accessor_fields
        self.fields: frozenset[str] = frozenset()
        self.calls: frozenset[str] = frozenset()

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == self.receiver
        ):
            if node.func.attr in self.accessor_fields:
                self.fields = self.fields | {self.accessor_fields[node.func.attr]}
            else:
                self.calls = self.calls | {node.func.attr}
            for argument in [*node.args, *node.keywords]:
                self.visit(argument.value if isinstance(argument, ast.keyword) else argument)
            return
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.value, ast.Name) and node.value.id == self.receiver:
            self.fields = self.fields | {self.accessor_fields.get(node.attr, node.attr)}
            return
        self.generic_visit(node)

    def visit_FunctionDef(self, _node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, _node: ast.AsyncFunctionDef) -> None:
        return

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return


def _accessor_fields(class_info: ClassInfo) -> dict[str, str]:
    return {
        method.name: field
        for method in class_info.methods
        if (field := _trivial_accessor_field(method)) is not None
    }


def _trivial_accessor_field(method: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    if len(method.body) != 1:
        return None
    statement = method.body[0]
    target = _accessor_target(statement, method)
    if (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == "self"
    ):
        return target.attr
    return None


def _accessor_target(statement: ast.stmt, method: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.expr | None:
    if isinstance(statement, ast.Return):
        return statement.value
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        return statement.targets[0] if _is_plain_accessor_value(statement.value, method) else None
    if isinstance(statement, ast.AnnAssign) and statement.value is not None:
        return statement.target if _is_plain_accessor_value(statement.value, method) else None
    return None


def _is_plain_accessor_value(value: ast.expr, method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    receiver = _instance_receiver(method)
    return (
        isinstance(value, ast.Name)
        and value.id != receiver
        and value.id in {argument.arg for argument in _arguments(method.args)}
    )


def _design_scope(
    node: ast.AST, parents: dict[int, ast.AST], contexts: dict[int, str]
) -> tuple[ast.AST, str]:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return current, contexts.get(id(current), "<lambda>")
    return current, "module"


def _expression_calls(node: ast.expr) -> list[ast.Call]:
    collector = _ExpressionCallCollector()
    collector.visit(node)
    return collector.calls


class _ExpressionCallCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[ast.Call] = []

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return


def _dotted_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else ""
    return ""


def _imported_call_aliases(tree: ast.Module) -> dict[int, _ScopeCallImports]:
    return {id(scope): _scope_call_imports(scope) for scope in _binding_scopes(tree)}


def _scope_call_imports(scope: _BindingScope) -> _ScopeCallImports:
    imports = _CallImportCollector()
    rebindings = _ScopeRebindingCollector()
    for statement in _scope_statements(scope):
        imports.visit(statement)
        rebindings.visit(statement)
    return _ScopeCallImports(call_modules=imports.names, rebound=rebindings.names)


class _CallImportCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:
        self.names.update(_call_import_aliases(node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module in {"sys", "os", "builtins", "pdb"}:
            self.names.update(_call_import_from_aliases(node))

    def visit_FunctionDef(self, _node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, _node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, _node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return


class _ScopeRebindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Import(self, _node: ast.Import) -> None:
        return

    def visit_ImportFrom(self, _node: ast.ImportFrom) -> None:
        return

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            self.names.add(node.id)
        _record_pattern_binding(self.names, node)
        super().generic_visit(node)


def _call_import_aliases(statement: ast.Import) -> dict[str, str]:
    return {
        imported.asname or imported.name: imported.name
        for imported in statement.names
        if imported.name in {"sys", "os", "builtins", "pdb"}
    }


def _call_import_from_aliases(statement: ast.ImportFrom) -> dict[str, str]:
    return {
        imported.asname or imported.name: f"{statement.module}.{imported.name}"
        for imported in statement.names
    }


def _binding_scopes(tree: ast.Module) -> list[_BindingScope]:
    scopes: list[_BindingScope] = [tree]
    scopes.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
    )
    return scopes


def _scope_statements(scope: _BindingScope) -> list[ast.AST]:
    return [scope.body] if isinstance(scope, ast.Lambda) else list(scope.body)


def _scope_bindings(tree: ast.Module) -> dict[int, set[str]]:
    return {id(scope): _direct_bindings(scope) for scope in _binding_scopes(tree)}


def _direct_bindings(scope: _BindingScope) -> set[str]:
    collector = _ScopeBindingCollector()
    if not isinstance(scope, ast.Module):
        collector.names.update(argument.arg for argument in _arguments(scope.args))
    for statement in _scope_statements(scope):
        collector.visit(statement)
    return collector.names


def _record_scope_binding(names: set[str], node: ast.AST) -> None:
    if isinstance(node, ast.Name):
        if isinstance(node.ctx, ast.Store):
            names.add(node.id)
        return
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        names.update(_import_binding_names(node))
        return
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        names.add(node.name)
        return
    _record_pattern_binding(names, node)


def _import_binding_names(node: ast.Import | ast.ImportFrom) -> list[str]:
    return [imported.asname or imported.name.split(".", 1)[0] for imported in node.names]


def _record_pattern_binding(names: set[str], node: ast.AST) -> None:
    if isinstance(node, (ast.MatchAs, ast.MatchStar, ast.ExceptHandler)):
        if node.name is not None:
            names.add(node.name)
    elif isinstance(node, ast.MatchMapping) and node.rest is not None:
        names.add(node.rest)


class _ScopeBindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()

    def generic_visit(self, node: ast.AST) -> None:
        _record_scope_binding(self.names, node)
        if not isinstance(
            node,
            (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            super().generic_visit(node)


def _is_function_shadowed(
    name: str,
    node: ast.AST,
    parents: dict[int, ast.AST],
    bindings: dict[int, set[str]],
) -> bool:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if name in bindings[id(current)]:
                return True
    return False


def _is_shadowed(
    name: str,
    node: ast.AST,
    tree: ast.Module,
    parents: dict[int, ast.AST],
    bindings: dict[int, set[str]],
) -> bool:
    current = node
    while id(current) in parents:
        current = parents[id(current)]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            if name in bindings[id(current)]:
                return True
    return name in bindings[id(tree)]


def _clean_code_findings(
    path: Path,
    source: str,
    tree: ast.Module,
    rules: Sequence[LoadedRule],
    clean_code_callables: Sequence[CleanCodeCallable],
) -> list[Finding]:
    return [
        *_boolean_argument_flag_findings(path, clean_code_callables, rules),
        *_else_expression_findings(path, clean_code_callables, rules),
        *_static_access_findings(path, clean_code_callables, rules),
        *_if_statement_assignment_findings(path, source, tree, rules),
        *_duplicated_array_key_findings(path, tree, rules),
    ]


def _boolean_argument_flag_findings(
    path: Path, callables: Sequence[CleanCodeCallable], rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, BOOLEAN_ARGUMENT_FLAG_RULE_NAME)
    if rule is None:
        return []
    exceptions = _exception_names(rule)
    ignored = _ignore_pattern(rule)
    findings: list[Finding] = []
    for callable_info in callables:
        if _ignore_boolean_flag_callable(callable_info, exceptions, ignored):
            continue
        node = callable_info.node
        for parameter in _boolean_parameters(node.args):
            if parameter.arg in {"self", "cls"} or parameter.arg.startswith("_"):
                continue
            context = _clean_code_context(callable_info)
            findings.append(
                Finding(
                    path,
                    parameter.lineno,
                    rule.name,
                    rule.priority,
                    f"The method {context} has a boolean flag argument {parameter.arg}, which is a certain sign "
                    "of a Single Responsibility Principle violation.",
                    context=context,
                )
            )
    return findings


def _ignore_boolean_flag_callable(
    callable_info: CleanCodeCallable, exceptions: set[str], ignored: re.Pattern[str]
) -> bool:
    node = callable_info.node
    return isinstance(node, ast.Lambda) or (
        node.name.startswith("_")
        or callable_info.owner_name in exceptions
        or bool(ignored.pattern and ignored.search(node.name))
    )


def _boolean_parameters(arguments: ast.arguments) -> list[ast.arg]:
    positional = [*arguments.posonlyargs, *arguments.args]
    defaults = {
        id(parameter): default
        for parameter, default in zip(positional[-len(arguments.defaults) :], arguments.defaults)
    } if arguments.defaults else {}
    defaults.update(
        {
            id(parameter): default
            for parameter, default in zip(arguments.kwonlyargs, arguments.kw_defaults)
            if default is not None
        }
    )
    return [
        parameter
        for parameter in _arguments(arguments)
        if _is_boolean_flag_annotation(parameter.annotation)
        or _is_boolean_literal(defaults.get(id(parameter)))
    ]


def _is_boolean_flag_annotation(node: ast.expr | None) -> bool:
    if _is_boolean_annotation(node):
        return True
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _is_boolean_flag_annotation(node.left) or _is_boolean_flag_annotation(node.right)
    if isinstance(node, ast.Subscript) and _is_boolean_union_name(node.value):
        values = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
        return any(_is_boolean_flag_annotation(value) for value in values)
    return False


def _is_boolean_union_name(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id in {"Optional", "Union"}
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "typing"
        and node.attr in {"Optional", "Union"}
    )


def _is_boolean_literal(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _else_expression_findings(
    path: Path, callables: Sequence[CleanCodeCallable], rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, ELSE_EXPRESSION_RULE_NAME)
    if rule is None:
        return []
    findings: list[Finding] = []
    for callable_info in callables:
        context = _clean_code_context(callable_info)
        nodes = _executable_nodes(callable_info.node)
        elif_nodes = _elif_nodes(nodes)
        for node in nodes:
            else_clause = _dead_else_clause(elif_nodes, node)
            if else_clause is None:
                continue
            findings.append(
                Finding(
                    path,
                    else_clause.lineno,
                    rule.name,
                    rule.priority,
                    f"The method {context} uses an else that follows a branch which always returns, raises, "
                    "continues, or breaks. That else clause is dead or misleading and you can simplify the "
                    "code by removing it.",
                    context=context,
                )
            )
    return findings


def _elif_nodes(nodes: Sequence[ast.AST]) -> set[int]:
    return {
        id(node.orelse[0])
        for node in nodes
        if isinstance(node, ast.If) and _is_single_if(node.orelse)
    }


def _dead_else_clause(elif_nodes: set[int], node: ast.AST) -> ast.stmt | None:
    if isinstance(node, ast.If):
        return None if id(node) in elif_nodes else _dead_else_after_if_chain(node)
    if isinstance(node, (ast.For, ast.AsyncFor, ast.While, ast.Try, ast.TryStar)):
        return node.orelse[0] if node.orelse and _block_always_exits(node.body) else None
    return None


def _is_single_if(statements: Sequence[ast.stmt]) -> bool:
    return len(statements) == 1 and isinstance(statements[0], ast.If)


def _dead_else_after_if_chain(node: ast.If) -> ast.stmt | None:
    branches, tail = _if_chain(node)
    if not tail:
        return None
    if all(_block_always_exits(branch) for branch in branches):
        return tail[0]
    return None


def _if_chain(node: ast.If) -> tuple[list[list[ast.stmt]], list[ast.stmt]]:
    branches = [node.body]
    tail = node.orelse
    while _is_single_if(tail):
        inner = tail[0]
        branches.append(inner.body)
        tail = inner.orelse
    return branches, tail


def _block_always_exits(body: Sequence[ast.stmt]) -> bool:
    return any(_statement_always_exits(statement) for statement in body)


def _statement_always_exits(statement: ast.stmt) -> bool:
    if isinstance(statement, (ast.Return, ast.Raise, ast.Continue, ast.Break)):
        return True
    if isinstance(statement, ast.If):
        return _if_statement_always_exits(statement)
    if isinstance(statement, (ast.With, ast.AsyncWith)):
        return _block_always_exits(statement.body)
    if isinstance(statement, (ast.Try, ast.TryStar)):
        return _try_statement_always_exits(statement)
    return False


def _if_statement_always_exits(node: ast.If) -> bool:
    branches, tail = _if_chain(node)
    if not tail:
        return False
    return all(_block_always_exits(branch) for branch in branches) and _block_always_exits(tail)


def _try_statement_always_exits(node: ast.Try | ast.TryStar) -> bool:
    if not node.handlers:
        return False
    if node.finalbody and _block_always_exits(node.finalbody):
        return True
    if not _block_always_exits(node.body) or (node.orelse and not _block_always_exits(node.orelse)):
        return False
    return all(_block_always_exits(handler.body) for handler in node.handlers)


def _static_access_findings(
    path: Path, callables: Sequence[CleanCodeCallable], rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, STATIC_ACCESS_RULE_NAME)
    if rule is None:
        return []
    exceptions = _exception_names(rule)
    ignored = _ignore_pattern(rule)
    findings: list[Finding] = []
    for callable_info in callables:
        name = _clean_code_callable_name(callable_info.node)
        if ignored.pattern and ignored.search(name):
            continue
        for node, receiver in _static_accesses(callable_info, exceptions):
            context = _clean_code_context(callable_info)
            findings.append(
                Finding(
                    path,
                    node.lineno,
                    rule.name,
                    rule.priority,
                    f"Avoid using static access to class '{receiver.id}' in method '{name}'.",
                    context=context,
                )
            )
    return findings


def _static_accesses(
    callable_info: CleanCodeCallable, exceptions: set[str]
) -> list[tuple[ast.Call, ast.Name]]:
    accesses: list[tuple[ast.Call, ast.Name]] = []
    for node in _executable_nodes(callable_info.node):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        receiver = node.func.value
        if not isinstance(receiver, ast.Name) or not receiver.id[:1].isupper():
            continue
        if receiver.id != callable_info.owner_name and receiver.id not in exceptions:
            accesses.append((node, receiver))
    return accesses


def _if_statement_assignment_findings(
    path: Path, source: str, tree: ast.Module, rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, IF_STATEMENT_ASSIGNMENT_RULE_NAME)
    if rule is None:
        return []
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.If, ast.While)):
            continue
        collector = _NamedExpressionCollector()
        collector.visit(node.test)
        findings.extend(
            Finding(
                path,
                assignment.lineno,
                rule.name,
                rule.priority,
                "Avoid assigning values to variables in if clauses and the like "
                f"(line '{assignment.lineno}', column '{_character_column(source, assignment)}').",
            )
            for assignment in collector.assignments
        )
    return findings


def _character_column(source: str, node: ast.AST) -> int:
    line = source.splitlines()[node.lineno - 1]
    prefix = line.encode("utf-8")[: node.col_offset].decode("utf-8")
    return len(prefix) + 1


class _NamedExpressionCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.assignments: list[ast.NamedExpr] = []

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.assignments.append(node)
        self.generic_visit(node)

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return


def _duplicated_array_key_findings(
    path: Path, tree: ast.Module, rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, DUPLICATED_ARRAY_KEY_RULE_NAME)
    if rule is None:
        return []
    findings: list[Finding] = []
    for dictionary in ast.walk(tree):
        if not isinstance(dictionary, ast.Dict):
            continue
        keys: dict[object, ast.expr] = {}
        for key in dictionary.keys:
            known, value = _static_dictionary_key(key)
            if not known or key is None:
                continue
            if value in keys:
                display = ast.unparse(key)
                findings.append(
                    Finding(
                        path,
                        key.lineno,
                        rule.name,
                        rule.priority,
                        f"Duplicated array key {display}, first declared at line {keys[value].lineno}.",
                        context=display,
                    )
                )
            else:
                keys[value] = key
    return findings


def _static_dictionary_key(node: ast.expr | None) -> tuple[bool, object]:
    if _is_static_constant(node):
        return True, node.value
    if isinstance(node, ast.UnaryOp):
        return _static_unary_key(node)
    if isinstance(node, ast.Tuple):
        return _static_tuple_key(node)
    return False, None


def _is_static_constant(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Constant) and type(node.value) in {
        str,
        bytes,
        int,
        float,
        complex,
        bool,
        type(None),
        type(Ellipsis),
    }


def _static_unary_key(node: ast.UnaryOp) -> tuple[bool, object]:
    if not isinstance(node.op, (ast.UAdd, ast.USub)):
        return False, None
    known, value = _static_dictionary_key(node.operand)
    if known and type(value) in {int, float, complex, bool}:
        return True, +value if isinstance(node.op, ast.UAdd) else -value
    return False, None


def _static_tuple_key(node: ast.Tuple) -> tuple[bool, object]:
    values = [_static_dictionary_key(element) for element in node.elts]
    return (
        (True, tuple(value for _, value in values))
        if all(known for known, _ in values)
        else (False, None)
    )


def _clean_code_callables(tree: ast.Module) -> list[CleanCodeCallable]:
    owner_collector = _CallableOwnerCollector()
    owner_collector.visit(tree)
    owners = owner_collector.owners
    return sorted(
        [
            CleanCodeCallable(node, owners.get(id(node)))
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
        ],
        key=lambda callable_info: (callable_info.node.lineno, callable_info.node.col_offset),
    )


class _CallableOwnerCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.owners: dict[int, str] = {}
        self.owner_name: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        previous_owner = self.owner_name
        self.owner_name = node.name
        for statement in node.body:
            self.visit(statement)
        self.owner_name = previous_owner

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_callable(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_callable(node)

    def _visit_callable(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if self.owner_name is not None:
            self.owners[id(node)] = self.owner_name
        previous_owner = self.owner_name
        self.owner_name = None
        for statement in node.body:
            self.visit(statement)
        self.owner_name = previous_owner


def _clean_code_callable_name(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> str:
    return "<lambda>" if isinstance(node, ast.Lambda) else node.name


def _clean_code_context(callable_info: CleanCodeCallable) -> str:
    name = _clean_code_callable_name(callable_info.node)
    return f"{callable_info.owner_name}.{name}" if callable_info.owner_name else name


def _executable_nodes(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> list[ast.AST]:
    collector = _ExecutableNodeCollector()
    if isinstance(node, ast.Lambda):
        collector.visit(node.body)
    else:
        for statement in node.body:
            collector.visit(statement)
    return collector.nodes


class _ExecutableNodeCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.nodes: list[ast.AST] = []

    def generic_visit(self, node: ast.AST) -> None:
        self.nodes.append(node)
        super().generic_visit(node)

    def visit_FunctionDef(self, _node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, _node: ast.AsyncFunctionDef) -> None:
        return

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, _node: ast.ClassDef) -> None:
        return


def _exception_names(rule: LoadedRule) -> set[str]:
    return {name.strip() for name in rule.properties.get("exceptions", "").split(",") if name.strip()}


def _unused_local_variable_findings(
    path: Path,
    rules: Sequence[LoadedRule],
    function_scopes: Sequence[
        tuple[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda, symtable.SymbolTable, frozenset[str]]
    ],
    comprehension_scopes: Sequence[
        tuple[
            ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
            symtable.SymbolTable | None,
        ]
    ],
    protocol_method_ids: set[int],
) -> list[Finding]:
    rule = _rule(rules, UNUSED_LOCAL_VARIABLE_RULE_NAME)
    if rule is None:
        return []
    findings = _unused_function_local_findings(path, function_scopes, rule, protocol_method_ids)
    findings.extend(_unused_comprehension_local_findings(path, comprehension_scopes, rule))
    return findings


def _lookup_symbol(table: symtable.SymbolTable, name: str) -> symtable.Symbol | None:
    try:
        return table.lookup(name)
    except KeyError:
        return None


def _unused_function_local_findings(
    path: Path,
    function_scopes: Sequence[
        tuple[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda, symtable.SymbolTable, frozenset[str]]
    ],
    rule: LoadedRule,
    protocol_method_ids: set[int],
) -> list[Finding]:
    findings: list[Finding] = []
    for node, table, used_names in function_scopes:
        if _is_conservative_callable(node, id(node) in protocol_method_ids):
            continue
        bindings = _FunctionLocalBindings()
        if isinstance(node, ast.Lambda):
            bindings.visit(node.body)
        else:
            for statement in node.body:
                bindings.visit(statement)
        reported: set[str] = set()
        for target in bindings.targets:
            symbol = _lookup_symbol(table, target.id)
            if symbol is None or _ignore_function_local(target.id, symbol, used_names, reported):
                continue
            reported.add(target.id)
            findings.append(
                Finding(
                    path,
                    target.lineno,
                    rule.name,
                    rule.priority,
                    f"Avoid unused local variables such as '{target.id}'.",
                    context=target.id,
                )
            )
    return findings


def _ignore_function_local(
    name: str,
    symbol: symtable.Symbol,
    used_names: frozenset[str],
    reported: set[str],
) -> bool:
    return (
        name.startswith("_")
        or name in used_names
        or not symbol.is_local()
        or symbol.is_parameter()
        or name in reported
    )


def _unused_comprehension_local_findings(
    path: Path,
    comprehension_scopes: Sequence[
        tuple[
            ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
            symtable.SymbolTable | None,
        ]
    ],
    rule: LoadedRule,
) -> list[Finding]:
    findings: list[Finding] = []
    for node, table in comprehension_scopes:
        findings.extend(_scope_comprehension_findings(path, node, table, rule))
    return findings


def _scope_comprehension_findings(
    path: Path,
    node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
    table: symtable.SymbolTable | None,
    rule: LoadedRule,
) -> list[Finding]:
    findings: list[Finding] = []
    reported: set[str] = set()
    used_names = _comprehension_used_names(node) if table is None else frozenset()
    for generator in node.generators:
        for target in _target_names(generator.target):
            symbol = _lookup_symbol(table, target.id) if table is not None else None
            if symbol is None and table is not None and not used_names:
                used_names = _comprehension_used_names(node)
            if _ignore_comprehension_local(target.id, symbol, used_names, reported):
                continue
            reported.add(target.id)
            findings.append(
                Finding(
                    path,
                    target.lineno,
                    rule.name,
                    rule.priority,
                    f"Avoid unused local variables such as '{target.id}'.",
                    context=target.id,
                )
            )
    return findings


def _ignore_comprehension_local(
    name: str,
    symbol: symtable.Symbol | None,
    used_names: frozenset[str],
    reported: set[str],
) -> bool:
    referenced = symbol.is_referenced() if symbol is not None else name in used_names
    return name.startswith("_") or referenced or (
        symbol is not None and not symbol.is_local()
    ) or name in reported


def _unused_formal_parameter_findings(
    path: Path,
    tree: ast.Module,
    rules: Sequence[LoadedRule],
    function_scopes: Sequence[
        tuple[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda, symtable.SymbolTable, frozenset[str]]
    ],
    protocol_method_ids: set[int],
) -> list[Finding]:
    rule = _rule(rules, UNUSED_FORMAL_PARAMETER_RULE_NAME)
    if rule is None:
        return []
    findings: list[Finding] = []
    visitor_method_ids = _ast_visitor_method_ids(tree)
    for node, table, used_names in function_scopes:
        if _is_conservative_callable(node, id(node) in protocol_method_ids):
            continue
        for parameter in _unused_parameters(node, table, used_names, visitor_method_ids):
            findings.append(
                Finding(
                    path,
                    parameter.lineno,
                    rule.name,
                    rule.priority,
                    f"Avoid unused parameters such as '{parameter.arg}'.",
                    context=parameter.arg,
                )
            )
    return findings


def _unused_parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
    table: symtable.SymbolTable,
    used_names: frozenset[str],
    visitor_method_ids: set[int],
) -> list[ast.arg]:
    parameters = _arguments(node.args)
    visitor_parameter = _visitor_parameter(node, parameters, visitor_method_ids)
    return [
        parameter
        for parameter in parameters
        if parameter.arg not in {"self", "cls"}
        and not parameter.arg.startswith("_")
        and parameter is not visitor_parameter
        and parameter.arg not in used_names
        and (symbol := _lookup_symbol(table, parameter.arg)) is not None
        and symbol.is_parameter()
    ]


def _is_conservative_callable(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
    is_protocol_method: bool,
) -> bool:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
        is_protocol_method
        or bool(node.decorator_list)
        or _is_contract_method(node)
    )


def _visitor_parameter(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
    parameters: list[ast.arg],
    visitor_method_ids: set[int],
) -> ast.arg | None:
    if id(node) not in visitor_method_ids:
        return None
    return next((parameter for parameter in parameters if parameter.arg not in {"self", "cls"}), None)


def _protocol_method_ids(tree: ast.Module) -> set[int]:
    protocol_names = _protocol_base_names(tree)
    return {
        id(method)
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and _is_protocol(node, protocol_names)
        for method in _class_member_statements(node.body)
        if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _function_scopes(
    source: str, tree: ast.Module
) -> list[tuple[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda, symtable.SymbolTable, frozenset[str]]]:
    tables: defaultdict[tuple[str, int], list[symtable.SymbolTable]] = defaultdict(list)
    _collect_function_tables(symtable.symtable(source, "<source>", "exec"), tables)
    scopes = []
    callable_nodes = _collect_callable_nodes(tree)
    for node in callable_nodes:
        name = node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "lambda"
        candidates = tables[(name, node.lineno)]
        if not candidates:
            continue
        table = _match_function_table(node, candidates)
        if table is None:
            continue
        used_names = (
            _scope_usage(table).used_names
            | _comprehension_referenced_names(node)
            | _augmented_assignment_names(node)
            | _annotation_referenced_names(node)
        )
        scopes.append((node, table, used_names))
    return scopes


def _collect_callable_nodes(
    tree: ast.Module,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda]:
    collector = _CallableNodeCollector()
    collector.visit(tree)
    return collector.nodes


class _CallableNodeCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.nodes: list[ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.nodes.append(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.nodes.append(node)
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.nodes.append(node)
        self.generic_visit(node)


def _match_function_table(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
    candidates: list[symtable.SymbolTable],
) -> symtable.SymbolTable | None:
    if not candidates:
        return None
    node_params = tuple(arg.arg for arg in _arguments(node.args))
    for index, candidate in enumerate(candidates):
        if getattr(candidate, "get_parameters", lambda: ())() == node_params:
            return candidates.pop(index)
    return candidates.pop(0)


def _comprehension_referenced_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
) -> frozenset[str]:
    # symtable can omit enclosing-scope references used only by comprehensions.
    # Record those loads so they count as uses in the current callable.
    referenced: set[str] = set()
    for descendant in _executable_nodes(node):
        if isinstance(descendant, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            referenced.update(_loaded_non_target_names(descendant))
    return frozenset(referenced)


def _augmented_assignment_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
) -> frozenset[str]:
    # symtable does not mark a plain Name target of an augmented assignment as
    # referenced, yet `name += 1` reads the previous value before storing.
    return frozenset(
        descendant.target.id
        for descendant in _executable_nodes(node)
        if isinstance(descendant, ast.AugAssign) and isinstance(descendant.target, ast.Name)
    )


def _annotation_referenced_names(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
) -> frozenset[str]:
    collector = _AnnotationReferenceCollector()
    roots = [node.body] if isinstance(node, ast.Lambda) else node.body
    for root in roots:
        collector.visit(root)
    return frozenset(collector.names)


class _AnnotationReferenceCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.names.update(_annotation_name_loads(node.annotation))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.names.update(_callable_annotation_name_loads(node))

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.names.update(_callable_annotation_name_loads(node))

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, _node: ast.ClassDef) -> None:
        return


def _callable_annotation_name_loads(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    annotations = [argument.annotation for argument in _arguments(node.args)]
    if node.returns is not None:
        annotations.append(node.returns)
    return {
        name
        for annotation in annotations
        if annotation is not None
        for name in _annotation_name_loads(annotation)
    }


def _annotation_name_loads(node: ast.AST) -> set[str]:
    return {
        descendant.id
        for descendant in ast.walk(node)
        if isinstance(descendant, ast.Name) and isinstance(descendant.ctx, ast.Load)
    }


def _loaded_non_target_names(
    node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
) -> set[str]:
    own_targets = {
        target.id for generator in node.generators for target in _target_names(generator.target)
    }
    pending = list(ast.iter_child_nodes(node))
    loaded_names: set[str] = set()
    while pending:
        descendant = pending.pop()
        if isinstance(descendant, ast.Name) and isinstance(descendant.ctx, ast.Load):
            if descendant.id not in own_targets:
                loaded_names.add(descendant.id)
            continue
        if isinstance(
            descendant,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.Lambda,
                ast.ClassDef,
                ast.ListComp,
                ast.SetComp,
                ast.DictComp,
                ast.GeneratorExp,
            ),
        ):
            continue
        pending.extend(ast.iter_child_nodes(descendant))
    return loaded_names


def _comprehension_scopes(
    source: str, tree: ast.Module
) -> list[
    tuple[
        ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
        symtable.SymbolTable | None,
    ]
]:
    tables: defaultdict[tuple[str, int], list[symtable.SymbolTable]] = defaultdict(list)
    _collect_comprehension_tables(symtable.symtable(source, "<source>", "exec"), tables)
    names = {
        ast.ListComp: "listcomp",
        ast.SetComp: "setcomp",
        ast.DictComp: "dictcomp",
        ast.GeneratorExp: "genexpr",
    }
    scopes = []
    comprehension_nodes = _collect_comprehension_nodes(tree)
    for node in comprehension_nodes:
        kind = names[type(node)]
        candidates = tables[(kind, node.lineno)]
        table = _match_comprehension_table(node, candidates)
        scopes.append((node, table))
    return scopes


def _collect_comprehension_nodes(
    tree: ast.Module,
) -> list[ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp]:
    collector = _ComprehensionNodeCollector()
    collector.visit(tree)
    return collector.nodes


class _ComprehensionNodeCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.nodes: list[ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp] = []

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self.nodes.append(node)
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self.nodes.append(node)
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self.nodes.append(node)
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self.nodes.append(node)
        self.generic_visit(node)


def _match_comprehension_table(
    node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
    candidates: list[symtable.SymbolTable],
) -> symtable.SymbolTable | None:
    if not candidates:
        return None
    target_names = {name.id for generator in node.generators for name in _target_names(generator.target)}
    for index, candidate in enumerate(candidates):
        candidate_identifiers = set(candidate.get_identifiers())
        if target_names.issubset(candidate_identifiers):
            return candidates.pop(index)
    return candidates.pop(0)


def _comprehension_used_names(
    node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
) -> frozenset[str]:
    used: set[str] = set()
    for index, generator in enumerate(node.generators):
        for target in _target_names(generator.target):
            if _comprehension_target_is_used(node, index, target.id):
                used.add(target.id)
    return frozenset(used)


def _comprehension_target_is_used(
    node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
    generator_index: int,
    target_name: str,
) -> bool:
    visitor = _ScopedNameUseVisitor(target_name)
    shadowed = _visit_later_comprehension_clauses(node, generator_index, target_name, visitor)
    if not shadowed:
        visitor.visit(node.key if isinstance(node, ast.DictComp) else node.elt)
        if isinstance(node, ast.DictComp):
            visitor.visit(node.value)
    return visitor.used


def _visit_later_comprehension_clauses(
    node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
    generator_index: int,
    target_name: str,
    visitor: _ScopedNameUseVisitor,
) -> bool:
    for later_index, later_generator in enumerate(
        node.generators[generator_index:], start=generator_index
    ):
        if later_index == generator_index:
            for condition in later_generator.ifs:
                visitor.visit(condition)
            continue
        visitor.visit(later_generator.iter)
        if target_name in {name.id for name in _target_names(later_generator.target)}:
            return True
        for condition in later_generator.ifs:
            visitor.visit(condition)
    return False


class _ScopedNameUseVisitor(ast.NodeVisitor):
    def __init__(self, name: str) -> None:
        self.name = name
        self.used = False

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load) and node.id == self.name:
            self.used = True

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        if self.name not in {argument.arg for argument in _arguments(node.args)}:
            self.visit(node.body)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self.visit_comprehension(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self.visit_comprehension(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self.visit_comprehension(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self.visit_comprehension(node)

    def visit_comprehension(
        self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp
    ) -> None:
        shadowed = False
        for generator in node.generators:
            self.visit(generator.iter)
            if self.name in {target.id for target in _target_names(generator.target)}:
                shadowed = True
                break
            for condition in generator.ifs:
                self.visit(condition)
        if shadowed:
            return
        self.visit(node.key if isinstance(node, ast.DictComp) else node.elt)
        if isinstance(node, ast.DictComp):
            self.visit(node.value)


def _collect_comprehension_tables(
    table: symtable.SymbolTable, tables: defaultdict[tuple[str, int], list[symtable.SymbolTable]]
) -> None:
    if table.get_type() == "function" and table.get_name() in {"listcomp", "setcomp", "dictcomp", "genexpr"}:
        tables[(table.get_name(), table.get_lineno())].append(table)
    for child in table.get_children():
        _collect_comprehension_tables(child, tables)


def _collect_function_tables(
    table: symtable.SymbolTable, tables: defaultdict[tuple[str, int], list[symtable.SymbolTable]]
) -> None:
    if table.get_type() == "function":
        tables[(table.get_name(), table.get_lineno())].append(table)
    for child in table.get_children():
        _collect_function_tables(child, tables)


def _scope_usage(table: symtable.SymbolTable) -> ScopeUsage:
    local_names = {name for name in table.get_identifiers() if table.lookup(name).is_local()}
    used_names = {name for name in table.get_identifiers() if table.lookup(name).is_referenced()}
    free_names = {name for name in table.get_identifiers() if table.lookup(name).is_free()}
    for child in table.get_children():
        child_usage = _scope_usage(child)
        captured = child_usage.free_names & local_names
        used_names.update(captured)
        free_names.update(child_usage.free_names - captured)
    return ScopeUsage(frozenset(used_names), frozenset(free_names))


def _unused_private_field_findings(
    path: Path,
    tree: ast.Module,
    classes: Sequence[ClassInfo],
    rules: Sequence[LoadedRule],
    usage: PrivateMemberUsage | None,
) -> list[Finding]:
    rule = _rule(rules, UNUSED_PRIVATE_FIELD_RULE_NAME)
    if rule is None or usage is None:
        return []
    if usage.requires_conservative_handling:
        return []
    findings: list[Finding] = []
    dataclass_names = _dataclass_decorator_names(tree)
    for class_info in classes:
        if _is_dataclass(class_info.node, dataclass_names):
            continue
        fields = _PrivateFieldCollector(class_info.node).collect()
        for name, line in fields.items():
            if name in usage.accessed_names or name in usage.exported_names:
                continue
            findings.append(
                Finding(
                    path,
                    line,
                    rule.name,
                    rule.priority,
                    f"Avoid unused private fields such as '{name}'.",
                    context=name,
                )
            )
    return findings


def _unused_private_method_findings(
    path: Path,
    classes: Sequence[ClassInfo],
    rules: Sequence[LoadedRule],
    usage: PrivateMemberUsage | None,
) -> list[Finding]:
    rule = _rule(rules, UNUSED_PRIVATE_METHOD_RULE_NAME)
    if rule is None or usage is None:
        return []
    if usage.requires_conservative_handling:
        return []
    findings: list[Finding] = []
    for class_info in classes:
        # An unresolved base may call protected hooks that this file cannot see.
        if class_info.has_unresolved_base:
            continue
        for method in class_info.methods:
            if not _is_unused_private_method(method, usage):
                continue
            findings.append(
                Finding(
                    path,
                    method.lineno,
                    rule.name,
                    rule.priority,
                    f"Avoid unused private methods such as '{method.name}'.",
                    context=method.name,
                )
            )
    return findings


def _is_unused_private_method(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
    usage: PrivateMemberUsage,
) -> bool:
    return (
        _is_private_name(method.name)
        and method.name not in usage.accessed_names
        and method.name not in usage.exported_names
        and not method.decorator_list
        and not _is_contract_method(method)
    )


class _PrivateFieldCollector(ast.NodeVisitor):
    def __init__(self, node: ast.ClassDef) -> None:
        self.node = node
        self.fields: dict[str, int] = {}
        self.loads: set[str] = set()
        self.has_unknown_dynamic_access = False
        self.receiver: str | None = None

    def collect(self) -> dict[str, int]:
        self._collect_class_fields()
        self._collect_method_fields()
        if self.has_unknown_dynamic_access:
            return {}
        return {name: line for name, line in self.fields.items() if name not in self.loads}

    def _collect_class_fields(self) -> None:
        for statement in _class_member_statements(self.node.body):
            for name in _field_names(statement):
                self._add_field(name, statement.lineno)

    def _collect_method_fields(self) -> None:
        for statement in _class_member_statements(self.node.body):
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.receiver = _instance_receiver(statement)
                for item in statement.body:
                    self.visit(item)

    def visit_Call(self, node: ast.Call) -> None:
        names, has_unknown_access = _dynamic_attribute_accesses(node)
        self.loads.update(names)
        self.has_unknown_dynamic_access = self.has_unknown_dynamic_access or has_unknown_access
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        # A direct attribute target is a store in the AST, but augmented
        # assignment reads the existing attribute before storing the result.
        target = node.target
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == self.receiver
        ):
            self.loads.add(target.attr)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            self.loads.add(node.attr)
        elif (
            isinstance(node.ctx, ast.Store)
            and self.receiver is not None
            and isinstance(node.value, ast.Name)
            and node.value.id == self.receiver
        ):
            self._add_field(node.attr, node.lineno)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self.receiver is not None and _shadows_receiver(node, self.receiver):
            return
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if self.receiver is not None and _shadows_receiver(node, self.receiver):
            return
        self.generic_visit(node)

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, _node: ast.ClassDef) -> None:
        return

    def _add_field(self, name: str, line: int) -> None:
        if _is_private_name(name):
            self.fields.setdefault(name, line)


def _is_private_name(name: str) -> bool:
    return name.startswith("_") and not (name.startswith("__") and name.endswith("__"))


def _dataclass_decorator_names(tree: ast.Module) -> set[str]:
    return {
        alias.asname or alias.name
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom) and statement.module == "dataclasses"
        for alias in statement.names
        if alias.name == "dataclass"
    } | {"dataclass"}


def _is_dataclass(node: ast.ClassDef, decorator_names: set[str]) -> bool:
    return any(
        _called_name(decorator.func if isinstance(decorator, ast.Call) else decorator) in decorator_names | {"dataclass"}
        for decorator in node.decorator_list
    )


def _private_member_usage(tree: ast.Module) -> PrivateMemberUsage:
    dynamic_names, has_unknown_dynamic_access = _dynamic_attribute_accesses(tree, _dynamic_access_aliases(tree))
    exported_names, has_unknown_exports = _exported_names(tree)
    loads = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load)
    } | dynamic_names
    return PrivateMemberUsage(
        frozenset(loads),
        frozenset(exported_names),
        has_unknown_dynamic_access or has_unknown_exports,
    )


def _dynamic_access_aliases(tree: ast.Module) -> set[str]:
    return {
        alias.asname or alias.name
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom) and statement.module == "builtins"
        for alias in statement.names
        if alias.name in {"getattr", "hasattr", "setattr", "delattr"}
    }


def _exported_names(tree: ast.Module) -> tuple[set[str], bool]:
    names: set[str] = set()
    has_unknown_exports = False
    for statement in ast.walk(tree):
        targets, value, augmented = _export_assignment(statement)
        if augmented:
            has_unknown_exports = True
            continue
        if targets is None:
            continue
        if not _assigns_exports(targets):
            continue
        static_names = _static_export_names(value)
        if static_names is None:
            has_unknown_exports = True
            continue
        names.update(static_names)
    return names, has_unknown_exports


def _assigns_exports(targets: list[ast.expr]) -> bool:
    return any(isinstance(target, ast.Name) and target.id == "__all__" for target in targets)


def _static_export_names(value: ast.expr | None) -> set[str] | None:
    if not isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        return None
    if not all(
        isinstance(element, ast.Constant) and isinstance(element.value, str)
        for element in value.elts
    ):
        return None
    return {element.value for element in value.elts if isinstance(element, ast.Constant)}


def _export_assignment(
    statement: ast.AST,
) -> tuple[list[ast.expr] | None, ast.expr | None, bool]:
    if isinstance(statement, ast.Assign):
        return statement.targets, statement.value, False
    if isinstance(statement, ast.AnnAssign):
        return [statement.target], statement.value, False
    augmented = (
        isinstance(statement, ast.AugAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id == "__all__"
    )
    return None, None, augmented


def _dynamic_attribute_accesses(node: ast.AST, aliases: set[str] | None = None) -> tuple[set[str], bool]:
    names: set[str] = set()
    has_unknown_access = False
    calls = [node] if isinstance(node, ast.Call) else ast.walk(node)
    for candidate in calls:
        if not isinstance(candidate, ast.Call):
            continue
        attribute_index = _dynamic_attribute_index(candidate, aliases or set())
        if attribute_index is None or len(candidate.args) <= attribute_index:
            continue
        attribute = candidate.args[attribute_index]
        if isinstance(attribute, ast.Constant) and isinstance(attribute.value, str):
            names.add(attribute.value)
        else:
            has_unknown_access = True
    return names, has_unknown_access


def _dynamic_attribute_index(candidate: ast.Call, aliases: set[str]) -> int | None:
    function_name = _called_name(candidate.func)
    if function_name in {"getattr", "hasattr", "setattr", "delattr"} | aliases:
        return 1
    if function_name in {"__getattribute__", "__setattr__", "__delattr__"}:
        return 0
    return None


class _NestedScopeSkippingVisitor(ast.NodeVisitor):
    def visit_FunctionDef(self, _node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, _node: ast.AsyncFunctionDef) -> None:
        return

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, _node: ast.ClassDef) -> None:
        return


class _FunctionLocalBindings(_NestedScopeSkippingVisitor):
    def __init__(self) -> None:
        self.targets: list[ast.Name] = []

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.targets.append(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self._add_target(node.name, node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name is not None:
            self._add_target(node.name, node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name is not None:
            self._add_target(node.name, node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest is not None:
            self._add_target(node.rest, node.lineno, node.col_offset)
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        self._add_named_expression_targets(node)

    def visit_SetComp(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        self._add_named_expression_targets(node)

    def visit_DictComp(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        self._add_named_expression_targets(node)

    def visit_GeneratorExp(self, node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp) -> None:
        self._add_named_expression_targets(node)

    def _add_named_expression_targets(self, node: ast.AST) -> None:
        pending = list(ast.iter_child_nodes(node))
        while pending:
            child = pending.pop()
            if isinstance(child, ast.NamedExpr):
                self.targets.extend(_target_names(child.target))
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            pending.extend(ast.iter_child_nodes(child))

    def _add_target(self, name: str, line: int, column: int) -> None:
        self.targets.append(ast.Name(id=name, ctx=ast.Store(), lineno=line, col_offset=column))


def _naming_findings(path: Path, tree: ast.Module, rules: Sequence[LoadedRule]) -> list[Finding]:
    targets, callables = _naming_roles(tree)
    findings: list[Finding] = []
    findings.extend(_short_class_name_findings(path, targets, rules))
    findings.extend(_long_class_name_findings(path, targets, rules))
    findings.extend(_short_variable_findings(path, targets, rules))
    findings.extend(_long_variable_findings(path, targets, rules))
    findings.extend(_short_method_name_findings(path, targets, rules))
    findings.extend(_constant_naming_findings(path, targets, rules))
    findings.extend(_boolean_get_method_name_findings(path, callables, rules))
    findings.extend(_strict_python_naming_findings(path, targets, rules))
    return findings


def _short_class_name_findings(path: Path, targets: Sequence[NamingTarget], rules: Sequence[LoadedRule]) -> list[Finding]:
    rule = _rule(rules, SHORT_CLASS_NAME_RULE_NAME)
    if rule is None:
        return []
    minimum = _integer_property(rule, "minimum")
    return [
        _naming_finding(
            path,
            target,
            rule,
            f"Avoid using short class names like {target.name}. Configured minimum length is {minimum}.",
        )
        for target in targets
        if target.role == "class" and not _is_exempt_target(target) and len(target.name) < minimum
    ]


def _long_class_name_findings(path: Path, targets: Sequence[NamingTarget], rules: Sequence[LoadedRule]) -> list[Finding]:
    rule = _rule(rules, LONG_CLASS_NAME_RULE_NAME)
    if rule is None:
        return []
    maximum = _integer_property(rule, "maximum")
    return [
        _naming_finding(
            path,
            target,
            rule,
            f"Avoid excessively long class names like {target.name}. Configured maximum length is {maximum}.",
        )
        for target in targets
        if target.role == "class" and not _is_exempt_target(target) and len(target.name) > maximum
    ]


def _short_variable_findings(path: Path, targets: Sequence[NamingTarget], rules: Sequence[LoadedRule]) -> list[Finding]:
    rule = _rule(rules, SHORT_VARIABLE_RULE_NAME)
    if rule is None:
        return []
    minimum = _integer_property(rule, "minimum")
    return _variable_length_findings(path, targets, rule, minimum, too_long=False)


def _long_variable_findings(path: Path, targets: Sequence[NamingTarget], rules: Sequence[LoadedRule]) -> list[Finding]:
    rule = _rule(rules, LONG_VARIABLE_RULE_NAME)
    if rule is None:
        return []
    maximum = _integer_property(rule, "maximum")
    return _variable_length_findings(path, targets, rule, maximum, too_long=True)


def _variable_length_findings(
    path: Path, targets: Sequence[NamingTarget], rule: LoadedRule, limit: int, too_long: bool
) -> list[Finding]:
    if too_long:
        message = lambda target: (
            f"Avoid excessively long variable names like {target.name}. Configured maximum length is {limit}."
        )
    else:
        message = lambda target: f"Avoid variables with short names like {target.name}. Configured minimum length is {limit}."
    return [
        _naming_finding(path, target, rule, message(target))
        for target in targets
        if target.role in {"parameter", "property", "variable"}
        and not _is_exempt_target(target)
        and (len(target.name) > limit if too_long else len(target.name) < limit)
    ]


def _short_method_name_findings(path: Path, targets: Sequence[NamingTarget], rules: Sequence[LoadedRule]) -> list[Finding]:
    rule = _rule(rules, SHORT_METHOD_NAME_RULE_NAME)
    if rule is None:
        return []
    minimum = _integer_property(rule, "minimum")
    return [
        _naming_finding(
            path,
            target,
            rule,
            f"Avoid using short method names like {target.name}(). Configured minimum length is {minimum}.",
        )
        for target in targets
        if target.role in {"function", "method"} and not _is_exempt_target(target) and len(target.name) < minimum
    ]


def _constant_naming_findings(path: Path, targets: Sequence[NamingTarget], rules: Sequence[LoadedRule]) -> list[Finding]:
    rule = _rule(rules, CONSTANT_NAMING_CONVENTIONS_RULE_NAME)
    if rule is None:
        return []
    return [
        _naming_finding(
            path,
            target,
            rule,
            f"The constant {target.name} should use UPPER_CASE naming.",
        )
        for target in targets
        if target.role == "constant"
        and not _is_exempt_target(target)
        and re.fullmatch(r"[A-Z][A-Z0-9_]*", target.name) is None
    ]


def _boolean_get_method_name_findings(
    path: Path, callables: Sequence[NamingCallable], rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, BOOLEAN_GET_METHOD_NAME_RULE_NAME)
    if rule is None:
        return []
    return [
        Finding(
            path,
            callable_info.node.lineno,
            rule.name,
            rule.priority,
            f"The boolean method {callable_info.node.name}() should not use the get prefix.",
            context=callable_info.node.name,
        )
        for callable_info in callables
        if callable_info.role == "method"
        and _is_getter_name(callable_info.node.name)
        and _has_boolean_result(callable_info.node)
    ]


def _strict_python_naming_findings(
    path: Path, targets: Sequence[NamingTarget], rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule_roles = {
        CAMEL_CASE_CLASS_RULE_NAME: {"class"},
        CAMEL_CASE_METHOD_RULE_NAME: {"function", "method"},
        CAMEL_CASE_PROPERTY_RULE_NAME: {"property"},
        CAMEL_CASE_PARAMETER_RULE_NAME: {"parameter"},
        CAMEL_CASE_VARIABLE_RULE_NAME: {"variable"},
    }
    findings: list[Finding] = []
    for rule_name, roles in rule_roles.items():
        rule = _rule(rules, rule_name)
        if rule is None:
            continue
        for target in targets:
            if target.role not in roles or _is_exempt_target(target):
                continue
            if target.role == "class":
                valid = re.fullmatch(r"[A-Z][A-Za-z0-9]*", target.name) is not None
                convention = "CapWords"
            else:
                valid = _is_snake_case_name(target.name)
                convention = "snake_case"
            if valid:
                continue
            subject = "method" if target.role == "function" else target.role
            findings.append(
                _naming_finding(
                    path,
                    target,
                    rule,
                    f"The {subject} {target.name} is not named in {convention}.",
                )
            )
    return findings


def _is_snake_case_name(name: str) -> bool:
    if re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", name) is not None:
        return True
    return (
        name.endswith("_")
        and keyword.iskeyword(name[:-1])
        and re.fullmatch(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*", name[:-1]) is not None
    )


def _naming_finding(path: Path, target: NamingTarget, rule: LoadedRule, message: str) -> Finding:
    return Finding(path, target.line, rule.name, rule.priority, message, context=target.name)


def _is_exempt_target(target: NamingTarget) -> bool:
    if target.name.startswith("_"):
        return True
    if target.contract:
        return True
    if target.role == "property" and target.name in {"i", "j", "k", "n", "x", "y", "z"}:
        return True
    return target.role in {"parameter", "variable"} and target.name in {
        "self",
        "cls",
        "e",
        "err",
        "exc",
        "ex",
        "i",
        "j",
        "k",
        "n",
        "x",
        "y",
        "z",
    }


def _is_getter_name(name: str) -> bool:
    return name.startswith("get_") or (name.startswith("get") and len(name) > 3 and name[3].isupper())


def _has_boolean_result(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return _is_boolean_annotation(node.returns) or _all_paths_return_boolean(node.body)


def _is_boolean_annotation(node: ast.expr | None) -> bool:
    return (isinstance(node, ast.Name) and node.id == "bool") or (
        isinstance(node, ast.Constant) and node.value == "bool"
    )


def _all_paths_return_boolean(statements: Sequence[ast.stmt]) -> bool:
    if not statements:
        return False
    statement, *remaining = statements
    if isinstance(statement, ast.Return):
        return statement.value is not None and _is_boolean_expression(statement.value)
    if isinstance(statement, ast.If):
        return _all_paths_return_boolean([*statement.body, *remaining]) and _all_paths_return_boolean(
            [*statement.orelse, *remaining]
        )
    if _contains_return(statement):
        return False
    return _all_paths_return_boolean(remaining)


def _contains_return(node: ast.AST) -> bool:
    if isinstance(node, ast.Return):
        return True
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return False
    return any(_contains_return(child) for child in ast.iter_child_nodes(node))


def _is_boolean_expression(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Compare)
        or isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not)
        or isinstance(node, ast.Constant) and isinstance(node.value, bool)
        or isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"bool", "isinstance", "issubclass"}
    )


def _called_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _cyclomatic_complexity_findings(
    path: Path, callables: Sequence[CallableInfo], rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = next((candidate for candidate in rules if candidate.name == CYCLOMATIC_COMPLEXITY_RULE_NAME), None)
    if rule is None:
        return []
    try:
        threshold = int(rule.properties["reportlevel"])
    except (KeyError, ValueError) as error:
        raise RulesetError("CyclomaticComplexity property 'reportLevel' must be an integer.") from error
    findings: list[Finding] = []
    for callable_info in callables:
        complexity = _cyclomatic_complexity(callable_info.node)
        if complexity < threshold:
            continue
        message = (
            f"The {callable_info.kind} {callable_info.name}() has a Cyclomatic Complexity of {complexity}. "
            f"The configured cyclomatic complexity threshold is {threshold}."
        )
        findings.append(
            Finding(
                path,
                callable_info.node.lineno,
                CYCLOMATIC_COMPLEXITY_RULE_NAME,
                rule.priority,
                message,
                context=callable_info.name,
            )
        )
    return findings


def _cyclomatic_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> int:
    visitor = _CyclomaticComplexityVisitor()
    if isinstance(node, ast.Lambda):
        visitor.visit(node.body)
    else:
        for statement in node.body:
            visitor.visit(statement)
    return 1 + visitor.decisions


class _CyclomaticComplexityVisitor(_NestedScopeSkippingVisitor):
    def __init__(self) -> None:
        self.decisions = 0

    def visit_If(self, node: ast.If) -> None:
        self.decisions += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.decisions += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.decisions += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.decisions += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.decisions += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.decisions += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.decisions += len(node.values) - 1
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.decisions += 1 + len(node.ifs)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.decisions += len(node.cases)
        self.generic_visit(node)


def _npath_complexity_findings(
    path: Path, callables: Sequence[CallableInfo], rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = next((candidate for candidate in rules if candidate.name == NPATH_COMPLEXITY_RULE_NAME), None)
    if rule is None:
        return []
    try:
        threshold = int(rule.properties["minimum"])
    except (KeyError, ValueError) as error:
        raise RulesetError("NPathComplexity property 'minimum' must be an integer.") from error
    findings: list[Finding] = []
    for callable_info in callables:
        complexity = _npath_complexity(callable_info.node)
        if complexity < threshold:
            continue
        message = (
            f"The {callable_info.kind} {callable_info.name}() has an NPath complexity of {complexity}. "
            f"The configured NPath complexity threshold is {threshold}."
        )
        findings.append(
            Finding(
                path,
                callable_info.node.lineno,
                NPATH_COMPLEXITY_RULE_NAME,
                rule.priority,
                message,
                context=callable_info.name,
            )
        )
    return findings


def _npath_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> int:
    return _npath_expression(node.body) if isinstance(node, ast.Lambda) else _npath_block(node.body)


def _npath_block(statements: Sequence[ast.stmt]) -> int:
    complexity = 1
    for statement in statements:
        complexity *= _npath_statement(statement)
    return complexity


def _npath_statement(node: ast.stmt) -> int:
    if isinstance(node, ast.If):
        return _npath_expression(node.test) * (_npath_block(node.body) + _npath_block(node.orelse))
    elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        return _npath_loop(node)
    elif isinstance(node, (ast.With, ast.AsyncWith)):
        return _npath_with(node)
    elif isinstance(node, (ast.Try, ast.TryStar)):
        return _npath_try(node)
    elif isinstance(node, ast.Match):
        return _npath_match(node)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return 1
    elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.Expr, ast.Return, ast.Raise)):
        value = getattr(node, "value", None)
        return _npath_expression(value) if value is not None else 1
    return 1


def _npath_loop(node: ast.For | ast.AsyncFor | ast.While) -> int:
    condition = node.iter if isinstance(node, (ast.For, ast.AsyncFor)) else node.test
    return _npath_expression(condition) * (_npath_block(node.body) + _npath_block(node.orelse))


def _npath_with(node: ast.With | ast.AsyncWith) -> int:
    complexity = 1
    for item in node.items:
        complexity *= _npath_expression(item.context_expr)
    return complexity * _npath_block(node.body)


def _npath_try(node: ast.Try | ast.TryStar) -> int:
    handlers = sum(_npath_block(handler.body) for handler in node.handlers)
    return (_npath_block(node.body) + handlers) * _npath_block(node.orelse) * _npath_block(node.finalbody)


def _npath_match(node: ast.Match) -> int:
    return _npath_expression(node.subject) * sum(
        _npath_block(case.body) + (_npath_expression(case.guard) if case.guard is not None else 0)
        for case in node.cases
    )


def _npath_expression(node: ast.AST | None) -> int:
    if node is None:
        return 1
    if isinstance(node, ast.BoolOp):
        return sum(_npath_expression(value) for value in node.values)
    if isinstance(node, ast.IfExp):
        return _npath_expression(node.test) + _npath_expression(node.body) + _npath_expression(node.orelse)
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
        return _npath_comprehension(node)
    if isinstance(node, ast.Lambda):
        return 1
    complexity = 1
    for child in ast.iter_child_nodes(node):
        complexity *= _npath_expression(child)
    return complexity


def _npath_comprehension(
    node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp,
) -> int:
    complexity = 1
    for generator in node.generators:
        filters = 1
        for condition in generator.ifs:
            filters += _npath_expression(condition)
        complexity *= _npath_expression(generator.iter) * filters
    if isinstance(node, ast.DictComp):
        return complexity * _npath_expression(node.key) * _npath_expression(node.value)
    return complexity * _npath_expression(node.elt)


def _excessive_parameter_list_findings(
    path: Path, callables: Sequence[CallableInfo], rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = next((candidate for candidate in rules if candidate.name == EXCESSIVE_PARAMETER_LIST_RULE_NAME), None)
    if rule is None:
        return []
    try:
        threshold = int(rule.properties["minimum"])
    except (KeyError, ValueError) as error:
        raise RulesetError("ExcessiveParameterList property 'minimum' must be an integer.") from error
    findings: list[Finding] = []
    for callable_info in callables:
        if callable_info.parameter_count < threshold:
            continue
        message = (
            f"The {callable_info.kind} {callable_info.name} has {callable_info.parameter_count} parameters. "
            f"Consider reducing the number of parameters to less than {threshold}."
        )
        findings.append(
            Finding(
                path,
                callable_info.node.lineno,
                EXCESSIVE_PARAMETER_LIST_RULE_NAME,
                rule.priority,
                message,
                context=callable_info.name,
            )
        )
    return findings


def _parameter_count(arguments: ast.arguments) -> int:
    return (
        len(arguments.posonlyargs)
        + len(arguments.args)
        + len(arguments.kwonlyargs)
        + int(arguments.vararg is not None)
        + int(arguments.kwarg is not None)
    )


def _callables(tree: ast.Module) -> list[CallableInfo]:
    collector = _CallableCollector()
    for statement in tree.body:
        collector.visit_statement(statement, in_class_body=False)
    collector.add_lambdas(tree)
    return sorted(collector.callables, key=lambda callable_info: callable_info.node.lineno)


class _CallableCollector:
    def __init__(self) -> None:
        self.callables: list[CallableInfo] = []

    def visit_statement(self, node: ast.stmt, in_class_body: bool) -> None:
        if isinstance(node, ast.ClassDef):
            for statement in node.body:
                self.visit_statement(statement, in_class_body=True)
            return
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            kind = "method" if in_class_body else "function"
            self.callables.append(CallableInfo(node, node.name, kind, _parameter_count(node.args)))
            for statement in node.body:
                self.visit_statement(statement, in_class_body=False)
            return
        for child in _child_statements(node):
            self.visit_statement(child, in_class_body=in_class_body)

    def add_lambdas(self, tree: ast.Module) -> None:
        self.callables.extend(
            CallableInfo(node, "<lambda>", "lambda", _parameter_count(node.args))
            for node in ast.walk(tree)
            if isinstance(node, ast.Lambda)
        )


def _naming_roles(tree: ast.Module) -> tuple[list[NamingTarget], list[NamingCallable]]:
    collector = _NamingRoleCollector(_ast_visitor_method_ids(tree), _type_alias_annotation_ids(tree))
    collector.visit(tree)
    for target in _named_binding_targets(tree):
        collector._add_target(target.name, target.line, target.role)
    targets = sorted(collector.targets, key=lambda target: (target.line, target.role, target.name))
    callables = sorted(collector.callables, key=lambda callable_info: callable_info.node.lineno)
    return targets, callables


def _named_binding_targets(tree: ast.Module) -> list[NamingTarget]:
    targets: list[NamingTarget] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and node.name is not None:
            targets.append(NamingTarget(node.name, node.lineno, "variable"))
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name is not None:
            targets.append(NamingTarget(node.name, node.lineno, "variable"))
        elif isinstance(node, ast.MatchMapping) and node.rest is not None:
            targets.append(NamingTarget(node.rest, node.lineno, "variable"))
    return targets


def _type_alias_annotation_ids(tree: ast.Module) -> set[int]:
    collector = _TypeAliasAnnotationCollector()
    collector.visit(tree)
    return collector.annotation_ids


class _TypeAliasAnnotationCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.annotation_ids: set[int] = set()
        self.import_aliases: dict[str, tuple[str, bool]] = {}
        self.class_outer_aliases: list[dict[str, tuple[str, bool]]] = []

    def visit_Import(self, node: ast.Import) -> None:
        self.import_aliases.update(_statement_import_aliases(node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.import_aliases.update(_statement_import_aliases(node))

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        outer_aliases = self.import_aliases
        inherited_aliases = self.class_outer_aliases[-1] if self.class_outer_aliases else outer_aliases
        local_names = _direct_bindings(node)
        self.import_aliases = {
            name: alias for name, alias in inherited_aliases.items() if name not in local_names
        }
        try:
            for statement in node.body:
                self.visit(statement)
        finally:
            self.import_aliases = outer_aliases
            self.import_aliases.pop(node.name, None)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        outer_aliases = self.import_aliases
        self.import_aliases = dict(outer_aliases)
        self.class_outer_aliases.append(outer_aliases)
        try:
            for statement in node.body:
                self.visit(statement)
        finally:
            self.class_outer_aliases.pop()
            self.import_aliases = outer_aliases
            self.import_aliases.pop(node.name, None)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        for name in _statement_assigned_names(node):
            self.import_aliases.pop(name, None)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if _is_type_alias_annotation(node.annotation, self.import_aliases):
            self.annotation_ids.add(id(node.annotation))
        self.generic_visit(node)
        for name in _statement_assigned_names(node):
            self.import_aliases.pop(name, None)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.generic_visit(node)
        for name in _statement_assigned_names(node):
            self.import_aliases.pop(name, None)


class _NamingRoleCollector(ast.NodeVisitor):
    def __init__(self, visitor_method_ids: set[int], type_alias_annotation_ids: set[int]) -> None:
        self.targets: list[NamingTarget] = []
        self.target_names: set[NamingTarget] = set()
        self.callables: list[NamingCallable] = []
        self.contexts: list[str] = []
        self.class_depth = 0
        self.receivers: list[str | None] = []
        self.constant_target_ids: set[int] = set()
        self.generic_target_ids: set[int] = set()
        self.visitor_method_ids = frozenset(visitor_method_ids)
        self.type_alias_annotation_ids = frozenset(type_alias_annotation_ids)

    def visit_TypeAlias(self, node: ast.TypeAlias) -> None:
        self.generic_target_ids.add(id(node.name))
        self._add_target(node.name.id, node.name.lineno, "class")
        self.visit(node.value)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add_target(node.name, node.lineno, "class")
        self.contexts.append("class")
        self.class_depth += 1
        for statement in node.body:
            self.visit(statement)
        self.class_depth -= 1
        self.contexts.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        _collect_naming_callable(self, node, self.contexts)

    def visit_AsyncFunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        _collect_naming_callable(self, node, self.contexts)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for argument in _arguments(node.args):
            self._add_target(argument.arg, argument.lineno, "parameter")
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        self.contexts.append("function")
        self.receivers.append(None)
        self.visit(node.body)
        self.receivers.pop()
        self.contexts.pop()

    def visit_Assign(self, node: ast.Assign) -> None:
        if _is_type_parameter_factory(node.value):
            self.generic_target_ids.update(id(target) for name in node.targets for target in _target_names(name))
        if _is_module_or_class_scope(self.contexts):
            self.constant_target_ids.update(
                id(target)
                for name in node.targets
                for target in _target_names(name)
                if re.fullmatch(r"[A-Z][A-Z0-9_]*", target.id) is not None
            )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        targets = _target_names(node.target)
        if id(node.annotation) in self.type_alias_annotation_ids:
            self.generic_target_ids.update(id(target) for target in targets)
            for target in targets:
                self._add_target(target.id, target.lineno, "class")
        elif _is_final_annotation(node.annotation) or (
            _is_module_or_class_scope(self.contexts)
            and any(re.fullmatch(r"[A-Z][A-Z0-9_]*", target.id) is not None for target in targets)
        ):
            self.constant_target_ids.update(id(target) for target in targets)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if not isinstance(node.ctx, ast.Store):
            return
        if id(node) in self.generic_target_ids:
            return
        role = "constant" if id(node) in self.constant_target_ids else _naming_variable_role(self.contexts)
        self._add_target(node.id, node.lineno, role)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        receiver = self.receivers[-1] if self.receivers else None
        if (
            isinstance(node.ctx, ast.Store)
            and self.class_depth > 0
            and receiver is not None
            and isinstance(node.value, ast.Name)
            and node.value.id == receiver
        ):
            self._add_target(node.attr, node.lineno, "property")
        self.generic_visit(node)

    def _add_target(
        self,
        name: str,
        line: int,
        role: str,
        contract: bool = False,
    ) -> None:
        target = NamingTarget(name, line, role, contract)
        if target not in self.target_names:
            self.target_names.add(target)
            self.targets.append(target)


def _naming_variable_role(contexts: list[str]) -> str:
    return "property" if contexts and contexts[-1] == "class" else "variable"


def _is_module_or_class_scope(contexts: list[str]) -> bool:
    return not contexts or contexts[-1] == "class"


def _collect_naming_callable(
    collector: _NamingRoleCollector, node: ast.FunctionDef | ast.AsyncFunctionDef, contexts: list[str]
) -> None:
    direct_class_member = bool(contexts and contexts[-1] == "class")
    role = _naming_callable_role(node, direct_class_member)
    collector._add_target(
        node.name,
        node.lineno,
        role,
        id(node) in collector.visitor_method_ids,
    )
    collector.callables.append(NamingCallable(node, role))
    for argument in _arguments(node.args):
        collector._add_target(argument.arg, argument.lineno, "parameter")
    for decorator in node.decorator_list:
        collector.visit(decorator)
    for default in [*node.args.defaults, *node.args.kw_defaults]:
        if default is not None:
            collector.visit(default)
    receiver = _instance_receiver(node) if direct_class_member else None
    contexts.append("function")
    collector.receivers.append(receiver)
    for statement in node.body:
        collector.visit(statement)
    collector.receivers.pop()
    contexts.pop()


def _naming_callable_role(node: ast.FunctionDef | ast.AsyncFunctionDef, direct_class_member: bool) -> str:
    if not direct_class_member:
        return "function"
    return "property" if _has_property_decorator(node) else "method"


def _arguments(arguments: ast.arguments) -> list[ast.arg]:
    values = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]
    if arguments.vararg is not None:
        values.append(arguments.vararg)
    if arguments.kwarg is not None:
        values.append(arguments.kwarg)
    return values


def _target_names(node: ast.AST) -> list[ast.Name]:
    if isinstance(node, ast.Name):
        return [node]
    if isinstance(node, ast.Starred):
        return _target_names(node.value)
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for element in node.elts for name in _target_names(element)]
    return []


def _is_type_alias_annotation(
    node: ast.expr,
    import_aliases: dict[str, tuple[str, bool]] | None = None,
) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TypeAlias" or _resolved_import_name(node, import_aliases or {}) == "typing.TypeAlias"
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "typing"
        and node.attr == "TypeAlias"
    ) or _resolved_import_name(node, import_aliases or {}) == "typing.TypeAlias"


def _is_final_annotation(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "Final"
    if isinstance(node, ast.Attribute):
        return node.attr == "Final"
    return isinstance(node, ast.Subscript) and _is_final_annotation(node.value)


def _is_type_parameter_factory(node: ast.expr) -> bool:
    return isinstance(node, ast.Call) and _called_name(node.func) in {"TypeVar", "ParamSpec", "TypeVarTuple"}


def _excessive_method_length_findings(
    path: Path, callables: Sequence[CallableInfo], rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = next((candidate for candidate in rules if candidate.name == METHOD_LENGTH_RULE_NAME), None)
    if rule is None:
        return []
    try:
        method_length_limit = int(rule.properties["minimum"])
    except (KeyError, ValueError) as error:
        raise RulesetError("ExcessiveMethodLength property 'minimum' must be an integer.") from error
    findings: list[Finding] = []
    for callable_info in callables:
        node = callable_info.node
        line_count = (node.end_lineno or node.lineno) - node.lineno + 1
        if line_count < method_length_limit:
            continue
        message = (
            f"The {callable_info.kind} {callable_info.name}() has {line_count} lines of code. "
            f"Current threshold is set to {method_length_limit}. Avoid really long methods."
        )
        findings.append(
            Finding(
                path,
                node.lineno,
                METHOD_LENGTH_RULE_NAME,
                rule.priority,
                message,
                context=callable_info.name,
            )
        )
    return findings


def _class_findings(
    path: Path,
    source_lines: Sequence[str],
    classes: Sequence[ClassInfo],
    rules: Sequence[LoadedRule],
) -> list[Finding]:
    findings: list[Finding] = []
    for class_info in classes:
        findings.extend(_excessive_class_length_findings(path, source_lines, class_info, rules))
        findings.extend(_excessive_public_count_findings(path, class_info, rules))
        findings.extend(_too_many_fields_findings(path, class_info, rules))
        findings.extend(_too_many_methods_findings(path, class_info, rules, public_only=False))
        findings.extend(_too_many_methods_findings(path, class_info, rules, public_only=True))
        findings.extend(_excessive_class_complexity_findings(path, class_info, rules))
    return findings


def _excessive_class_length_findings(
    path: Path, source_lines: Sequence[str], class_info: ClassInfo, rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, EXCESSIVE_CLASS_LENGTH_RULE_NAME)
    if rule is None:
        return []
    threshold = _integer_property(rule, "minimum")
    ignore_whitespace = _boolean_property(rule, "ignore-whitespace")
    start = class_info.node.lineno
    end = class_info.node.end_lineno or start
    lines = source_lines[start - 1 : end]
    line_count = sum(bool(line.strip()) for line in lines) if ignore_whitespace else len(lines)
    if line_count < threshold:
        return []
    return [
        _class_finding(
            path,
            class_info,
            rule,
            f"The class {class_info.name} has {line_count} lines of code. "
            f"Current threshold is set to {threshold}. Avoid really long classes.",
        )
    ]


def _excessive_public_count_findings(
    path: Path, class_info: ClassInfo, rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, EXCESSIVE_PUBLIC_COUNT_RULE_NAME)
    if rule is None:
        return []
    threshold = _integer_property(rule, "minimum")
    count = sum(_is_public(name) for name in class_info.fields) + sum(
        _is_public(method.name)
        for method in class_info.methods
        if not _is_contract_method(method)
    )
    if count < threshold:
        return []
    return [
        _class_finding(
            path,
            class_info,
            rule,
            f"The class {class_info.name} has {count} public methods and attributes. "
            f"Consider reducing the number of public items to less than {threshold}.",
        )
    ]


def _too_many_fields_findings(
    path: Path, class_info: ClassInfo, rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, TOO_MANY_FIELDS_RULE_NAME)
    if rule is None:
        return []
    threshold = _integer_property(rule, "maxfields")
    count = len(class_info.fields)
    if count <= threshold:
        return []
    return [
        _class_finding(
            path,
            class_info,
            rule,
            f"The class {class_info.name} has {count} fields. Consider redesigning {class_info.name} "
            f"to keep the number of fields under {threshold}.",
        )
    ]


def _too_many_methods_findings(
    path: Path, class_info: ClassInfo, rules: Sequence[LoadedRule], public_only: bool
) -> list[Finding]:
    name = TOO_MANY_PUBLIC_METHODS_RULE_NAME if public_only else TOO_MANY_METHODS_RULE_NAME
    rule = _rule(rules, name)
    if rule is None:
        return []
    threshold = _integer_property(rule, "maxmethods")
    ignore = _ignore_pattern(rule)
    methods = [
        method
        for method in class_info.methods
        if not _is_contract_method(method)
        and not ignore.match(method.name)
        and (not public_only or _is_public(method.name))
    ]
    count = len(methods)
    if count <= threshold:
        return []
    return [_class_finding(path, class_info, rule, _too_many_methods_message(class_info, count, threshold, public_only))]


def _too_many_methods_message(
    class_info: ClassInfo, count: int, threshold: int, public_only: bool
) -> str:
    if public_only:
        return (
            f"The class {class_info.name} has {count} public methods. Consider refactoring {class_info.name} "
            f"to keep number of public methods under {threshold}."
        )
    return (
        f"The class {class_info.name} has {count} non-getter- and setter-methods. "
        f"Consider refactoring {class_info.name} to keep number of methods under {threshold}."
    )


def _excessive_class_complexity_findings(
    path: Path, class_info: ClassInfo, rules: Sequence[LoadedRule]
) -> list[Finding]:
    rule = _rule(rules, EXCESSIVE_CLASS_COMPLEXITY_RULE_NAME)
    if rule is None:
        return []
    threshold = _integer_property(rule, "maximum")
    complexity = sum(
        _cyclomatic_complexity(method)
        for method in class_info.methods
        if not _is_contract_method(method)
    )
    if complexity < threshold:
        return []
    return [
        _class_finding(
            path,
            class_info,
            rule,
            f"The class {class_info.name} has an overall complexity of {complexity} which is very high. "
            f"The configured complexity threshold is {threshold}.",
        )
    ]


def _classes(tree: ast.Module) -> list[ClassInfo]:
    classes = []
    protocol_names = _protocol_base_names(tree)
    visitor_ids = _ast_visitor_class_ids(tree)
    qualified_names, classes_by_qualified_name = _qualified_class_index(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or _is_protocol(node, protocol_names):
            continue
        classes.append(
            _class_info(
                node,
                id(node) in visitor_ids,
                _has_unresolved_base(node, qualified_names, classes_by_qualified_name),
            )
        )
    return sorted(classes, key=lambda class_info: class_info.node.lineno)


def _ast_visitor_class_ids(tree: ast.Module) -> set[int]:
    class_nodes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    visitor_ids = _direct_ast_visitor_class_ids(class_nodes, _class_import_aliases(tree))
    qualified_names, classes_by_qualified_name = _qualified_class_index(tree)
    inherited_ids = _inherited_ast_visitor_class_ids(
        class_nodes,
        qualified_names,
        classes_by_qualified_name,
        visitor_ids,
    )
    return visitor_ids | inherited_ids


def _child_statements(node: ast.AST) -> list[ast.stmt]:
    statements: list[ast.stmt] = []
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.stmt):
            statements.append(child)
        elif isinstance(child, (ast.match_case, ast.ExceptHandler)):
            statements.extend(child.body)
    return statements


def _base_dotted_name(node: ast.expr) -> str:
    while isinstance(node, ast.Subscript):
        node = node.value
    return _dotted_name(node)


def _direct_ast_visitor_class_ids(
    class_nodes: list[ast.ClassDef],
    aliases_by_class: dict[int, dict[str, tuple[str, bool]]],
) -> set[int]:
    visitor_bases = {"ast.NodeVisitor", "ast.NodeTransformer"}
    return {
        id(node)
        for node in class_nodes
        if {
            _resolved_import_name(base, aliases_by_class.get(id(node), {}))
            for base in node.bases
        }
        & visitor_bases
    }


def _class_import_aliases(tree: ast.Module) -> dict[int, dict[str, tuple[str, bool]]]:
    aliases_by_class: dict[int, dict[str, tuple[str, bool]]] = {}
    _index_class_import_aliases(tree.body, {}, aliases_by_class)
    return aliases_by_class


def _index_class_import_aliases(
    statements: list[ast.stmt],
    inherited: dict[str, tuple[str, bool]],
    aliases_by_class: dict[int, dict[str, tuple[str, bool]]],
) -> None:
    aliases = dict(inherited)
    for statement in statements:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            aliases.update(_statement_import_aliases(statement))
            continue
        if isinstance(statement, ast.ClassDef):
            aliases_by_class[id(statement)] = dict(aliases)
            _index_class_import_aliases(statement.body, aliases, aliases_by_class)
            aliases.pop(statement.name, None)
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _index_class_import_aliases(statement.body, aliases, aliases_by_class)
            aliases.pop(statement.name, None)
            continue
        for name in _statement_assigned_names(statement):
            aliases.pop(name, None)
        child_statements = _child_statements(statement)
        _index_class_import_aliases(child_statements, aliases, aliases_by_class)


def _statement_import_aliases(
    statement: ast.Import | ast.ImportFrom,
) -> dict[str, tuple[str, bool]]:
    if isinstance(statement, ast.Import):
        return {
            item.asname or item.name.split(".", 1)[0]: (
                item.name if item.asname else item.name.split(".", 1)[0],
                False,
            )
            for item in statement.names
        }
    module = _import_from_module(statement)
    return {
        item.asname or item.name: (_imported_name(module, item.name), True)
        for item in statement.names
    }


def _statement_assigned_names(statement: ast.stmt) -> set[str]:
    if isinstance(statement, ast.Assign):
        return {name for target in statement.targets for name in _assigned_names(target)}
    if isinstance(statement, (ast.AnnAssign, ast.AugAssign)):
        return set(_assigned_names(statement.target))
    return set()


def _inherited_ast_visitor_class_ids(
    class_nodes: list[ast.ClassDef],
    qualified_names: dict[int, str],
    classes_by_qualified_name: defaultdict[str, list[ast.ClassDef]],
    direct_ids: set[int],
) -> set[int]:
    visitor_ids = set(direct_ids)
    changed = True
    while changed:
        changed = False
        for node in class_nodes:
            if id(node) in visitor_ids:
                continue
            if _has_known_visitor_base(
                node,
                qualified_names,
                classes_by_qualified_name,
                visitor_ids,
            ):
                visitor_ids.add(id(node))
                changed = True
    return visitor_ids - direct_ids


def _has_known_visitor_base(
    node: ast.ClassDef,
    qualified_names: dict[int, str],
    classes_by_qualified_name: defaultdict[str, list[ast.ClassDef]],
    visitor_ids: set[int],
) -> bool:
    for base in node.bases:
        base_node = _local_base_class(
            node,
            _base_dotted_name(base),
            qualified_names,
            classes_by_qualified_name,
        )
        if base_node is not None and id(base_node) in visitor_ids:
            return True
    return False


def _qualified_class_index(
    tree: ast.Module,
) -> tuple[dict[int, str], defaultdict[str, list[ast.ClassDef]]]:
    qualified_names: dict[int, str] = {}
    classes_by_name: defaultdict[str, list[ast.ClassDef]] = defaultdict(list)
    _index_qualified_classes(tree.body, "", qualified_names, classes_by_name)
    return qualified_names, classes_by_name


def _index_qualified_classes(
    statements: list[ast.stmt],
    prefix: str,
    qualified_names: dict[int, str],
    classes_by_name: defaultdict[str, list[ast.ClassDef]],
) -> None:
    for statement in statements:
        if isinstance(statement, ast.ClassDef):
            qualified_name = f"{prefix}.{statement.name}" if prefix else statement.name
            qualified_names[id(statement)] = qualified_name
            classes_by_name[qualified_name].append(statement)
            _index_qualified_classes(statement.body, qualified_name, qualified_names, classes_by_name)
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_prefix = f"{prefix}.{statement.name}" if prefix else statement.name
            _index_qualified_classes(statement.body, function_prefix, qualified_names, classes_by_name)
        else:
            child_statements = _child_statements(statement)
            _index_qualified_classes(child_statements, prefix, qualified_names, classes_by_name)


def _local_base_class(
    node: ast.ClassDef,
    base_name: str,
    qualified_names: dict[int, str],
    classes_by_qualified_name: defaultdict[str, list[ast.ClassDef]],
) -> ast.ClassDef | None:
    owner_name = qualified_names.get(id(node))
    if owner_name is None:
        return None
    owner_parts = owner_name.split(".")[:-1]
    candidate_names = [
        ".".join([*owner_parts[:depth], base_name])
        for depth in range(len(owner_parts), -1, -1)
    ]
    for candidate_name in candidate_names:
        earlier = [candidate for candidate in classes_by_qualified_name[candidate_name] if candidate.lineno < node.lineno]
        if earlier:
            return earlier[-1]
    return None


def _has_unresolved_base(
    node: ast.ClassDef,
    qualified_names: dict[int, str],
    classes_by_qualified_name: defaultdict[str, list[ast.ClassDef]],
) -> bool:
    return any(
        _local_base_class(node, _base_dotted_name(base), qualified_names, classes_by_qualified_name) is None
        for base in node.bases
    )


def _resolved_import_name(
    node: ast.expr,
    aliases: dict[str, tuple[str, bool]],
) -> str:
    name = _base_dotted_name(node)
    root, *tail = name.split(".")
    if root not in aliases:
        return ""
    imported, _is_symbol = aliases[root]
    return ".".join([imported, *tail])


def _ast_visitor_method_ids(tree: ast.Module) -> set[int]:
    visitor_ids = _ast_visitor_class_ids(tree)
    return {
        id(statement)
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and id(node) in visitor_ids
        for statement in _class_member_statements(node.body)
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _is_ast_visitor_handler(statement.name)
    }


def _class_info(node: ast.ClassDef, is_ast_visitor: bool, has_unresolved_base: bool) -> ClassInfo:
    members = _class_member_statements(node.body)
    methods = tuple(
        statement
        for statement in members
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    fields = tuple(
        dict.fromkeys(
            [
                *(name for statement in members for name in _field_names(statement)),
                *(name for method in methods for name in _instance_field_names(method)),
            ]
        )
    )
    return ClassInfo(node, node.name, fields, methods, is_ast_visitor, has_unresolved_base)


def _class_member_statements(statements: Sequence[ast.stmt]) -> list[ast.stmt]:
    members: list[ast.stmt] = []
    for statement in statements:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            members.append(statement)
            continue
        if isinstance(statement, ast.ClassDef):
            continue
        members.append(statement)
        members.extend(_class_member_statements(_child_statements(statement)))
    return members


def _field_names(statement: ast.stmt) -> list[str]:
    if isinstance(statement, ast.AnnAssign):
        return _assigned_names(statement.target)
    if isinstance(statement, ast.Assign):
        return [name for target in statement.targets for name in _assigned_names(target)]
    if isinstance(statement, ast.AugAssign):
        return _assigned_names(statement.target)
    return []


def _assigned_names(target: ast.AST) -> list[str]:
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, ast.Starred):
        return _assigned_names(target.value)
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for element in target.elts for name in _assigned_names(element)]
    return []


def _instance_field_names(method: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    receiver = _instance_receiver(method)
    if receiver is None:
        return []
    collector = _InstanceFieldCollector(receiver)
    for statement in method.body:
        collector.visit(statement)
    return collector.names


def _instance_receiver(method: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    if _has_decorator(method, "staticmethod"):
        return None
    arguments = [*method.args.posonlyargs, *method.args.args]
    if not arguments:
        return None
    receiver = arguments[0].arg
    if receiver == "self" or (_has_decorator(method, "classmethod") and receiver == "cls"):
        return receiver
    return None


def _shadows_receiver(function: ast.FunctionDef | ast.AsyncFunctionDef, receiver: str) -> bool:
    arguments = function.args
    candidates = [
        *arguments.posonlyargs,
        *arguments.args,
        *arguments.kwonlyargs,
        arguments.vararg,
        arguments.kwarg,
    ]
    return any(argument is not None and argument.arg == receiver for argument in candidates)


class _InstanceFieldCollector(ast.NodeVisitor):
    def __init__(self, receiver: str) -> None:
        self.receiver = receiver
        self.names: list[str] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if _shadows_receiver(node, self.receiver):
            return
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if _shadows_receiver(node, self.receiver):
            return
        self.generic_visit(node)

    def visit_Lambda(self, _node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, _node: ast.ClassDef) -> None:
        return

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if (
            isinstance(node.ctx, ast.Store)
            and isinstance(node.value, ast.Name)
            and node.value.id == self.receiver
        ):
            self.names.append(node.attr)
        self.generic_visit(node)


def _protocol_base_names(tree: ast.Module) -> set[str]:
    return {
        alias.asname or alias.name
        for statement in tree.body
        if isinstance(statement, ast.ImportFrom) and statement.module == "typing"
        for alias in statement.names
        if alias.name == "Protocol"
    } | {"Protocol"}


def _is_protocol(node: ast.ClassDef, protocol_names: set[str] | None = None) -> bool:
    names = protocol_names or {"Protocol"}
    return any(_is_protocol_base(base, names) for base in node.bases)


def _is_protocol_base(base: ast.AST, protocol_names: set[str]) -> bool:
    target = base.value if isinstance(base, ast.Subscript) else base
    return (
        isinstance(target, ast.Name) and target.id in protocol_names
    ) or (isinstance(target, ast.Attribute) and target.attr == "Protocol")


def _is_contract_method(
    method: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    return _has_decorator(method, "overload") or _is_stub_body(method.body)


def _is_ast_visitor_handler(name: str) -> bool:
    return re.fullmatch(r"visit_(?:[A-Z][A-Za-z0-9]*|arg|comprehension)", name) is not None


def _has_property_decorator(method: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return _has_decorator(method, "property") or any(
        isinstance(decorator, ast.Attribute) and decorator.attr in {"getter", "setter", "deleter"}
        for decorator in method.decorator_list
    )


def _has_decorator(method: ast.FunctionDef | ast.AsyncFunctionDef, name: str) -> bool:
    return any(
        (isinstance(decorator, ast.Name) and decorator.id == name)
        or (isinstance(decorator, ast.Attribute) and decorator.attr == name)
        for decorator in method.decorator_list
    )


def _is_stub_body(statements: Sequence[ast.stmt]) -> bool:
    body = _body_without_docstring(statements)
    if not body:
        return True
    if all(isinstance(statement, ast.Pass) for statement in body):
        return True
    return len(body) == 1 and (_is_ellipsis_statement(body[0]) or (
        isinstance(body[0], ast.Raise) and _raises_not_implemented(body[0])
    ))


def _body_without_docstring(statements: Sequence[ast.stmt]) -> list[ast.stmt]:
    body = list(statements)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def _is_ellipsis_statement(statement: ast.stmt) -> bool:
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and statement.value.value is Ellipsis
    )


def _raises_not_implemented(statement: ast.Raise) -> bool:
    exception = statement.exc
    if isinstance(exception, ast.Name):
        return exception.id == "NotImplementedError"
    return isinstance(exception, ast.Call) and isinstance(exception.func, ast.Name) and exception.func.id == "NotImplementedError"


def _is_public(name: str) -> bool:
    return not name.startswith("_")


def _rule(rules: Sequence[LoadedRule], name: str) -> LoadedRule | None:
    return next((candidate for candidate in rules if candidate.name == name), None)


def _has_any_rule(rule_names: AbstractSet[str], names: AbstractSet[str]) -> bool:
    return bool(rule_names & names)


def _integer_property(rule: LoadedRule, property_name: str) -> int:
    try:
        return int(rule.properties[property_name])
    except (KeyError, ValueError) as error:
        raise RulesetError(f"{rule.name} property '{property_name}' must be an integer.") from error


def _boolean_property(rule: LoadedRule, property_name: str) -> bool:
    value = rule.properties.get(property_name, "false").casefold()
    if value == "true":
        return True
    if value == "false":
        return False
    raise RulesetError(f"{rule.name} property '{property_name}' must be true or false.")


def _ignore_pattern(rule: LoadedRule) -> re.Pattern[str]:
    value = rule.properties.get("ignorepattern", "").strip()
    ignore_case = value.endswith(")i")
    pattern = value[:-1].strip() if ignore_case else value
    if not pattern:
        # An empty (or whitespace-only) pattern would match every name, so it
        # excludes nothing: fall back to a pattern that never matches.
        return re.compile(r"(?!)")
    try:
        return re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as error:
        raise RulesetError(f"{rule.name} property 'ignorepattern' must be a valid regular expression.") from error


def _class_finding(path: Path, class_info: ClassInfo, rule: LoadedRule, message: str) -> Finding:
    return Finding(path, class_info.node.lineno, rule.name, rule.priority, message, context=class_info.name)


def _unsuppressed(findings: Sequence[Finding]) -> list[Finding]:
    return [finding for finding in findings if not finding.suppressed]


def _apply_suppressions(source: str, tree: ast.Module, findings: Sequence[Finding]) -> list[Finding]:
    directives, source_lines = _suppression_directives(source)
    decorated_headers = _decorated_definition_lines(tree)
    active_counts: dict[str, int] = {}
    next_line_rules: dict[int, set[str]] = {}
    directive_index = 0
    directive_count = len(directives)
    suppressed: list[Finding] = []
    for finding in sorted(findings, key=lambda candidate: candidate.line):
        while directive_index < directive_count and directives[directive_index][0] < finding.line:
            _apply_suppression_directive(
                directives[directive_index], source_lines, decorated_headers, active_counts, next_line_rules
            )
            directive_index += 1
        identity = _rule_identity(finding.rule_name)
        is_suppressed = active_counts.get(identity, 0) > 0 or identity in next_line_rules.get(
            finding.line, set()
        )
        suppressed.append(replace(finding, suppressed=is_suppressed))
    return suppressed


def _decorated_definition_lines(tree: ast.Module) -> dict[int, int]:
    decorated_headers: dict[int, int] = {}
    for node in ast.walk(tree):
        decorators = getattr(node, "decorator_list", None)
        if not decorators:
            continue
        header_line = node.lineno
        for line in range(decorators[0].lineno, header_line):
            decorated_headers[line] = header_line
    return decorated_headers


def _apply_suppression_directive(
    directive: tuple[int, str, set[str]],
    source_lines: list[int],
    decorated_headers: dict[int, int],
    active_counts: dict[str, int],
    next_line_rules: dict[int, set[str]],
) -> None:
    line, action, rule_names = directive
    if action == "disable-next-line":
        next_line_index = bisect_right(source_lines, line)
        if next_line_index < len(source_lines):
            target_line = source_lines[next_line_index]
            next_line_rules.setdefault(target_line, set()).update(rule_names)
            header_line = decorated_headers.get(target_line)
            if header_line is not None:
                next_line_rules.setdefault(header_line, set()).update(rule_names)
        return
    delta = 1 if action == "disable" else -1
    for rule_name in rule_names:
        active_counts[rule_name] = max(0, active_counts.get(rule_name, 0) + delta)


def _suppression_directives(source: str) -> tuple[list[tuple[int, str, set[str]]], list[int]]:
    directives: list[tuple[int, str, set[str]]] = []
    source_lines: set[int] = set()
    ignored_tokens = {
        token.COMMENT,
        token.DEDENT,
        token.ENDMARKER,
        token.INDENT,
        token.NEWLINE,
        token.NL,
    }
    for item in tokenize.generate_tokens(StringIO(source).readline):
        if item.type == token.COMMENT:
            directive = _suppression_directive(item.string, item.start[0])
            if directive is not None:
                directives.append(directive)
        elif item.type not in ignored_tokens:
            source_lines.add(item.start[0])
    return directives, sorted(source_lines)


def _suppression_directive(comment: str, line: int) -> tuple[int, str, set[str]] | None:
    match = DIRECTIVE_PATTERN.fullmatch(comment[1:].strip())
    if match is None:
        return None
    rule_text = match.group(2)
    if rule_text is None or re.search(r",\s*(?:,|$)", rule_text):
        return None
    rule_names = re.split(r"[\s,]+", rule_text.strip())
    if not rule_names or not all(RULE_NAME_PATTERN.fullmatch(name) for name in rule_names):
        return None
    return line, match.group(1).casefold(), {_rule_identity(name) for name in rule_names}


def _rule_identity(name: str) -> str:
    return name.casefold()


def _source_files(
    paths: Sequence[Path], suffixes: AbstractSet[str], exclusions: Sequence[str], ignore_tests: bool
) -> list[Path]:
    source_files: set[Path] = set()
    for path in paths:
        source_files.update(_source_files_under(path, suffixes, exclusions, ignore_tests))
    return sorted(source_files, key=lambda candidate: candidate.as_posix())


def _source_files_under(
    path: Path, suffixes: AbstractSet[str], exclusions: Sequence[str], ignore_tests: bool
) -> set[Path]:
    if _is_excluded(path, exclusions) or (ignore_tests and _is_test_path(path)):
        return set()
    if path.is_file():
        return {path} if path.suffix.lower() in suffixes else set()
    if not path.is_dir():
        raise OSError("Input path does not exist")

    source_files: set[Path] = set()
    for candidate in sorted(path.iterdir(), key=lambda entry: entry.name):
        source_files.update(_source_files_for_candidate(candidate, suffixes, exclusions, ignore_tests))
    return source_files


def _source_files_for_candidate(
    candidate: Path,
    suffixes: AbstractSet[str],
    exclusions: Sequence[str],
    ignore_tests: bool,
) -> set[Path]:
    if candidate.is_dir():
        if candidate.is_symlink() or candidate.name.lower() in DEFAULT_IGNORED_DIRECTORY_NAMES:
            return set()
        return _source_files_under(candidate, suffixes, exclusions, ignore_tests)
    if not candidate.is_file() or candidate.suffix.lower() not in suffixes:
        return set()
    if _is_excluded(candidate, exclusions) or (ignore_tests and _is_test_path(candidate)):
        return set()
    return {candidate.resolve()}


def _split_nonempty(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _normalized_suffixes(value: str) -> set[str]:
    return {
        suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}"
        for suffix in _split_nonempty(value)
    }


def _is_excluded(path: Path, exclusions: Sequence[str]) -> bool:
    return any(exclusion in path.parts for exclusion in exclusions)


def _is_test_path(path: Path) -> bool:
    return (
        any(part.lower() in TEST_DIRECTORY_NAMES for part in path.parts[:-1])
        or path.name.lower().startswith("test_")
        or path.stem.lower().endswith("_test")
    )


def _help_text() -> str:
    return (
        "usage: messpy <paths> <format> <ruleset[,ruleset...]> [options]\n"
        "formats: text, xml, json, html, ansi, github, gitlab, checkstyle, sarif\n"
        "\n"
        "Source discovery:\n"
        "  --suffixes <list>  Replace source suffixes (default: .py,.pyi)\n"
        "  --exclude <paths>  Skip matching source paths\n"
        "  --ignore-tests     Skip test_*.py, *_test.py, and test or tests directories\n"
        "  Input directory symlinks are scanned; nested directory symlinks are skipped.\n"
        "\n"
        "Reporting:\n"
        "  --reportfile <path>               Write the complete report to a file\n"
        "  --color <auto|always|never>       Text color: auto on TTY, always, or never\n"
        "  --strict                          Include suppressed findings\n"
        "  --only, --enable, --disable <list> Filter loaded rules\n"
        "  --minimumpriority <1-5>           Include priorities at or above the lower bound\n"
        "  --maximumpriority <1-5>           Include priorities at or below the upper bound\n"
        "  --verbose                         Show deterministic ruleset diagnostics\n"
        "  --ignore-errors-on-exit           Return success despite processing errors\n"
        "  --ignore-violations-on-exit       Return success despite findings\n"
        "\n"
        "Exit codes: 0 clean, 1 errors, 2 findings.\n"
    )
