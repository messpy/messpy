from __future__ import annotations

import ast
import json
import os
from io import StringIO
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from messpy.cli import run, _direct_bindings, _is_protocol, _protocol_base_names


FIXTURES = Path(__file__).parent / "fixtures"


class CommandAcceptanceTests(unittest.TestCase):
    def test_directory_scan_recurses_over_python_files_in_path_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            first = project / "a_first.py"
            second = project / "nested" / "z_second.pyi"
            first.write_text(_long_function("first"), encoding="utf-8")
            second.parent.mkdir()
            second.write_text(_long_function("second"), encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(project), "text", "codesize"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual(
            "\n".join(
                [
                    _finding_for(first, "first"),
                    _finding_for(second, "second"),
                    "",
                ]
            ),
            stdout.getvalue(),
        )
        self.assertEqual("", stderr.getvalue())

    def test_overlapping_and_repeated_roots_do_not_duplicate_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            root_file = project / "root.py"
            nested_file = project / "package" / "nested.py"
            root_file.write_text(_long_function("root"), encoding="utf-8")
            nested_file.parent.mkdir()
            nested_file.write_text(_long_function("nested"), encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run(
                [
                    f"{project},{project / 'package'},{root_file},{project}",
                    "text",
                    "codesize",
                ],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual(
            "\n".join(
                [
                    _finding_for(nested_file, "nested"),
                    _finding_for(root_file, "root"),
                    "",
                ]
            ),
            stdout.getvalue(),
        )
        self.assertEqual("", stderr.getvalue())

    def test_directory_scan_skips_dependency_cache_and_generated_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            included = project / "application.py"
            included.write_text(_long_function("application"), encoding="utf-8")
            for directory in [
                ".git",
                ".venv/lib/python/site-packages",
                "__pycache__",
                ".mypy_cache",
                ".pytest_cache",
                ".ruff_cache",
                ".tox",
                "build",
                "coverage",
                "dist",
                "generated",
            ]:
                ignored = project / directory / "ignored.py"
                ignored.parent.mkdir(parents=True, exist_ok=True)
                ignored.write_text(_long_function("ignored"), encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(project), "text", "codesize"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual(f"{_finding_for(included, 'application')}\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_suffixes_replaces_the_default_source_suffixes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            module = project / "module.py"
            stub = project / "interface.pyi"
            module.write_text(_long_function("module"), encoding="utf-8")
            stub.write_text(_long_function("interface"), encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(project), "text", "codesize", "--suffixes", ".pyi"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual(f"{_finding_for(stub, 'interface')}\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_exclude_omits_matching_source_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            included = project / "application.py"
            excluded = project / "vendorized" / "schema.py"
            included.write_text(_long_function("application"), encoding="utf-8")
            excluded.parent.mkdir()
            excluded.write_text(_long_function("schema"), encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(project), "text", "codesize", "--exclude", "vendorized"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual(f"{_finding_for(included, 'application')}\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_exclude_omits_a_matching_source_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            included = project / "application.py"
            excluded = project / "generated_client.py"
            included.write_text(_long_function("application"), encoding="utf-8")
            excluded.write_text(_long_function("generated_client"), encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run(
                [str(project), "text", "codesize", "--exclude", "generated_client.py"], stdout, stderr
            )

        self.assertEqual(2, status)
        self.assertEqual(f"{_finding_for(included, 'application')}\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_exclude_matches_whole_path_components_without_absolute_substrings(self) -> None:
        with tempfile.TemporaryDirectory(prefix="src-messpy-exclude-") as temporary_directory:
            project = Path(temporary_directory)
            sources = {
                "app.py": project / "app.py",
                "host.py": project / "host.py",
                "most.py": project / "most.py",
                "nested.py": project / "src" / "nested.py",
            }
            for source in sources.values():
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(_long_function(source.stem), encoding="utf-8")

            def run_with_exclusion(exclusion: str) -> tuple[int, str, str]:
                stdout = StringIO()
                stderr = StringIO()
                status = run(
                    [str(project), "text", "codesize", "--exclude", exclusion], stdout, stderr
                )
                return status, stdout.getvalue(), stderr.getvalue()

            expected_all = "\n".join(
                _finding_for(source, source.stem) for source in sources.values()
            ) + "\n"
            expected_without_nested = "\n".join(
                _finding_for(sources[name], sources[name].stem)
                for name in ("app.py", "host.py", "most.py")
            ) + "\n"
            expected_without_host = "\n".join(
                _finding_for(sources[name], sources[name].stem)
                for name in ("app.py", "most.py", "nested.py")
            ) + "\n"

            for exclusion in ["os", ".", "py"]:
                with self.subTest(exclusion=exclusion):
                    status, report, errors = run_with_exclusion(exclusion)
                    self.assertEqual(2, status)
                    self.assertEqual(expected_all, report)
                    self.assertEqual("", errors)

            with self.subTest(exclusion="src"):
                status, report, errors = run_with_exclusion("src")
                self.assertEqual(2, status)
                self.assertEqual(expected_without_nested, report)
                self.assertEqual("", errors)

            with self.subTest(exclusion="host.py"):
                status, report, errors = run_with_exclusion("host.py")
                self.assertEqual(2, status)
                self.assertEqual(expected_without_host, report)
                self.assertEqual("", errors)

    def test_ignore_tests_omits_conventional_test_files_and_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            application = project / "application.py"
            test_module = project / "test_application.py"
            suffix_test = project / "application_test.py"
            test_package = project / "tests" / "integration.py"
            for path, name in [
                (application, "application"),
                (test_module, "test_module"),
                (suffix_test, "suffix_test"),
                (test_package, "test_package"),
            ]:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(_long_function(name), encoding="utf-8")

            included_stdout = StringIO()
            included_stderr = StringIO()
            included_status = run([str(project), "text", "codesize"], included_stdout, included_stderr)
            ignored_stdout = StringIO()
            ignored_stderr = StringIO()
            ignored_status = run(
                [str(project), "text", "codesize", "--ignore-tests"], ignored_stdout, ignored_stderr
            )

        self.assertEqual(2, included_status)
        self.assertEqual(
            "\n".join(
                [
                    _finding_for(application, "application"),
                    _finding_for(suffix_test, "suffix_test"),
                    _finding_for(test_module, "test_module"),
                    _finding_for(test_package, "test_package"),
                    "",
                ]
            ),
            included_stdout.getvalue(),
        )
        self.assertEqual("", included_stderr.getvalue())
        self.assertEqual(2, ignored_status)
        self.assertEqual(f"{_finding_for(application, 'application')}\n", ignored_stdout.getvalue())
        self.assertEqual("", ignored_stderr.getvalue())

    def test_directory_symlinks_are_not_followed_during_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            project = workspace / "project"
            source_directory = project / "source"
            source = source_directory / "module.py"
            external_directory = workspace / "external"
            external = external_directory / "external.py"
            source_directory.mkdir(parents=True)
            external_directory.mkdir()
            source.write_text(_long_function("module"), encoding="utf-8")
            external.write_text(_long_function("external"), encoding="utf-8")
            (project / "linked_source").symlink_to(external_directory, target_is_directory=True)

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(project), "text", "codesize"], stdout, stderr)
            linked_stdout = StringIO()
            linked_stderr = StringIO()
            linked_status = run([str(project / "linked_source"), "text", "codesize"], linked_stdout, linked_stderr)

        self.assertEqual(2, status)
        self.assertEqual(f"{_finding_for(source, 'module')}\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(2, linked_status)
        self.assertEqual(f"{_finding_for(external, 'external')}\n", linked_stdout.getvalue())
        self.assertEqual("", linked_stderr.getvalue())

    def test_clean_python_file_exits_zero_without_a_report(self) -> None:
        stdout = StringIO()
        stderr = StringIO()

        status = run([str(FIXTURES / "clean.py"), "text", "codesize"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_long_python_function_has_a_stable_codesize_finding(self) -> None:
        stdout = StringIO()
        stderr = StringIO()

        long_function = (FIXTURES / "long_function.py").resolve()
        status = run([str(long_function), "text", "codesize"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual(
            "tests/fixtures/long_function.py:1: ExcessiveMethodLength "
            "[priority 3] The function too_long() has 101 lines of code. "
            "Current threshold is set to 100. Avoid really long methods.\n",
            stdout.getvalue(),
        )
        self.assertEqual("", stderr.getvalue())

    def test_json_report_contains_the_normalized_finding_record(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        source = (FIXTURES / "long_function.py").resolve()

        status = run([str(source), "json", "codesize"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(
            {
                "tool": {"name": "messpy", "version": "0.1.13"},
                "findings": [
                    {
                        "path": "tests/fixtures/long_function.py",
                        "line": 1,
                        "column": 1,
                        "ruleName": "ExcessiveMethodLength",
                        "priority": 3,
                        "message": "The function too_long() has 101 lines of code. Current threshold is set to 100. Avoid really long methods.",
                        "context": "too_long",
                        "suppressed": False,
                    }
                ],
                "errors": [],
            },
            json.loads(stdout.getvalue()),
        )

    def test_public_reports_keep_one_finding_and_one_processing_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            finding_source = project / "finding&source.py"
            malformed_source = project / "malformed.py"
            finding_source.write_text(_long_function("too_long"), encoding="utf-8")
            malformed_source.write_text("def broken(:\n", encoding="utf-8")

            reports: dict[str, str] = {}
            for report_format in [
                "text",
                "xml",
                "json",
                "html",
                "ansi",
                "github",
                "gitlab",
                "checkstyle",
                "sarif",
            ]:
                stdout = StringIO()
                stderr = StringIO()
                status = run([str(project), report_format, "codesize"], stdout, stderr)

                self.assertEqual(1, status, report_format)
                self.assertEqual("", stderr.getvalue(), report_format)
                reports[report_format] = stdout.getvalue()

        for report_format in ["text", "html", "ansi", "github"]:
            self.assertIn("ExcessiveMethodLength", reports[report_format])
            self.assertIn("ProcessingError", reports[report_format])
        self.assertIn("finding&amp;source.py", reports["html"])
        self.assertIn("\x1b[", reports["ansi"])
        self.assertIn("::warning file=", reports["github"])
        self.assertIn("::error file=", reports["github"])

        xml = ElementTree.fromstring(reports["xml"])
        self.assertEqual("messpy", xml.tag)
        self.assertEqual("0.1.13", xml.get("version"))
        self.assertEqual("too_long", xml.find("./findings/finding").get("context"))
        self.assertEqual("ProcessingError", xml.find("./errors/error").get("ruleName"))

        json_report = json.loads(reports["json"])
        self.assertEqual("too_long", json_report["findings"][0]["context"])
        self.assertEqual("ProcessingError", json_report["errors"][0]["ruleName"])

        checkstyle = ElementTree.fromstring(reports["checkstyle"])
        self.assertEqual("checkstyle", checkstyle.tag)
        self.assertEqual(2, len(checkstyle.findall(".//error")))

        gitlab = json.loads(reports["gitlab"])
        self.assertEqual(["ExcessiveMethodLength", "ProcessingError"], [entry["check_name"] for entry in gitlab])
        self.assertEqual({"name": "messpy", "version": "0.1.13"}, gitlab[0]["tool"])
        self.assertEqual(
            (
                f"{finding_source.resolve().as_posix()}:1:1:ExcessiveMethodLength:"
                "The function too_long() has 101 lines of code. Current threshold is set to 100. Avoid really long methods."
            ).encode("utf-8").hex(),
            gitlab[0]["fingerprint"],
        )

        sarif = json.loads(reports["sarif"])
        run_record = sarif["runs"][0]
        self.assertEqual("2.1.0", sarif["version"])
        self.assertEqual("messpy", run_record["tool"]["driver"]["name"])
        self.assertEqual("ExcessiveMethodLength", run_record["results"][0]["ruleId"])
        self.assertFalse(run_record["invocations"][0]["executionSuccessful"])

    @unittest.skipIf(
        sys.platform == "win32",
        "Windows rejects control characters in file names, so this file cannot exist there.",
    )
    def test_xml_and_checkstyle_reports_stay_well_formed_for_control_characters_in_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            source = project / ("bad" + chr(1) + "name.py")
            source.write_text("def f():\n    return 1\n", encoding="utf-8")

            for report_format in ["xml", "checkstyle"]:
                stdout = StringIO()
                stderr = StringIO()
                status = run([str(project), report_format, "python"], stdout, stderr)

                self.assertEqual(2, status, report_format)
                self.assertEqual("", stderr.getvalue(), report_format)
                ElementTree.fromstring(stdout.getvalue())  # raises ParseError if not well-formed
                self.assertIn("\\x01", stdout.getvalue(), report_format)
                self.assertNotIn("\x01", stdout.getvalue(), report_format)

    @unittest.skipIf(
        sys.platform == "win32",
        "Windows rejects control characters in file names, so this file cannot exist there.",
    )
    def test_xml_and_checkstyle_reports_stay_well_formed_for_control_characters_in_error_messages(
        self,
    ) -> None:
        # A processing error carries the offending path into its message (see
        # "Could not process {source_file}: ..." in _analyze), so a control
        # character in the path also reaches the message field, not only the
        # path field. Pair it with invalid UTF-8 bytes so the file raises a
        # ProcessingError instead of parsing cleanly.
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            source = project / ("bad" + chr(1) + "name.py")
            source.write_bytes(b"\xff\xfe not valid utf-8")

            for report_format in ["xml", "checkstyle"]:
                stdout = StringIO()
                stderr = StringIO()
                status = run([str(project), report_format, "python"], stdout, stderr)

                self.assertEqual(1, status, report_format)
                self.assertEqual("", stderr.getvalue(), report_format)
                report = ElementTree.fromstring(stdout.getvalue())  # raises ParseError if not well-formed
                message = report.find(".//error").get("message")
                self.assertIn("\\x01", message, report_format)
                self.assertNotIn("\x01", stdout.getvalue(), report_format)

    def test_text_color_controls_do_not_color_redirected_output_by_default(self) -> None:
        source = str((FIXTURES / "long_function.py").resolve())
        reports: dict[str, str] = {}
        for option in [[], ["--color", "always"], ["--color", "never"]]:
            stdout = StringIO()
            stderr = StringIO()
            status = run([source, "text", "codesize", *option], stdout, stderr)

            self.assertEqual(2, status)
            self.assertEqual("", stderr.getvalue())
            reports[option[-1] if option else "auto"] = stdout.getvalue()

        self.assertNotIn("\x1b[", reports["auto"])
        self.assertIn("\x1b[", reports["always"])
        self.assertNotIn("\x1b[", reports["never"])

    def test_every_format_keeps_clean_status_and_report_file_content(self) -> None:
        formats = ["text", "xml", "json", "html", "ansi", "github", "gitlab", "checkstyle", "sarif"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            finding_source = temporary / "finding.py"
            finding_source.write_text(_long_function("too_long"), encoding="utf-8")
            for report_format in formats:
                clean_stdout = StringIO()
                clean_stderr = StringIO()
                clean_status = run(
                    [str(FIXTURES / "clean.py"), report_format, "codesize"], clean_stdout, clean_stderr
                )
                stdout = StringIO()
                stderr = StringIO()
                status = run([str(finding_source), report_format, "codesize"], stdout, stderr)
                report_file = temporary / f"report.{report_format}"
                file_stdout = StringIO()
                file_stderr = StringIO()
                file_status = run(
                    [
                        str(finding_source),
                        report_format,
                        "codesize",
                        "--reportfile",
                        str(report_file),
                    ],
                    file_stdout,
                    file_stderr,
                )

                self.assertEqual(0, clean_status, report_format)
                self.assertEqual("", clean_stderr.getvalue(), report_format)
                self.assertEqual(2, status, report_format)
                self.assertEqual("", stderr.getvalue(), report_format)
                self.assertEqual(2, file_status, report_format)
                self.assertEqual("", file_stdout.getvalue(), report_format)
                self.assertEqual("", file_stderr.getvalue(), report_format)
                self.assertEqual(stdout.getvalue(), report_file.read_text(encoding="utf-8"), report_format)

    def test_disable_next_line_hides_only_the_named_finding_on_the_next_source_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "suppressed.py"
            source.write_text(
                "# messpy-disable-next-line ExcessiveMethodLength\n"
                + _long_function("waived")
                + "\n"
                + _long_function("still_reported"),
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "codesize"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual(f"{_finding_for(source, 'still_reported', 104)}\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_disable_next_line_above_a_decorator_suppresses_the_decorated_definition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "decorated.py"
            source.write_text(
                "import functools\n"
                "\n"
                "\n"
                "class Widget:\n"
                "    # messpy-disable-next-line CamelCaseMethodName\n"
                "    @functools.cache\n"
                "    def getValue(self):\n"
                "        return 1\n"
                "\n"
                "    def getStillReported(self):\n"
                "        return 2\n",
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "controversial"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertNotIn("getValue", report)
        self.assertIn("The method getStillReported is not named in snake_case.", report)

    def test_disable_next_line_between_a_decorator_and_def_suppresses_the_definition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "between.py"
            source.write_text(
                "import functools\n"
                "\n"
                "\n"
                "class Widget:\n"
                "    @functools.cache\n"
                "    # messpy-disable-next-line CamelCaseMethodName\n"
                "    def getValue(self):\n"
                "        return 1\n",
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "controversial"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_disable_next_line_does_not_skip_an_unsuitable_source_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "next_line.py"
            source.write_text(
                "# messpy-disable-next-line ExcessiveMethodLength\n"
                "marker = 1\n"
                + _long_function("still_reported"),
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "codesize"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual(f"{_finding_for(source, 'still_reported', 3)}\n", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_strict_includes_a_suppressed_finding_without_changing_its_location(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "strict.py"
            source.write_text(
                "# messpy-disable-next-line excessivemethodlength\n" + _long_function("waived"),
                encoding="utf-8",
            )

            normal_stdout = StringIO()
            normal_stderr = StringIO()
            normal_status = run([str(source), "text", "codesize"], normal_stdout, normal_stderr)
            strict_stdout = StringIO()
            strict_stderr = StringIO()
            strict_status = run([str(source), "text", "codesize", "--strict"], strict_stdout, strict_stderr)

        self.assertEqual(0, normal_status)
        self.assertEqual("", normal_stdout.getvalue())
        self.assertEqual("", normal_stderr.getvalue())
        self.assertEqual(2, strict_status)
        self.assertEqual(
            f"{_finding_for(source, 'waived', 2).replace('[priority 3]', '[priority 3] [suppressed]')}\n",
            strict_stdout.getvalue(),
        )
        self.assertEqual("", strict_stderr.getvalue())

    def test_disable_next_line_skips_comments_and_blank_lines_when_many_directives_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "many_suppressions.py"
            source.write_text(
                "# messpy-disable-next-line ShortVariable\n"
                "# ordinary comment\n"
                "\n"
                "ab = 1\n"
                "# messpy-disable-next-line ShortVariable\n"
                "cd = 2\n"
                "ef = 3\n",
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "naming"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertNotIn("Avoid variables with short names like ab.", report)
        self.assertNotIn("Avoid variables with short names like cd.", report)
        self.assertIn("Avoid variables with short names like ef.", report)

    def test_regions_nest_and_malformed_or_other_tool_comments_do_not_hide_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "regions.py"
            ruleset = temporary / "policy.xml"
            source.write_text(
                "# messpy-disable ExcessiveMethodLength MissingRule\n"
                + _function_with_passes("outer", 3)
                + "# messpy-disable ExcessiveMethodLength\n"
                + _function_with_passes("nested", 3)
                + "# messpy-enable ExcessiveMethodLength\n"
                + _function_with_passes("outer_still_active", 3)
                + "# messpy-enable MissingRule\n"
                + _function_with_passes("partially_enabled", 3)
                + "# messpy-enable ExcessiveMethodLength\n"
                + _function_with_passes("released", 3)
                + "# messpy-enable ExcessiveMethodLength\n"
                + _function_with_passes("unbalanced_enable", 3)
                + "# noqa: E501\n"
                + _function_with_passes("noqa", 3)
                + "# type: ignore\n"
                + _function_with_passes("type_checker", 3)
                + "# fmt: off\n"
                + _function_with_passes("formatter", 3)
                + "# pragma: no cover\n"
                + _function_with_passes("coverage", 3)
                + "# messpy-disable\n"
                + _function_with_passes("malformed_region", 3)
                + "# messpy-disable-next-line ExcessiveMethodLength,\n"
                + _function_with_passes("malformed_next_line", 3),
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="team policy">
    <rule ref="codesize"><properties><property name="minimum" value="3" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        for name in [
            "released",
            "unbalanced_enable",
            "noqa",
            "type_checker",
            "formatter",
            "coverage",
            "malformed_region",
            "malformed_next_line",
        ]:
            self.assertIn(
                f"The function {name}() has 4 lines of code. Current threshold is set to 3. Avoid really long methods.",
                stdout.getvalue(),
            )
        for name in ["outer", "nested", "outer_still_active", "partially_enabled"]:
            self.assertNotIn(f"The function {name}() has 4 lines of code.", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_malformed_source_reports_an_error_without_hiding_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            violating = project / "violating.py"
            malformed = project / "malformed.py"
            violating.write_text(_long_function("violating"), encoding="utf-8")
            malformed.write_text("def broken(:\n", encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(project), "text", "codesize"], stdout, stderr)

        self.assertEqual(1, status)
        self.assertIn(_finding_for(violating, "violating"), stdout.getvalue())
        self.assertIn(f"{malformed.resolve().as_posix()}:1: ProcessingError", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_duplicate_parameter_name_reports_an_error_without_hiding_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            violating = project / "violating.py"
            malformed = project / "malformed.py"
            violating.write_text(_long_function("violating"), encoding="utf-8")
            malformed.write_text("def broken(s, s):\n    pass\n", encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(project), "text", "codesize,unusedcode"], stdout, stderr)

        self.assertEqual(1, status)
        self.assertIn(_finding_for(violating, "violating"), stdout.getvalue())
        self.assertIn(f"{malformed.resolve().as_posix()}:1: ProcessingError", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_invalid_source_encoding_reports_an_error_without_hiding_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            violating = project / "violating.py"
            malformed = project / "malformed.py"
            violating.write_text(_long_function("violating"), encoding="utf-8")
            malformed.write_bytes(b"\xff")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(project), "text", "codesize"], stdout, stderr)

        self.assertEqual(1, status)
        self.assertIn(_finding_for(violating, "violating"), stdout.getvalue())
        self.assertIn(f"{malformed.resolve().as_posix()}:1: ProcessingError", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_coding_cookie_decodes_source_before_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "latin1.py"
            source.write_bytes(b"# coding: latin-1\nvalue = '\xe9'\n")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "python"], stdout, stderr)

        self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_utf8_bom_is_removed_before_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "bom.py"
            source.write_bytes(b"\xef\xbb\xbfdef walk():\n    return 1\n")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "python"], stdout, stderr)

        self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_unknown_coding_cookie_reports_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "unknown_encoding.py"
            source.write_bytes(b"# coding: nonsense\nx = 1\n")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "python"], stdout, stderr)

        self.assertEqual(1, status)
        self.assertIn(f"{source.resolve().as_posix()}:1: ProcessingError", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_duplicate_function_arguments_reports_processing_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            duplicate_args = project / "duplicate_args.py"
            duplicate_args.write_text("def function(x, x):\n    pass\n", encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(duplicate_args), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(1, status)
        self.assertIn(f"{duplicate_args.resolve().as_posix()}:1: ProcessingError", stdout.getvalue())
        self.assertIn("duplicate argument 'x' in function definition", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_deeply_nested_expression_reports_processing_error_without_aborting_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            deep = project / "deep.py"
            messy = project / "messy.py"
            deep.write_text("def compute_total():\n    value = " + "+".join(["1"] * 500) + "\n    return value\n", encoding="utf-8")
            messy.write_text("def unused_example():\n    leftover = 1\n    return 0\n", encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run([f"{deep},{messy}", "text", "unusedcode"], stdout, stderr)

        self.assertEqual(1, status)
        self.assertIn(f"{deep.resolve().as_posix()}:1: ProcessingError", stdout.getvalue())
        self.assertIn("UnusedLocalVariable [priority 3] Avoid unused local variables such as 'leftover'.", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())


    def test_embedded_null_byte_in_path_reports_error_cleanly(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        status = run(["invalid\x00path.py", "text", "codesize"], stdout, stderr)

        self.assertEqual(1, status)
        self.assertEqual("", stdout.getvalue())
        self.assertTrue(stderr.getvalue().startswith("Error: "))
        if os.name == "posix":
            self.assertIn("embedded null", stderr.getvalue())



    def test_exit_ignore_flags_change_status_without_changing_the_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project = Path(temporary_directory)
            violating = project / "violating.py"
            malformed = project / "malformed.py"
            violating.write_text(_long_function("violating"), encoding="utf-8")
            malformed.write_text("def broken(:\n", encoding="utf-8")

            default_stdout = StringIO()
            default_stderr = StringIO()
            default_status = run([str(project), "text", "codesize"], default_stdout, default_stderr)
            errors_ignored_stdout = StringIO()
            errors_ignored_stderr = StringIO()
            errors_ignored_status = run(
                [str(project), "text", "codesize", "--ignore-errors-on-exit"],
                errors_ignored_stdout,
                errors_ignored_stderr,
            )
            violations_ignored_stdout = StringIO()
            violations_ignored_stderr = StringIO()
            violations_ignored_status = run(
                [str(violating), "text", "codesize", "--ignore-violations-on-exit"],
                violations_ignored_stdout,
                violations_ignored_stderr,
            )
            all_ignored_stdout = StringIO()
            all_ignored_stderr = StringIO()
            all_ignored_status = run(
                [
                    str(project),
                    "text",
                    "codesize",
                    "--ignore-errors-on-exit",
                    "--ignore-violations-on-exit",
                ],
                all_ignored_stdout,
                all_ignored_stderr,
            )

        self.assertEqual(1, default_status)
        self.assertEqual(2, errors_ignored_status)
        self.assertEqual(0, violations_ignored_status)
        self.assertEqual(0, all_ignored_status)
        self.assertEqual(default_stdout.getvalue(), errors_ignored_stdout.getvalue())
        self.assertEqual(default_stdout.getvalue(), all_ignored_stdout.getvalue())
        self.assertEqual(f"{_finding_for(violating, 'violating')}\n", violations_ignored_stdout.getvalue())
        self.assertEqual("", default_stderr.getvalue())
        self.assertEqual(default_stderr.getvalue(), errors_ignored_stderr.getvalue())
        self.assertEqual(default_stderr.getvalue(), all_ignored_stderr.getvalue())
        self.assertEqual("", violations_ignored_stderr.getvalue())

    def test_reportfile_replaces_the_complete_report_without_writing_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            report_file = temporary / "reports" / "messpy.txt"
            report_file.parent.mkdir()
            report_file.write_text("stale report", encoding="utf-8")
            source = temporary / "violating.py"
            source.write_text(_long_function("violating"), encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run(
                [str(source), "text", "codesize", "--reportfile", str(report_file)], stdout, stderr
            )

            report = report_file.read_text(encoding="utf-8")

        self.assertEqual(2, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(f"{_finding_for(source, 'violating')}\n", report)

    def test_reportfile_write_failure_is_an_operational_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "violating.py"
            source.write_text(_long_function("violating"), encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run(
                [
                    str(source),
                    "text",
                    "codesize",
                    "--reportfile",
                    str(temporary / "missing" / "messpy.txt"),
                ],
                stdout,
                stderr,
            )

        self.assertEqual(1, status)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("Unable to write report", stderr.getvalue())

    @unittest.skipIf(
        sys.platform == "win32",
        "Windows does not support POSIX file permission bits or umask.",
    )
    def test_reportfile_preserves_existing_file_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            report_file = temporary / "reports" / "messpy.txt"
            report_file.parent.mkdir()
            report_file.write_text("stale report", encoding="utf-8")
            report_file.chmod(0o640)
            source = temporary / "violating.py"
            source.write_text(_long_function("violating"), encoding="utf-8")

            stdout = StringIO()
            stderr = StringIO()
            status = run(
                [str(source), "text", "codesize", "--reportfile", str(report_file)], stdout, stderr
            )

            mode = stat.S_IMODE(report_file.stat().st_mode)

        self.assertEqual(2, status)
        self.assertEqual(0o640, mode)

    @unittest.skipIf(
        sys.platform == "win32",
        "Windows does not support POSIX file permission bits or umask.",
    )
    def test_reportfile_creates_new_file_with_umask_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            report_file = temporary / "reports" / "messpy.txt"
            report_file.parent.mkdir()
            source = temporary / "violating.py"
            source.write_text(_long_function("violating"), encoding="utf-8")

            original_umask = os.umask(0o027)
            try:
                stdout = StringIO()
                stderr = StringIO()
                status = run(
                    [str(source), "text", "codesize", "--reportfile", str(report_file)], stdout, stderr
                )
                mode = stat.S_IMODE(report_file.stat().st_mode)
            finally:
                os.umask(original_umask)

        self.assertEqual(2, status)
        self.assertEqual(0o640, mode)

    def test_command_errors_have_deterministic_diagnostics(self) -> None:
        cases = [
            ([], "Missing required arguments: <paths> <format> <ruleset[,ruleset...]>"),
            (["missing.py", "text", "codesize"], "Input path does not exist"),
            (["input.py", "text", "codesize", "--reportfile"], "Missing value for option: --reportfile"),
            (["input.py", "text", "codesize", "extra"], "Unexpected positional argument: extra"),
            (["input.py", "text", "codesize", "--unknown"], "Unknown option: --unknown"),
            (
                ["input.py", "text", "codesize", "--minimum-priority", "0"],
                "--minimum-priority expects a priority between 1 and 5, received '0'.",
            ),
            (["input.py", "unknown", "codesize"], "Unknown format: unknown"),
            (["input.py", "text", "unknown"], "Unknown ruleset 'unknown'."),
        ]

        for arguments, diagnostic in cases:
            with self.subTest(arguments=arguments):
                stdout = StringIO()
                stderr = StringIO()

                status = run(arguments, stdout, stderr)

                self.assertEqual(1, status)
                self.assertEqual("", stdout.getvalue())
                self.assertIn(diagnostic, stderr.getvalue())

    def test_custom_ruleset_composes_references_and_later_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "short.py"
            ruleset = temporary / "policy.xml"
            source.write_text(_function_with_passes("short", 3), encoding="utf-8")
            ruleset.write_text(
                """<ruleset name="team policy">
    <rule ref="rulesets/CoDeSiZe.xml"><exclude name="ExcessiveMethodLength" /></rule>
    <rule ref="excessivemethodlength">
        <priority>2</priority>
        <properties><property name="minimum" value="3" /></properties>
    </rule>
</ruleset>
""",
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", f"CoDeSiZe,{ruleset}"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual(
            f"{source.resolve().as_posix()}:1: ExcessiveMethodLength "
            "[priority 2] The function short() has 4 lines of code. "
            "Current threshold is set to 3. Avoid really long methods.\n",
            stdout.getvalue(),
        )
        self.assertEqual("", stderr.getvalue())

    def test_nested_ruleset_and_filters_select_only_loaded_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "short.py"
            nested_ruleset = temporary / "base.xml"
            ruleset = temporary / "policy.xml"
            source.write_text(_function_with_passes("short", 3), encoding="utf-8")
            nested_ruleset.write_text(
                """<ruleset name="base">
    <rule ref="codesize">
        <properties><property name="minimum" value="3" /></properties>
    </rule>
</ruleset>
""",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="team policy">
    <rule ref="base.xml" />
    <rule ref="ExcessiveMethodLength"><priority>2</priority></rule>
</ruleset>
""",
                encoding="utf-8",
            )

            enabled_stdout = StringIO()
            enabled_stderr = StringIO()
            enabled_status = run(
                [
                    str(source),
                    "text",
                    str(ruleset),
                    "--enable",
                    "EXCESSIVEMETHODLENGTH",
                    "--verbose",
                ],
                enabled_stdout,
                enabled_stderr,
            )
            disabled_stdout = StringIO()
            disabled_stderr = StringIO()
            disabled_status = run(
                [str(source), "text", str(ruleset), "--disable", "excessivemethodlength"],
                disabled_stdout,
                disabled_stderr,
            )
            priority_stdout = StringIO()
            priority_stderr = StringIO()
            priority_status = run(
                [
                    str(source),
                    "text",
                    str(ruleset),
                    "--only",
                    "ExcessiveMethodLength",
                    "--minimumpriority",
                    "3",
                ],
                priority_stdout,
                priority_stderr,
            )

        self.assertEqual(2, enabled_status)
        self.assertIn("ExcessiveMethodLength [priority 2]", enabled_stdout.getvalue())
        self.assertEqual("Loaded rules: ExcessiveMethodLength\n", enabled_stderr.getvalue())
        self.assertEqual(0, disabled_status)
        self.assertEqual("", disabled_stdout.getvalue())
        self.assertEqual("", disabled_stderr.getvalue())
        self.assertEqual(0, priority_status)
        self.assertEqual("", priority_stdout.getvalue())
        self.assertEqual("", priority_stderr.getvalue())

    def test_ruleset_loading_rejects_unknown_filter_and_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "source.py"
            ruleset = temporary / "invalid.xml"
            unknown_rule_exclusion = temporary / "unknown-rule-exclusion.xml"
            unknown_ruleset_exclusion = temporary / "unknown-ruleset-exclusion.xml"
            source.write_text(_function_with_passes("source", 3), encoding="utf-8")
            ruleset.write_text(
                """<ruleset name="invalid">
    <rule ref="not-a-ruleset" />
</ruleset>
""",
                encoding="utf-8",
            )
            unknown_rule_exclusion.write_text(
                """<ruleset name="invalid">
    <rule ref="codesize"><exclude name="ExcessiveMethodLenght" /></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            unknown_ruleset_exclusion.write_text(
                """<ruleset name="invalid">
    <rule ref="codesize" />
    <exclude name="ExcessiveMethodLenght" />
</ruleset>
""",
                encoding="utf-8",
            )

            unknown_filter_stdout = StringIO()
            unknown_filter_stderr = StringIO()
            unknown_filter_status = run(
                [str(source), "text", "codesize", "--only", "not-a-rule"],
                unknown_filter_stdout,
                unknown_filter_stderr,
            )
            unknown_reference_stdout = StringIO()
            unknown_reference_stderr = StringIO()
            unknown_reference_status = run(
                [str(source), "text", str(ruleset), "--verbose"],
                unknown_reference_stdout,
                unknown_reference_stderr,
            )
            unknown_rule_exclusion_stdout = StringIO()
            unknown_rule_exclusion_stderr = StringIO()
            unknown_rule_exclusion_status = run(
                [str(source), "text", str(unknown_rule_exclusion)],
                unknown_rule_exclusion_stdout,
                unknown_rule_exclusion_stderr,
            )
            unknown_ruleset_exclusion_stdout = StringIO()
            unknown_ruleset_exclusion_stderr = StringIO()
            unknown_ruleset_exclusion_status = run(
                [str(source), "text", str(unknown_ruleset_exclusion)],
                unknown_ruleset_exclusion_stdout,
                unknown_ruleset_exclusion_stderr,
            )

        self.assertEqual(1, unknown_filter_status)
        self.assertEqual("", unknown_filter_stdout.getvalue())
        self.assertEqual("Error: Unknown loaded rule 'not-a-rule'.\n", unknown_filter_stderr.getvalue())
        self.assertEqual(1, unknown_reference_status)
        self.assertEqual("", unknown_reference_stdout.getvalue())
        self.assertIn("Unknown ruleset reference 'not-a-ruleset'.", unknown_reference_stderr.getvalue())
        self.assertEqual(1, unknown_rule_exclusion_status)
        self.assertEqual("", unknown_rule_exclusion_stdout.getvalue())
        self.assertIn("Unknown rule exclusion 'ExcessiveMethodLenght'.", unknown_rule_exclusion_stderr.getvalue())
        self.assertEqual(1, unknown_ruleset_exclusion_status)
        self.assertEqual("", unknown_ruleset_exclusion_stdout.getvalue())
        self.assertIn("Unknown rule exclusion 'ExcessiveMethodLenght'.", unknown_ruleset_exclusion_stderr.getvalue())

    def test_ruleset_loading_rejects_unknown_property_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "source.py"
            ruleset = temporary / "invalid-property.xml"
            source.write_text("pass\n", encoding="utf-8")
            ruleset.write_text(
                """<ruleset name="invalid">
    <rule ref="LongVariable">
        <properties><property name="maximun" value="5" /></properties>
    </rule>
</ruleset>
""",
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(1, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("Error: Unknown property 'maximun' for rule 'LongVariable'.\n", stderr.getvalue())

    def test_ruleset_loading_rejects_unknown_property_on_rule_without_properties(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "source.py"
            ruleset = temporary / "invalid-property.xml"
            source.write_text("pass\n", encoding="utf-8")
            ruleset.write_text(
                """<ruleset name="invalid">
    <rule ref="BooleanGetMethodName">
        <properties><property name="typo" value="true" /></properties>
    </rule>
</ruleset>
""",
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(1, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("Error: Unknown property 'typo' for rule 'BooleanGetMethodName'.\n", stderr.getvalue())

    def test_callable_metrics_cover_python_callables_and_exact_configured_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "callables.py"
            ruleset = temporary / "callable-metrics.xml"
            parameter_ruleset = temporary / "parameter-forms.xml"
            lambda_ruleset = temporary / "lambda-metrics.xml"
            source.write_text(
                "def decision_flow(value: int | None) -> int:\n"
                "    if value and value > 0:\n        pass\n"
                "    for item in [value]:\n        pass\n"
                "    while value:\n        break\n"
                "    try:\n        raise RuntimeError\n"
                "    except RuntimeError:\n        pass\n"
                "    branch = max(1 if value else 0, 0)\n"
                "    values = [1 if item else 0 for item in range(2) if item]\n"
                "    match value:\n"
                "        case 1:\n            pass\n"
                "        case _:\n            pass\n"
                "    return branch\n\n"
                "def exact_length():\n    pass\n    pass\n\n"
                "def function(first, second, third, fourth, fifth, sixth, seventh, eighth, ninth, tenth):\n    pass\n\n"
                "async def async_function(first, second, third, fourth, fifth, sixth, seventh, eighth, ninth, tenth):\n    pass\n\n"
                "class Service:\n"
                "    def __init__(self, first, second, third, fourth, fifth, sixth, seventh, eighth, ninth, tenth):\n        pass\n\n"
                "    def method(self, first, second, third, fourth, fifth, sixth, seventh, eighth, ninth, tenth):\n        pass\n\n"
                "    async def async_method(self, first, second, third, fourth, fifth, sixth, seventh, eighth, ninth, tenth):\n        pass\n\n"
                "    @classmethod\n"
                "    def class_method(cls, first, second, third, fourth, fifth, sixth, seventh, eighth, ninth, tenth):\n        pass\n\n"
                "    def receiver_only(self, first, second, third, fourth, fifth, sixth, seventh, eighth, ninth):\n        pass\n\n"
                "    @staticmethod\n"
                "    def static_method(first, second, third, fourth, fifth, sixth, seventh, eighth, ninth, tenth):\n        pass\n\n"
                "    def parameter_forms(self, first, /, second, *rest, named, **extra):\n        pass\n\n"
                "lambda_value = lambda first, second, third, fourth, fifth, sixth, seventh, eighth, ninth, tenth: first\n"
                "lambda_decision = lambda value: 1 if value else 0\n\n"
                "def annotated(value: dict[str, list[int | None]]) -> tuple[int | None, ...]:\n    return (value,)[0]\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="callable metrics">
    <rule ref="CyclomaticComplexity"><properties><property name="reportLevel" value="12" /></properties></rule>
    <rule ref="NPathComplexity"><properties><property name="minimum" value="1152" /></properties></rule>
    <rule ref="ExcessiveMethodLength"><properties><property name="minimum" value="3" /></properties></rule>
    <rule ref="ExcessiveParameterList"><properties><property name="minimum" value="10" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            parameter_ruleset.write_text(
                """<ruleset name="parameter forms">
    <rule ref="ExcessiveParameterList"><properties><property name="minimum" value="5" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            lambda_ruleset.write_text(
                """<ruleset name="lambda metrics">
    <rule ref="CyclomaticComplexity"><properties><property name="reportLevel" value="2" /></properties></rule>
    <rule ref="NPathComplexity"><properties><property name="minimum" value="3" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )

            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", str(ruleset)], stdout, stderr)
            parameter_stdout = StringIO()
            parameter_stderr = StringIO()
            parameter_status = run(
                [str(source), "text", str(parameter_ruleset)],
                parameter_stdout,
                parameter_stderr,
            )
            lambda_stdout = StringIO()
            lambda_stderr = StringIO()
            lambda_status = run(
                [str(source), "text", str(lambda_ruleset)],
                lambda_stdout,
                lambda_stderr,
            )
            parameter_report = parameter_stdout.getvalue()
            lambda_report = lambda_stdout.getvalue()

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn(
            "CyclomaticComplexity [priority 3] The function decision_flow() has a Cyclomatic Complexity of 12. "
            "The configured cyclomatic complexity threshold is 12.",
            report,
        )
        self.assertIn(
            "NPathComplexity [priority 3] The function decision_flow() has an NPath complexity of 1152. "
            "The configured NPath complexity threshold is 1152.",
            report,
        )
        self.assertIn(
            "The function exact_length() has 3 lines of code. Current threshold is set to 3. Avoid really long methods.",
            report,
        )
        for kind, name, parameter_count in [
            ("function", "function", 10),
            ("function", "async_function", 10),
            ("method", "__init__", 11),
            ("method", "method", 11),
            ("method", "async_method", 11),
            ("method", "class_method", 11),
            ("method", "static_method", 10),
            ("lambda", "<lambda>", 10),
        ]:
            self.assertIn(
                f"ExcessiveParameterList [priority 3] The {kind} {name} has {parameter_count} parameters. "
                "Consider reducing the number of parameters to less than 10.",
                report,
            )
        self.assertIn(
            "The method receiver_only has 10 parameters. Consider reducing the number of parameters to less than 10.",
            report,
        )
        self.assertNotIn("annotated has", report)
        self.assertEqual(2, parameter_status)
        self.assertEqual("", parameter_stderr.getvalue())
        self.assertIn(
            "The method parameter_forms has 6 parameters. Consider reducing the number of parameters to less than 5.",
            parameter_report,
        )
        self.assertEqual(2, lambda_status)
        self.assertEqual("", lambda_stderr.getvalue())
        self.assertIn("The lambda <lambda>() has a Cyclomatic Complexity of 2.", lambda_report)
        self.assertIn("The lambda <lambda>() has an NPath complexity of 3.", lambda_report)

    def test_phpmd_2_15_0_codesize_reference_keeps_callable_messages_and_priorities_stable(self) -> None:
        reference = json.loads((FIXTURES / "phpmd_2_15_0_codesize.json").read_text(encoding="utf-8"))
        self.assertEqual("2.15.0", reference["version"])
        self.assertTrue((FIXTURES / reference["php_fixture"]).is_file())
        python_fixture = FIXTURES / reference["python_fixture"]
        self.assertTrue(python_fixture.is_file())
        self.assertEqual(
            "vendor/bin/phpmd tests/fixtures/phpmd_2_15_0_callable_metrics.php text codesize",
            reference["phpmd_command"],
        )
        self.assertEqual(
            [
                "CyclomaticComplexity    The function decisionFlow() has a Cyclomatic Complexity of 10. "
                "The configured cyclomatic complexity threshold is 10.",
                "NPathComplexity         The function decisionFlow() has an NPath complexity of 512. "
                "The configured NPath complexity threshold is 200.",
                "ExcessiveParameterList  The function decisionFlow has 10 parameters. "
                "Consider reducing the number of parameters to less than 10.",
            ],
            reference["phpmd_text_output"],
        )

        reports: dict[str, str] = {}
        for rule_name, source in [
            ("CyclomaticComplexity", python_fixture),
            ("NPathComplexity", python_fixture),
            ("ExcessiveParameterList", python_fixture),
            ("ExcessiveMethodLength", FIXTURES / "long_function.py"),
        ]:
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", rule_name], stdout, stderr)
            self.assertEqual(2, status, rule_name)
            self.assertEqual("", stderr.getvalue(), rule_name)
            reports[rule_name] = stdout.getvalue()

        expected_messages = {
            "CyclomaticComplexity": "The function decision_flow() has a Cyclomatic Complexity of 10. "
            "The configured cyclomatic complexity threshold is 10.",
            "NPathComplexity": "The function decision_flow() has an NPath complexity of 512. "
            "The configured NPath complexity threshold is 200.",
            "ExcessiveParameterList": "The function decision_flow has 10 parameters. "
            "Consider reducing the number of parameters to less than 10.",
            "ExcessiveMethodLength": "The function too_long() has 101 lines of code. "
            "Current threshold is set to 100. Avoid really long methods.",
        }
        for rule in reference["rules"]:
            self.assertIn(f"{rule['name']} [priority {rule['priority']}]", reports[rule["name"]])
            self.assertIn(expected_messages[rule["name"]], reports[rule["name"]])
            self.assertEqual(1, reports[rule["name"]].count(f"{rule['name']} [priority"))
            for other_rule in reference["rules"]:
                if other_rule["name"] != rule["name"]:
                    self.assertNotIn(other_rule["name"], reports[rule["name"]])

    def test_callable_metrics_below_each_default_threshold_are_clean(self) -> None:
        sources = {
            "CyclomaticComplexity": "def choose(value):\n" + "    if value:\n        return value\n" * 8,
            "NPathComplexity": "def choose(value):\n" + "    if value:\n        value += 1\n" * 7,
            "ExcessiveMethodLength": _function_with_passes("choose", 98),
            "ExcessiveParameterList": "def choose(first, second, third, fourth, fifth, sixth, seventh, eighth, ninth):\n    pass\n",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            for rule_name, source_text in sources.items():
                source = temporary / f"{rule_name}.py"
                source.write_text(source_text, encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()

                status = run([str(source), "text", rule_name], stdout, stderr)

                self.assertEqual(0, status, rule_name)
                self.assertEqual("", stdout.getvalue(), rule_name)
                self.assertEqual("", stderr.getvalue(), rule_name)

    def test_callable_metrics_leave_idiomatic_python_quiet(self) -> None:
        source_text = (
            "def normalized_labels(raw_labels: list[str]) -> list[str]:\n"
            "    labels = [label.strip().lower() for label in raw_labels if label.strip()]\n"
            "    return sorted(set(labels))\n"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "labels.py"
            source.write_text(source_text, encoding="utf-8")
            for rule_name in [
                "CyclomaticComplexity",
                "NPathComplexity",
                "ExcessiveMethodLength",
                "ExcessiveParameterList",
            ]:
                stdout = StringIO()
                stderr = StringIO()

                status = run([str(source), "text", rule_name], stdout, stderr)

                self.assertEqual(0, status, rule_name)
                self.assertEqual("", stdout.getvalue(), rule_name)
                self.assertEqual("", stderr.getvalue(), rule_name)

    def test_npath_counts_conditional_expression_in_comprehension_element(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "comprehension.py"
            ruleset = temporary / "npath.xml"
            source.write_text(
                "def choose(values):\n    return [1 if value else 0 for value in values]\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="npath">
    <rule ref="NPathComplexity"><properties><property name="minimum" value="3" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "The function choose() has an NPath complexity of 3. The configured NPath complexity threshold is 3.",
            stdout.getvalue(),
        )

    def test_npath_counts_conditional_expression_in_match_subject(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "match_subject.py"
            ruleset = temporary / "npath.xml"
            source.write_text(
                "def choose(flag):\n"
                "    match (1 if flag else 2):\n"
                "        case 1:\n"
                "            return 1\n"
                "        case _:\n"
                "            return 2\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="npath">
    <rule ref="NPathComplexity"><properties><property name="minimum" value="3" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "The function choose() has an NPath complexity of 6. The configured NPath complexity threshold is 3.",
            stdout.getvalue(),
        )

    def test_npath_counts_with_statement_body_branches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "with_sample.py"
            ruleset = temporary / "npath.xml"
            source.write_text(
                "def process(x):\n"
                "    with open('test.txt') as f:\n"
                "        if x:\n"
                "            return 1\n"
                "        return 0\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="npath">
    <rule ref="NPathComplexity"><properties><property name="minimum" value="2" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "The function process() has an NPath complexity of 2. The configured NPath complexity threshold is 2.",
            stdout.getvalue(),
        )

    def test_npath_counts_async_with_statement_body_branches(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "async_with_sample.py"
            ruleset = temporary / "npath.xml"
            source.write_text(
                "async def process(lock, x):\n"
                "    async with lock:\n"
                "        if x:\n"
                "            return 1\n"
                "        return 0\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="npath">
    <rule ref="NPathComplexity"><properties><property name="minimum" value="2" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "The function process() has an NPath complexity of 2. The configured NPath complexity threshold is 2.",
            stdout.getvalue(),
        )

    def test_npath_counts_multiple_context_managers_and_expressions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "multi_context.py"
            ruleset = temporary / "npath.xml"
            source.write_text(
                "def process(a, b, flag):\n"
                "    with (x if flag else y) as first, z as second:\n"
                "        if a:\n"
                "            return 1\n"
                "        return 0\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="npath">
    <rule ref="NPathComplexity"><properties><property name="minimum" value="6" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "The function process() has an NPath complexity of 6. The configured NPath complexity threshold is 6.",
            stdout.getvalue(),
        )

    def test_npath_simple_with_statement_does_not_inflate_complexity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "simple_with.py"
            ruleset = temporary / "npath.xml"
            source.write_text(
                "def process():\n"
                "    with open('test.txt') as f:\n"
                "        return 1\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="npath">
    <rule ref="NPathComplexity"><properties><property name="minimum" value="2" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual("", stdout.getvalue())

    def test_npath_counts_nested_control_flow_in_with_statement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "nested_control_flow.py"
            ruleset = temporary / "npath.xml"
            source.write_text(
                "def process(items, value):\n"
                "    with open('test.txt') as f:\n"
                "        for item in items:\n"
                "            if item:\n"
                "                pass\n"
                "        match value:\n"
                "            case 1:\n"
                "                return 10\n"
                "            case 2:\n"
                "                return 20\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="npath">
    <rule ref="NPathComplexity"><properties><property name="minimum" value="6" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "The function process() has an NPath complexity of 6. The configured NPath complexity threshold is 6.",
            stdout.getvalue(),
        )



    def test_class_metrics_scan_real_python_classes_with_configured_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "service.py"
            ruleset = temporary / "class-metrics.xml"
            source.write_text(
                "class Service:\n"
                "    public_field: int = 1\n"
                "    another_field = 2\n"
                "    _private_field = 3\n"
                "\n"
                "    def get_value(self):\n"
                "        return self.public_field\n"
                "\n"
                "    def work_one(self, value):\n"
                "        if value:\n"
                "            return value\n"
                "        return 0\n"
                "\n"
                "    async def work_two(self, value):\n"
                "        if value:\n"
                "            return value\n"
                "        return 0\n"
                "\n"
                "    class Nested:\n"
                "        nested_field = 1\n"
                "        def nested_work(self):\n"
                "            return self.nested_field\n"
                "\n"
                "class ServiceProtocol(Protocol):\n"
                "    protocol_field: int\n"
                "    def contract(self) -> int: ...\n"
                "\n"
                "class AbstractService(ABC):\n"
                "    @abstractmethod\n"
                "    def contract(self) -> int:\n"
                "        raise NotImplementedError\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="class metrics">
    <rule ref="ExcessiveClassLength"><properties><property name="minimum" value="22" /></properties></rule>
    <rule ref="ExcessivePublicCount"><properties><property name="minimum" value="5" /></properties></rule>
    <rule ref="TooManyFields"><properties><property name="maxfields" value="2" /></properties></rule>
    <rule ref="TooManyMethods"><properties><property name="maxmethods" value="1" /></properties></rule>
    <rule ref="TooManyPublicMethods"><properties><property name="maxmethods" value="1" /></properties></rule>
    <rule ref="ExcessiveClassComplexity"><properties><property name="maximum" value="5" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn(
            "ExcessiveClassLength [priority 3] The class Service has 22 lines of code. "
            "Current threshold is set to 22. Avoid really long classes.",
            report,
        )
        self.assertIn(
            "ExcessivePublicCount [priority 3] The class Service has 5 public methods and attributes. "
            "Consider reducing the number of public items to less than 5.",
            report,
        )
        self.assertIn(
            "TooManyFields [priority 3] The class Service has 3 fields. "
            "Consider redesigning Service to keep the number of fields under 2.",
            report,
        )
        self.assertIn(
            "TooManyMethods [priority 3] The class Service has 2 non-getter- and setter-methods. "
            "Consider refactoring Service to keep number of methods under 1.",
            report,
        )
        self.assertIn(
            "TooManyPublicMethods [priority 3] The class Service has 2 public methods. "
            "Consider refactoring Service to keep number of public methods under 1.",
            report,
        )
        self.assertIn(
            "ExcessiveClassComplexity [priority 3] The class Service has an overall complexity of 5 "
            "which is very high. The configured complexity threshold is 5.",
            report,
        )
        self.assertNotIn("Nested has", report)
        self.assertNotIn("ServiceProtocol has", report)
        self.assertNotIn("AbstractService has an overall complexity", report)

    def test_class_metrics_include_members_declared_in_class_control_flow_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "conditional.py"
            ruleset = temporary / "class-metrics.xml"
            source.write_text(
                "class Conditional:\n"
                "    if feature_enabled:\n"
                "        conditional_field = 1\n"
                "\n"
                "        def conditional_method(self):\n"
                "            def helper():\n"
                "                return 0\n"
                "            helper()\n"
                "            if self.value:\n"
                "                return 1\n"
                "            return 0\n"
                "\n"
                "    try:\n"
                "        fallback_field = 2\n"
                "    except OSError:\n"
                "        pass\n"
                "\n"
                "    for _ in range(3):\n"
                "        pass\n"
                "    else:\n"
                "        loop_field = 3\n"
                "\n"
                "    while waiting:\n"
                "        class Inner:\n"
                "            inner_field = 5\n"
                "\n"
                "    match shape:\n"
                "        case 1:\n"
                "            match_field = 4\n"
                "            def match_method(self):\n"
                "                return self.match_field\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="class metrics">
    <rule ref="TooManyFields"><properties><property name="maxfields" value="0" /></properties></rule>
    <rule ref="TooManyMethods"><properties><property name="maxmethods" value="0" /></properties></rule>
    <rule ref="TooManyPublicMethods"><properties><property name="maxmethods" value="0" /></properties></rule>
    <rule ref="ExcessivePublicCount"><properties><property name="minimum" value="1" /></properties></rule>
    <rule ref="ExcessiveClassComplexity"><properties><property name="maximum" value="1" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn(
            "TooManyFields [priority 3] The class Conditional has 4 fields. "
            "Consider redesigning Conditional to keep the number of fields under 0.",
            report,
        )
        self.assertIn(
            "TooManyMethods [priority 3] The class Conditional has 2 non-getter- and setter-methods. "
            "Consider refactoring Conditional to keep number of methods under 0.",
            report,
        )
        self.assertIn(
            "TooManyPublicMethods [priority 3] The class Conditional has 2 public methods. "
            "Consider refactoring Conditional to keep number of public methods under 0.",
            report,
        )
        self.assertIn(
            "ExcessivePublicCount [priority 3] The class Conditional has 6 public methods and attributes. "
            "Consider reducing the number of public items to less than 1.",
            report,
        )
        self.assertIn(
            "ExcessiveClassComplexity [priority 3] The class Conditional has an overall complexity of 3 "
            "which is very high. The configured complexity threshold is 1.",
            report,
        )
        self.assertNotIn("helper", report)
        self.assertNotIn("inner_field = 5", report)
        self.assertNotIn("Conditional has 5 fields", report)
        self.assertNotIn("Conditional has 3 non-getter", report)

    def test_too_many_fields_counts_class_body_augmented_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "counter.py"
            ruleset = temporary / "class-metrics.xml"
            source.write_text(
                "counter = 1\n"
                "\n"
                "class Counter:\n"
                "    field = 1\n"
                "    counter += 1\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="class metrics">
    <rule ref="TooManyFields"><properties><property name="maxfields" value="1" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "TooManyFields [priority 3] The class Counter has 2 fields. "
            "Consider redesigning Counter to keep the number of fields under 1.",
            stdout.getvalue(),
        )

    def test_too_many_fields_counts_instance_fields_assigned_with_unpacking(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "unpacking.py"
            ruleset = temporary / "class-metrics.xml"
            source.write_text(
                "class Point:\n"
                "    def __init__(self, point, items, tree):\n"
                "        self.x, self.y = point\n"
                "        [self.head, *self.tail] = items\n"
                "        (self.left, (self.mid, [self.right])) = tree\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="class metrics">
    <rule ref="TooManyFields"><properties><property name="maxfields" value="6" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "TooManyFields [priority 3] The class Point has 7 fields. "
            "Consider redesigning Point to keep the number of fields under 6.",
            stdout.getvalue(),
        )

    def test_too_many_fields_counts_instance_fields_assigned_in_nested_functions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "nested_fields.py"
            ruleset = temporary / "class-metrics.xml"
            source.write_text(
                "class Widget:\n"
                "    def __init__(self):\n"
                "        def inner():\n"
                "            self.first = 1\n"
                "            self.second = 2\n"
                "        inner()\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="class metrics">
    <rule ref="TooManyFields"><properties><property name="maxfields" value="1" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "TooManyFields [priority 3] The class Widget has 2 fields. "
            "Consider redesigning Widget to keep the number of fields under 1.",
            stdout.getvalue(),
        )

    def test_too_many_fields_ignores_nested_functions_that_shadow_the_receiver(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "shadowed_receiver.py"
            ruleset = temporary / "class-metrics.xml"
            source.write_text(
                "class Widget:\n"
                "    def __init__(self):\n"
                "        def inner(self):\n"
                "            self.first = 1\n"
                "        inner(Widget())\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="class metrics">
    <rule ref="TooManyFields"><properties><property name="maxfields" value="0" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_codesize_includes_all_ten_callable_and_class_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "clean.py"
            source.write_text("class Service:\n    pass\n", encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "codesize", "--verbose"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual(
            "Loaded rules: CyclomaticComplexity, NPathComplexity, ExcessiveMethodLength, "
            "ExcessiveClassLength, ExcessiveParameterList, ExcessivePublicCount, TooManyFields, "
            "TooManyMethods, TooManyPublicMethods, ExcessiveClassComplexity\n",
            stderr.getvalue(),
        )

    def test_field_metrics_include_conventional_instance_attributes_without_static_noise(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "model.py"
            ruleset = temporary / "fields.xml"
            source.write_text(
                "class Model:\n"
                "    declared: str\n"
                "\n"
                "    def __init__(self):\n"
                "        self.active = True\n"
                "        self._cache = {}\n"
                "\n"
                "    @staticmethod\n"
                "    def configure(value):\n"
                "        value.not_a_model_field = True\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="fields">
    <rule ref="TooManyFields"><properties><property name="maxfields" value="2" /></properties></rule>
    <rule ref="ExcessivePublicCount"><properties><property name="minimum" value="2" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn("The class Model has 3 fields.", stdout.getvalue())
        self.assertIn("The class Model has 3 public methods and attributes.", stdout.getvalue())

    def test_codesize_reports_every_callable_and_class_rule_in_one_real_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "all_codesize_rules.py"
            fields = "".join(f"    field_{index} = {index}\n" for index in range(45))
            complex_methods = "".join(
                f"    def work_{index}(self, first, second, third, fourth, fifth, sixth, seventh, eighth, ninth):\n"
                + "".join(f"        if value_{branch}:\n            pass\n" for branch in range(9))
                + ("        pass\n" * 90 if index == 0 else "")
                for index in range(11)
            )
            private_methods = "".join(
                f"    def _work_{index}(self):\n        return None\n" for index in range(15)
            )
            source.write_text(
                "class Everything:\n"
                + fields
                + complex_methods
                + private_methods
                + "".join(f"    _filler_{index} = None\n" for index in range(650)),
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "codesize"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        for rule_name in [
            "CyclomaticComplexity",
            "NPathComplexity",
            "ExcessiveMethodLength",
            "ExcessiveParameterList",
            "ExcessiveClassLength",
            "ExcessivePublicCount",
            "TooManyFields",
            "TooManyMethods",
            "TooManyPublicMethods",
            "ExcessiveClassComplexity",
        ]:
            self.assertIn(rule_name, stdout.getvalue())

    def test_class_rule_default_boundaries_and_conventional_interfaces_are_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "boundary.py"
            fields = "".join(f"    field_{index} = {index}\n" for index in range(15))
            methods = "".join(
                f"    def work_{index}(self):\n        return {index}\n" for index in range(10)
            ) + "".join(f"    def _work_{index}(self):\n        return {index}\n" for index in range(15))
            source.write_text(
                "class Boundary:\n"
                + fields
                + methods
                + "\nclass Interface(Protocol):\n"
                + "    value: int\n"
                + "    @overload\n"
                + "    def parse(self, value: int) -> int: ...\n"
                + "\nclass AbstractInterface(ABC):\n"
                + "    @abstractmethod\n"
                + "    def parse(self, value: int) -> int:\n"
                + "        raise NotImplementedError\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "codesize"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_dataclass_fields_are_real_without_inventing_generated_methods(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "generated.py"
            ruleset = temporary / "generated.xml"
            source.write_text(
                "from dataclasses import dataclass\n"
                "\n"
                "@dataclass\n"
                "class Generated:\n"
                "    first: int\n"
                "    second: int\n"
                "    third: int\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="generated">
    <rule ref="TooManyFields"><properties><property name="maxfields" value="2" /></properties></rule>
    <rule ref="TooManyMethods"><properties><property name="maxmethods" value="0" /></properties></rule>
    <rule ref="TooManyPublicMethods"><properties><property name="maxmethods" value="0" /></properties></rule>
    <rule ref="ExcessivePublicCount"><properties><property name="minimum" value="4" /></properties></rule>
    <rule ref="ExcessiveClassComplexity"><properties><property name="maximum" value="1" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn("TooManyFields [priority 3] The class Generated has 3 fields.", stdout.getvalue())
        for rule_name in [
            "TooManyMethods",
            "TooManyPublicMethods",
            "ExcessivePublicCount",
            "ExcessiveClassComplexity",
        ]:
            self.assertNotIn(rule_name, stdout.getvalue())

    def test_naming_rules_find_unambiguous_python_roles_in_one_cli_scan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "names.py"
            source.write_text(
                "from typing import Final, TypeVar\n"
                "\n"
                "T = TypeVar(\"T\")\n"
                "\n"
                "def go():\n"
                "    return None\n"
                "\n"
                "class Ab:\n"
                "    pass\n"
                "\n"
                "class ThisClassNameIsLongerThanTheDefaultMaximum:\n"
                "    pass\n"
                "\n"
                "class Holder:\n"
                "    ab = 1\n"
                "\n"
                "    def ok(self, ab):\n"
                "        very_long_variable_name = ab\n"
                "        return very_long_variable_name\n"
                "\n"
                "    def get_ready(self) -> bool:\n"
                "        return True\n"
                "\n"
                "wrong_constant: Final = 1\n"
                "UPPER_CASE: Final = 2\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "naming"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        for rule_name in [
            "ShortClassName",
            "LongClassName",
            "ShortVariable",
            "LongVariable",
            "ShortMethodName",
            "ConstantNamingConventions",
            "BooleanGetMethodName",
        ]:
            self.assertIn(rule_name, report)
        self.assertNotIn("ConstructorWithNameAsEnclosingClass", report)

    def test_naming_rules_scope_exemptions_and_boolean_proof_to_python_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "role_scoped_names.py"
            source.write_text(
                "class e:\n"
                "    pass\n"
                "\n"
                "class Holder:\n"
                "    ab = 1\n"
                "    x = 1\n"
                "    y = 2\n"
                "\n"
                "    def i(self):\n"
                "        return None\n"
                "\n"
                "    def get_remote(self):\n"
                "        return service.bool()\n"
                "\n"
                "    def get_annotated(self) -> service.bool:\n"
                "        return object()\n"
                "\n"
                "    def get_partial(self):\n"
                "        if condition:\n"
                "            return True\n"
                "\n"
                "    @property\n"
                "    def p(self):\n"
                "        return 1\n"
                "\n"
                "    @p.setter\n"
                "    def p(self, value):\n"
                "        pass\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "naming"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("ShortClassName [priority 3] Avoid using short class names like e.", report)
        self.assertIn("ShortVariable [priority 3] Avoid variables with short names like ab.", report)
        self.assertNotIn("ShortVariable [priority 3] Avoid variables with short names like x.", report)
        self.assertNotIn("ShortVariable [priority 3] Avoid variables with short names like y.", report)
        self.assertIn("ShortMethodName [priority 3] Avoid using short method names like i().", report)
        self.assertNotIn("ShortMethodName [priority 3] Avoid using short method names like p().", report)
        self.assertNotIn("BooleanGetMethodName", report)

    def test_naming_rules_honor_configured_lengths_at_the_cli_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "configured_names.py"
            ruleset = temporary / "configured-naming.xml"
            source.write_text(
                "class Four:\n"
                "    four = 1\n"
                "\n"
                "    def four(self, four):\n"
                "        longer = four\n"
                "        return longer\n"
                "\n"
                "class ExactlyFive:\n"
                "    pass\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="configured naming">
    <rule ref="ShortClassName"><properties><property name="minimum" value="5" /></properties></rule>
    <rule ref="LongClassName"><properties><property name="maximum" value="10" /></properties></rule>
    <rule ref="ShortVariable"><properties><property name="minimum" value="5" /></properties></rule>
    <rule ref="LongVariable"><properties><property name="maximum" value="5" /></properties></rule>
    <rule ref="ShortMethodName"><properties><property name="minimum" value="5" /></properties></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("ShortClassName [priority 3] Avoid using short class names like Four. Configured minimum length is 5.", report)
        self.assertIn("LongClassName [priority 3] Avoid excessively long class names like ExactlyFive. Configured maximum length is 10.", report)
        self.assertIn("ShortVariable [priority 3] Avoid variables with short names like four. Configured minimum length is 5.", report)
        self.assertIn("LongVariable [priority 3] Avoid excessively long variable names like longer. Configured maximum length is 5.", report)
        self.assertIn("ShortMethodName [priority 3] Avoid using short method names like four(). Configured minimum length is 5.", report)

    def test_naming_rules_keep_repeated_store_targets_on_distinct_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "duplicate_targets.py"
            source.write_text(
                "class Holder:\n"
                "    def assign(self):\n"
                "        ab = 1\n"
                "        ab = 2\n"
                "        self.cd = ab\n"
                "        self.cd = 3\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "naming", "--only", "ShortVariable"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertEqual(2, report.count("Avoid variables with short names like ab."))
        self.assertEqual(2, report.count("Avoid variables with short names like cd."))

    def test_naming_rules_keep_python_idioms_and_default_boundaries_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "idiomatic_names.py"
            source_text = (
                "from typing import Final, TypeVar\n"
                "\n"
                "T = TypeVar(\"T\")\n"
                "\n"
                "class Cat:\n"
                "    age = 1\n"
                "\n"
                "    def run(self, value, /, *, option):\n"
                "        abc = value\n"
                "        very_long_variable_n = option\n"
                "        for i, x, y in enumerate((abc, very_long_variable_n)):\n"
                "            abc += i + x + y\n"
                "        try:\n"
                "            raise ValueError\n"
                "        except ValueError as exc:\n"
                "            return abc\n"
                "\n"
                "    def get_value(self):\n"
                "        return object()\n"
                "\n"
                "    def is_ready(self) -> bool:\n"
                "        return True\n"
                "\n"
                "    def _go(self):\n"
                "        __internal__ = 1\n"
                "        return __internal__\n"
                "\n"
                "MAXIMUM_VALUE: Final = 1\n"
                "__all__: Final = (\"Cat\",)\n"
                "THIS_IS_AN_UPPER_CASE_CONSTANT_LONGER_THAN_TWENTY = 1\n"
                + f"class {'C' * 40}:\n    pass\n"
            )
            source.write_text(
                source_text,
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "naming"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_reports_an_unused_function_local_through_the_command_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "unused_local.py"
            source.write_text(
                "def build():\n"
                "    discarded = 1\n"
                "    return 0\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "UnusedLocalVariable [priority 3] Avoid unused local variables such as 'discarded'.",
            stdout.getvalue(),
        )

    def test_unusedcode_reports_an_unused_parameter_through_the_command_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "unused_parameter.py"
            source.write_text(
                "def transform(value, unused):\n"
                "    return value\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "UnusedFormalParameter [priority 3] Avoid unused parameters such as 'unused'.",
            stdout.getvalue(),
        )

    def test_unusedcode_reports_an_unused_private_field_through_the_command_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "unused_field.py"
            source.write_text(
                "class Cache:\n"
                "    def __init__(self):\n"
                "        self._stale = 1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "UnusedPrivateField [priority 3] Avoid unused private fields such as '_stale'.",
            stdout.getvalue(),
        )

    def test_unusedcode_treats_a_direct_augmented_private_field_update_as_a_use(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "augmented_field.py"
            source.write_text(
                "class Counter:\n"
                "    def __init__(self):\n"
                "        self._count = 0\n"
                "        self._count += 1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedPrivateField"],
                stdout,
                stderr,
            )

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_reports_unused_private_class_fields_in_control_flow_and_augmented_assignments(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "control_flow_fields.py"
            source.write_text(
                "class Counter:\n"
                "    if True:\n"
                "        _in_if = 1\n"
                "    try:\n"
                "        _in_try = 2\n"
                "    except Exception:\n"
                "        pass\n"
                "    _augmented += 3\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedPrivateField"],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "UnusedPrivateField [priority 3] Avoid unused private fields such as '_in_if'.",
            stdout.getvalue(),
        )
        self.assertIn(
            "UnusedPrivateField [priority 3] Avoid unused private fields such as '_in_try'.",
            stdout.getvalue(),
        )
        self.assertIn(
            "UnusedPrivateField [priority 3] Avoid unused private fields such as '_augmented'.",
            stdout.getvalue(),
        )

    def test_unusedcode_reports_unused_private_instance_fields_from_methods_in_control_flow(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "control_flow_method.py"
            source.write_text(
                "class Counter:\n"
                "    if True:\n"
                "        def __init__(self):\n"
                "            self._unused = 1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedPrivateField"],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "UnusedPrivateField [priority 3] Avoid unused private fields such as '_unused'.",
            stdout.getvalue(),
        )

    def test_unusedcode_reports_unused_private_fields_assigned_in_nested_functions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "nested_private_field.py"
            source.write_text(
                "class Cache:\n"
                "    def __init__(self):\n"
                "        def inner():\n"
                "            self._stale = 1\n"
                "        inner()\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedPrivateField"],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "UnusedPrivateField [priority 3] Avoid unused private fields such as '_stale'.",
            stdout.getvalue(),
        )

    def test_unusedcode_ignores_nested_functions_that_shadow_the_receiver_for_private_fields(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "nested_shadowed_private_field.py"
            source.write_text(
                "class Cache:\n"
                "    def __init__(self):\n"
                "        def inner(self):\n"
                "            self._stale = 1\n"
                "        inner(Cache())\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedPrivateField"],
                stdout,
                stderr,
            )

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_reports_an_unused_private_method_through_the_command_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "unused_method.py"
            source.write_text(
                "class Service:\n"
                "    def _discarded(self):\n"
                "        return None\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "UnusedPrivateMethod [priority 3] Avoid unused private methods such as '_discarded'.",
            stdout.getvalue(),
        )

    def test_unusedcode_keeps_private_methods_overriding_imported_bases_quiet(self) -> None:
        source = (FIXTURES / "issue_138").resolve()
        stdout = StringIO()
        stderr = StringIO()

        status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_still_reports_unused_private_methods_in_local_subclasses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "local_base.py"
            source.write_text(
                "class Base:\n"
                "    def run(self):\n"
                "        return self._hook()\n"
                "\n"
                "    def _hook(self):\n"
                "        return 0\n"
                "\n"
                "class Child(Base):\n"
                "    def _hook(self):\n"
                "        return 1\n"
                "\n"
                "    def _discarded(self):\n"
                "        return 2\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertNotIn("_hook", report)
        self.assertIn(
            "UnusedPrivateMethod [priority 3] Avoid unused private methods such as '_discarded'.",
            report,
        )

    def test_unusedcode_keeps_closure_and_comprehension_bindings_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "scopes.py"
            source.write_text(
                "def transform(values):\n"
                "    captured = 1\n"
                "    def read_capture():\n"
                "        return captured\n"
                "    return [item + read_capture() for item in values]\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_reports_unused_exception_and_pattern_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "bindings.py"
            source.write_text(
                "def parse(value):\n"
                "    try:\n"
                "        raise ValueError\n"
                "    except ValueError as error:\n"
                "        match value:\n"
                "            case {\"id\": item}:\n"
                "                return value\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("UnusedLocalVariable [priority 3] Avoid unused local variables such as 'error'.", report)
        self.assertIn("UnusedLocalVariable [priority 3] Avoid unused local variables such as 'item'.", report)

    def test_unusedcode_honors_a_configured_rule_priority_at_the_command_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "configured_unused.py"
            ruleset = temporary / "unused.xml"
            source.write_text("def build():\n    discarded = 1\n", encoding="utf-8")
            ruleset.write_text(
                """<ruleset name="unused">
    <rule ref="UnusedLocalVariable"><priority>2</priority></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn("UnusedLocalVariable [priority 2]", stdout.getvalue())

    def test_unusedcode_keeps_generated_and_dynamic_private_members_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "conservative_members.py"
            source.write_text(
                "from dataclasses import dataclass\n"
                "\n"
                "@dataclass\n"
                "class Record:\n"
                "    _stored: int\n"
                "\n"
                "class Dynamic:\n"
                "    def __init__(self):\n"
                "        self._cached = 1\n"
                "\n"
                "    def read(self, name):\n"
                "        return getattr(self, name)\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_keeps_global_and_nonlocal_bindings_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "global_nonlocal.py"
            source.write_text(
                "shared = 0\n"
                "\n"
                "def write_global():\n"
                "    global shared\n"
                "    shared = 1\n"
                "\n"
                "def outer():\n"
                "    captured = 0\n"
                "    def write_capture():\n"
                "        nonlocal captured\n"
                "        captured = 1\n"
                "    return write_capture\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_keeps_contracts_and_decorated_members_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "contracts.py"
            source.write_text(
                "from abc import ABC, abstractmethod\n"
                "from typing import Protocol, overload\n"
                "\n"
                "def decorator(function):\n"
                "    return function\n"
                "\n"
                "class Contract(Protocol):\n"
                "    @overload\n"
                "    def _convert(self, value): ...\n"
                "\n"
                "class Abstract(ABC):\n"
                "    @abstractmethod\n"
                "    def _hook(self, value):\n"
                "        raise NotImplementedError\n"
                "\n"
                "class Model:\n"
                "    @property\n"
                "    def _value(self):\n"
                "        return 1\n"
                "\n"
                "    @decorator\n"
                "    def _decorated(self, value):\n"
                "        pass\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_keeps_used_private_members_and_underscore_parameters_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "used_members.py"
            source.write_text(
                "class Cache:\n"
                "    def __init__(self):\n"
                "        self._value = 1\n"
                "\n"
                "    def read(self, _context):\n"
                "        return self._read_value()\n"
                "\n"
                "    def _read_value(self):\n"
                "        return self._value\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_keeps_externally_and_qualified_dynamically_used_members_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "external_members.py"
            source.write_text(
                "import builtins\n"
                "from dataclasses import dataclass\n"
                "\n"
                "@dataclass(frozen=True)\n"
                "class Record:\n"
                "    _stored: int\n"
                "\n"
                "class Cache:\n"
                "    def __init__(self):\n"
                "        self._value = 1\n"
                "\n"
                "    def _refresh(self):\n"
                "        return self._value\n"
                "\n"
                "cache = Cache()\n"
                "cache._value\n"
                "cache._refresh()\n"
                "builtins.getattr(cache, name)\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_honors_configured_priorities_for_every_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            source = temporary / "configured_all_unused.py"
            ruleset = temporary / "unused.xml"
            source.write_text(
                "def build(unused):\n"
                "    discarded = 1\n"
                "\n"
                "class Cache:\n"
                "    _stale = 1\n"
                "\n"
                "    def _discarded(self):\n"
                "        return None\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="unused">
    <rule ref="UnusedLocalVariable"><priority>1</priority></rule>
    <rule ref="UnusedFormalParameter"><priority>2</priority></rule>
    <rule ref="UnusedPrivateField"><priority>4</priority></rule>
    <rule ref="UnusedPrivateMethod"><priority>5</priority></rule>
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("UnusedLocalVariable [priority 1]", report)
        self.assertIn("UnusedFormalParameter [priority 2]", report)
        self.assertIn("UnusedPrivateField [priority 4]", report)
        self.assertIn("UnusedPrivateMethod [priority 5]", report)

    def test_unusedcode_reports_an_unused_comprehension_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "unused_comprehension.py"
            source.write_text(
                "def build(values):\n"
                "    return [0 for item in values]\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn(
            "UnusedLocalVariable [priority 3] Avoid unused local variables such as 'item'.",
            stdout.getvalue(),
        )

    def test_unusedcode_keeps_local_type_alias_used_by_postponed_annotation_quiet(self) -> None:
        stdout = StringIO()
        stderr = StringIO()
        source = (FIXTURES / "issue_127_local_annotation.py").resolve()

        status = run(
            [str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"],
            stdout,
            stderr,
        )

        self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_unusedcode_keeps_outer_type_alias_used_by_nested_annotations_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "nested_annotation.py"
            source.write_text(
                "from __future__ import annotations\n"
                "\n"
                "def outer():\n"
                "    MyType = int\n"
                "\n"
                "    def inner(value: MyType) -> MyType:\n"
                "        return value\n"
                "\n"
                "    return inner\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"],
                stdout,
                stderr,
            )

        self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_unusedcode_distinguishes_prebinding_and_shadowed_comprehension_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "comprehension_scopes.py"
            source.write_text(
                "def prebinding(item):\n"
                "    return [0 for item in item]\n"
                "\ndef nested(values):\n"
                "    return [0 for item in values if any(item for item in values)]\n"
                "\ndef used(values):\n"
                "    return [item for item in values]\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(2, stdout.getvalue().count("such as 'item'"))

    def test_nested_comprehension_does_not_hide_unused_outer_local(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "nested_comprehension.py"
            source.write_text(
                "def outer():\n"
                "    unused = 1\n"
                "    def inner():\n"
                "        unused = 2\n"
                "        return [unused for _ in range(1)]\n"
                "    return inner()\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(1, stdout.getvalue().count("such as 'unused'"))

    def test_nested_lambda_in_comprehension_does_not_hide_unused_outer_local(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "comprehension_lambda.py"
            source.write_text(
                "def outer():\n"
                "    unused = 1\n"
                "    return [(lambda unused: unused)(2) for _ in range(1)]\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(1, stdout.getvalue().count("such as 'unused'"))

    def test_nested_comprehension_does_not_hide_shadowed_outer_local(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "nested_shadowing_comprehension.py"
            source.write_text(
                "def outer():\n"
                "    unused = 1\n"
                "    return [[unused for unused in range(1)] for _ in range(1)]\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(1, stdout.getvalue().count("such as 'unused'"))

    def test_augmented_assignment_counts_as_local_variable_use(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "augmented_local.py"
            source.write_text(
                "def transform():\n"
                "    value = 1\n"
                "    value += 1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"],
                stdout,
                stderr,
            )

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_augmented_assignment_counts_as_parameter_use(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "augmented_parameter.py"
            source.write_text(
                "def transform(value):\n"
                "    value += 1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedFormalParameter"],
                stdout,
                stderr,
            )

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_augmented_assignment_in_nested_function_does_not_use_outer_local(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "augmented_nested.py"
            source.write_text(
                "def outer():\n"
                "    unused = 1\n"
                "\n"
                "    def inner():\n"
                "        unused = 2\n"
                "        unused += 1\n"
                "\n"
                "    return inner\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(1, stdout.getvalue().count("such as 'unused'"))

    def test_visitor_like_function_does_not_hide_unused_parameter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "visitor_like_function.py"
            source.write_text(
                "import ast\n"
                "\n"
                "def visit_Name(node):\n"
                "    return 1\n"
                "\n"
                "class Visitor(ast.NodeVisitor):\n"
                "    def visit_Name(self, node):\n"
                "        return 1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedFormalParameter"],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(1, stdout.getvalue().count("such as 'node'"))

    def test_ast_visitor_aliases_preserve_callback_parameter_exemption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "visitor_aliases.py"
            source.write_text(
                "from ast import NodeVisitor\n"
                "import ast as syntax\n"
                "\n"
                "class ImportedVisitor(NodeVisitor):\n"
                "    def visit_Name(self, node):\n"
                "        return 1\n"
                "\n"
                "class AliasedVisitor(syntax.NodeVisitor):\n"
                "    def visit_Name(self, node):\n"
                "        return 1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedFormalParameter"],
                stdout,
                stderr,
            )

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_exempts_visitor_and_protocol_methods_in_class_control_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "control_flow_contracts.py"
            source.write_text(
                "import ast\n"
                "from typing import Protocol\n"
                "\n"
                "class IfVisitor(ast.NodeVisitor):\n"
                "    if True:\n"
                "        def visit_Name(self, node):\n"
                "            return None\n"
                "\n"
                "class TryVisitor(ast.NodeVisitor):\n"
                "    try:\n"
                "        def visit_Constant(self, node):\n"
                "            return None\n"
                "    except Exception:\n"
                "        pass\n"
                "\n"
                "class ForVisitor(ast.NodeVisitor):\n"
                "    for _ in ():\n"
                "        def visit_Attribute(self, node):\n"
                "            return None\n"
                "\n"
                "class MatchVisitor(ast.NodeVisitor):\n"
                "    match 0:\n"
                "        case _:\n"
                "            def visit_BinOp(self, node):\n"
                "                return None\n"
                "\n"
                "class IfProtocol(Protocol):\n"
                "    if True:\n"
                "        def read_if(self, unused_param: int) -> str:\n"
                "            return \"ok\"\n"
                "\n"
                "class TryProtocol(Protocol):\n"
                "    try:\n"
                "        def read_try(self, unused_param: int) -> str:\n"
                "            return \"ok\"\n"
                "    except Exception:\n"
                "        pass\n"
                "\n"
                "class ForProtocol(Protocol):\n"
                "    for _ in ():\n"
                "        def read_for(self, unused_param: int) -> str:\n"
                "            return \"ok\"\n"
                "\n"
                "class MatchProtocol(Protocol):\n"
                "    match 0:\n"
                "        case _:\n"
                "            def read_match(self, unused_param: int) -> str:\n"
                "                return \"ok\"\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedFormalParameter"],
                stdout,
                stderr,
            )

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_node_transformer_preserves_callback_parameter_exemption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "transformer.py"
            source.write_text(
                "import ast\n"
                "\n"
                "class Transformer(ast.NodeTransformer):\n"
                "    def visit_Name(self, node):\n"
                "        return None\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedFormalParameter"],
                stdout,
                stderr,
            )

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_duplicate_class_names_do_not_change_visitor_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "duplicate_visitors.py"
            source.write_text(
                "import ast\n"
                "\n"
                "class A:\n"
                "    class Visitor(ast.NodeVisitor):\n"
                "        def visit_Name(self, node):\n"
                "            return 1\n"
                "\n"
                "class B:\n"
                "    class Visitor:\n"
                "        def visit_Name(self, node):\n"
                "            return 1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedFormalParameter"],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(1, stdout.getvalue().count("such as 'node'"))

    def test_qualified_local_visitor_inheritance_preserves_callback_exemption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "qualified_visitor.py"
            source.write_text(
                "import ast\n"
                "\n"
                "class Namespace:\n"
                "    class Base(ast.NodeVisitor):\n"
                "        pass\n"
                "\n"
                "class Child(Namespace.Base):\n"
                "    def visit_Name(self, node):\n"
                "        return 1\n"
                "\n"
                "class Base(ast.NodeVisitor):\n"
                "    pass\n"
                "\n"
                "class Other:\n"
                "    class Base:\n"
                "        pass\n"
                "\n"
                "class TopChild(Base):\n"
                "    def visit_Name(self, node):\n"
                "        return 1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedFormalParameter"],
                stdout,
                stderr,
            )

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_subscripted_ast_visitor_bases_preserve_contract_exemptions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "generic_visitors.py"
            source.write_text(
                "import ast\n"
                "from ast import NodeVisitor, NodeTransformer\n"
                "from typing import Generic, TypeVar, Sequence\n"
                "\n"
                "T = TypeVar('T')\n"
                "\n"
                "class DirectModuleVisitor(ast.NodeVisitor[T]):\n"
                "    def visit_AsyncFunctionDef(self, node):\n"
                "        return 1\n"
                "\n"
                "class DirectImportedVisitor(NodeVisitor[int]):\n"
                "    def visit_AsyncFunctionDef(self, node):\n"
                "        return 1\n"
                "\n"
                "class DirectTransformer(NodeTransformer[str]):\n"
                "    def visit_AsyncFunctionDef(self, node):\n"
                "        return None\n"
                "\n"
                "class BaseVisitor(ast.NodeVisitor[int]):\n"
                "    pass\n"
                "\n"
                "class SubVisitor(BaseVisitor[str]):\n"
                "    def visit_AsyncFunctionDef(self, node):\n"
                "        return 1\n"
                "\n"
                "class Namespace:\n"
                "    class InnerBase(NodeVisitor[T]):\n"
                "        pass\n"
                "\n"
                "class QualifiedSubVisitor(Namespace.InnerBase[int]):\n"
                "    def visit_AsyncFunctionDef(self, node):\n"
                "        return 1\n"
                "\n"
                "class NonVisitorGeneric(Sequence[int]):\n"
                "    def visit_AsyncFunctionDef(self, node):\n"
                "        return 1\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "controversial", "--only", "CamelCaseMethodName"],
                stdout,
                stderr,
            )

            self.assertEqual(2, status)
            self.assertEqual("", stderr.getvalue())
            output = stdout.getvalue()
            self.assertIn("The method visit_AsyncFunctionDef is not named in snake_case.", output)
            self.assertEqual(1, output.count("CamelCaseMethodName"))
            self.assertIn(":35: CamelCaseMethodName", output)  # line 35 is NonVisitorGeneric.visit_AsyncFunctionDef

            # Also verify UnusedFormalParameter exempts valid visitors but flags NonVisitorGeneric
            stdout_unused = StringIO()
            stderr_unused = StringIO()
            status_unused = run(
                [str(source), "text", "unusedcode", "--only", "UnusedFormalParameter"],
                stdout_unused,
                stderr_unused,
            )
            self.assertEqual(2, status_unused)
            self.assertEqual("", stderr_unused.getvalue())
            output_unused = stdout_unused.getvalue()
            self.assertEqual(1, output_unused.count("such as 'node'"))


    def test_function_local_visitor_import_and_shadowing_are_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "local_visitor_import.py"
            source.write_text(
                "import ast\n"
                "\n"
                "def make_visitor():\n"
                "    from ast import NodeVisitor\n"
                "    class Visitor(NodeVisitor):\n"
                "        def visit_Name(self, node):\n"
                "            return 1\n"
                "    return Visitor\n"
                "\n"
                "def make_ordinary():\n"
                "    ast = object()\n"
                "    class Ordinary(ast.NodeVisitor):\n"
                "        def visit_Name(self, node):\n"
                "            return 1\n"
                "    return Ordinary\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run(
                [str(source), "text", "unusedcode", "--only", "UnusedFormalParameter"],
                stdout,
                stderr,
            )

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(1, stdout.getvalue().count("such as 'node'"))

    def test_ast_visitor_handlers_still_report_body_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "visitor_body.py"
            ruleset = directory / "visitor-rules.xml"
            source.write_text(
                "import ast\n"
                "\n"
                "class Visitor(ast.NodeVisitor):\n"
                "    def visit_Name(self, node):\n"
                "        unused = 1\n"
                "        if node:\n"
                "            return 1\n"
                "        return 0\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                "<ruleset>"
                "<rule ref=\"UnusedLocalVariable\"/>"
                "<rule ref=\"CyclomaticComplexity\"><properties>"
                "<property name=\"reportlevel\" value=\"2\"/>"
                "</properties></rule>"
                "</ruleset>",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn("UnusedLocalVariable", stdout.getvalue())
        self.assertIn("CyclomaticComplexity", stdout.getvalue())

    def test_unusedcode_keeps_exported_private_members_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "exported_member.py"
            source.write_text(
                "__all__ = (\"_helper\",)\n"
                "\n"
                "class Service:\n"
                "    def _helper(self):\n"
                "        return None\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_unusedcode_handles_aliased_dataclasses_and_protocol_default_methods_conservatively(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "generated_contracts.py"
            source.write_text(
                "from dataclasses import dataclass, dataclass as dc\n"
                "from typing import Protocol\n"
                "\n"
                "@dc\n"
                "class Record:\n"
                "    _stored: int\n"
                "\n"
                "@dataclass\n"
                "class Service:\n"
                "    def _dead(self):\n"
                "        return None\n"
                "\n"
                "class Contract(Protocol):\n"
                "    def transform(self, value):\n"
                "        return 0\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("UnusedPrivateMethod [priority 3] Avoid unused private methods such as '_dead'.", report)
        self.assertNotIn("_stored", report)
        self.assertNotIn("UnusedFormalParameter", report)

    def test_unusedcode_reports_an_unused_lambda_parameter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "expression_scopes.py"
            source.write_text(
                "transform = lambda unused: 0\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("UnusedFormalParameter [priority 3] Avoid unused parameters such as 'unused'.", report)

    def test_unusedcode_reports_each_same_line_lambda_parameter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "same_line_lambdas.py"
            source.write_text("lambda a: 0, lambda b: 1\n", encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("Avoid unused parameters such as 'a'.", report)
        self.assertIn("Avoid unused parameters such as 'b'.", report)

    def test_unusedcode_reports_nested_same_line_lambda_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "nested_lambdas.py"
            source.write_text("lambda a: (lambda b: 1)\n", encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("Avoid unused parameters such as 'a'.", report)
        self.assertIn("Avoid unused parameters such as 'b'.", report)

    def test_unusedcode_keeps_map_filter_lambdas_from_raising(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "map_filter.py"
            source.write_text(
                "xs = map(lambda x: x, filter(lambda y: y, [1]))\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "unusedcode"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_python_reports_same_line_lambda_walrus_locals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "walrus_lambdas.py"
            source.write_text("lambda a: (b := 1), lambda c: 2\n", encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "python"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn("Avoid unused local variables such as 'b'.", stdout.getvalue())

    def test_cleancode_finds_each_honest_python_hazard_through_the_command_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "hazards.py"
            source.write_text(
                "class Logger:\n"
                "    @staticmethod\n"
                "    def write(value):\n"
                "        return value\n"
                "\n"
                "def choose(flag: bool):\n"
                "    if flag:\n"
                "        return 1\n"
                "    else:\n"
                "        return 0\n"
                "\n"
                "def inspect(values):\n"
                "    if current := values:\n"
                "        return Logger.write(current)\n"
                "    return {\"alpha\": 1, \"alpha\": 2}\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "cleancode"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        for rule_name in [
            "BooleanArgumentFlag",
            "ElseExpression",
            "StaticAccess",
            "IfStatementAssignment",
            "DuplicatedArrayKey",
        ]:
            self.assertIn(rule_name, report)

    def test_cleancode_reports_only_else_that_follows_an_always_exiting_branch(self) -> None:
        reported = {
            "if_raises": (
                "def decide(value):\n"
                "    if value:\n"
                "        raise ValueError(value)\n"
                "    else:\n"
                "        return 2\n",
                5,
            ),
            "if_returns": (
                "def decide(value):\n"
                "    if value:\n"
                "        return 1\n"
                "    else:\n"
                "        return 2\n",
                5,
            ),
            "for_returns": (
                "def first(values):\n"
                "    for value in values:\n"
                "        return value\n"
                "    else:\n"
                "        return None\n",
                5,
            ),
            "while_returns": (
                "def hunt(items):\n"
                "    while items:\n"
                "        return items.pop()\n"
                "    else:\n"
                "        return None\n",
                5,
            ),
            "try_raises": (
                "def verify(data):\n"
                "    try:\n"
                "        raise ValueError(data)\n"
                "    except ValueError:\n"
                "        return False\n"
                "    else:\n"
                "        return True\n",
                7,
            ),
            "elif_chain_exits": (
                "def chain(value):\n"
                "    if value == 1:\n"
                "        raise ValueError(value)\n"
                "    elif value == 2:\n"
                "        return 2\n"
                "    else:\n"
                "        return 3\n",
                7,
            ),
        }
        quiet = {
            "if_assigns": (
                "def choose(flag):\n"
                "    if flag:\n"
                "        value = 1\n"
                "    else:\n"
                "        value = 0\n"
                "    return value\n"
            ),
            "for_keeps_scanning": (
                "def scan(values):\n"
                "    for value in values:\n"
                "        total += value\n"
                "    else:\n"
                "        return total\n"
            ),
            "while_keeps_scanning": (
                "def drain(items):\n"
                "    while items:\n"
                "        items.pop()\n"
                "    else:\n"
                "        return None\n"
            ),
            "try_completes": (
                "def verify(data):\n"
                "    try:\n"
                "        check(data)\n"
                "    except ValueError:\n"
                "        return False\n"
                "    else:\n"
                "        return True\n"
            ),
            "elif_chain_falls_through": (
                "def keep(value):\n"
                "    if value == 1:\n"
                "        return 1\n"
                "    elif value == 2:\n"
                "        raise ValueError(value)\n"
                "    return 3\n"
            ),
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            for name, (code, _) in {**reported, **{n: (c, None) for n, c in quiet.items()}}.items():
                (Path(temporary_directory) / f"{name}.py").write_text(code, encoding="utf-8")
            for name, (_, line) in reported.items():
                stdout = StringIO()
                stderr = StringIO()
                status = run(
                    [str(Path(temporary_directory) / f"{name}.py"), "json", "cleancode", "--only", "ElseExpression"],
                    stdout,
                    stderr,
                )
                findings = [f for f in json.loads(stdout.getvalue())["findings"] if f["ruleName"] == "ElseExpression"]
                self.assertEqual(2, status, name)
                self.assertEqual("", stderr.getvalue(), name)
                self.assertEqual([line], [f["line"] for f in findings], name)
                self.assertIn("dead or misleading", findings[0]["message"], name)
            for name, code in quiet.items():
                stdout = StringIO()
                stderr = StringIO()
                status = run(
                    [str(Path(temporary_directory) / f"{name}.py"), "json", "cleancode", "--only", "ElseExpression"],
                    stdout,
                    stderr,
                )
                self.assertEqual(0, status, name)
                self.assertEqual(
                    [],
                    [f for f in json.loads(stdout.getvalue())["findings"] if f["ruleName"] == "ElseExpression"],
                    name,
                )
                self.assertEqual("", stderr.getvalue(), name)

    def test_cleancode_keeps_clean_boundaries_and_dynamic_dictionary_keys_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "clean_hazards.py"
            source.write_text(
                "dynamic_key = object()\n"
                "\n"
                "class Worker:\n"
                "    def choose(self, value: object = None):\n"
                "        if value is None:\n"
                "            return Worker.default()\n"
                "        elif value:\n"
                "            return logger.write(value)\n"
                "        return {dynamic_key: 1, dynamic_key: 2, \"first\": 1, \"second\": 2}\n"
                "\n"
                "    @staticmethod\n"
                "    def default():\n"
                "        return 0\n"
                "\n"
                "def calculate(values):\n"
                "    current = values\n"
                "    return (stored := current)\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "cleancode"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_cleancode_uses_python_syntax_boundaries_without_guessing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "boundaries.py"
            source.write_text(
                "from typing import Optional\n"
                "\n"
                "class Logger:\n"
                "    @staticmethod\n"
                "    def write():\n"
                "        return None\n"
                "\n"
                "    @staticmethod\n"
                "    def close():\n"
                "        return None\n"
                "\n"
                "if enabled:\n"
                "    Logger.write()\n"
                "else:\n"
                "    Logger.close()\n"
                "\n"
                "def inspect(option: bool | None = False, *, enabled: Optional[bool] = None, unknown: service.bool = None):\n"
                "    if (lambda: (hidden := option)):\n"
                "        pass\n"
                "    while current := enabled:\n"
                "        break\n"
                "    if \"é\" and (unicode_name := enabled):\n"
                "        pass\n"
                "    return {True: 1, 1: 2, -True: 3, -1: 4, (\"known\", 1): 5, (\"known\", True): 6, ...: 7, ...: 8, dynamic: 9, dynamic: 10, [1]: 11, [1]: 12}\n"
                "\n"
                "class Worker:\n"
                "    if enabled:\n"
                "        def run(self):\n"
                "            return Worker.build()\n"
                "\n"
                "    @staticmethod\n"
                "    def build():\n"
                "        return None\n",
                encoding="utf-8",
            )
            reports = {}
            for rule_name in [
                "BooleanArgumentFlag",
                "ElseExpression",
                "StaticAccess",
                "IfStatementAssignment",
                "DuplicatedArrayKey",
            ]:
                stdout = StringIO()
                stderr = StringIO()
                status = run(
                    [str(source), "text", "cleancode", "--only", rule_name],
                    stdout,
                    stderr,
                )
                reports[rule_name] = (status, stdout.getvalue(), stderr.getvalue())

        self.assertEqual(2, reports["BooleanArgumentFlag"][0])
        self.assertEqual(2, reports["BooleanArgumentFlag"][1].count("BooleanArgumentFlag"))
        self.assertNotIn("unknown", reports["BooleanArgumentFlag"][1])
        self.assertEqual((0, "", ""), reports["ElseExpression"])
        self.assertEqual((0, "", ""), reports["StaticAccess"])
        self.assertEqual(2, reports["IfStatementAssignment"][0])
        self.assertEqual(2, reports["IfStatementAssignment"][1].count("IfStatementAssignment"))
        self.assertIn("column '17'", reports["IfStatementAssignment"][1])
        self.assertNotIn("hidden", reports["IfStatementAssignment"][1])
        self.assertEqual(2, reports["DuplicatedArrayKey"][0])
        self.assertEqual(4, reports["DuplicatedArrayKey"][1].count("DuplicatedArrayKey"))
        self.assertEqual("", reports["DuplicatedArrayKey"][2])

    def test_cleancode_honors_boolean_and_static_access_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "configured_hazards.py"
            ruleset = directory / "configured.xml"
            source.write_text(
                "class Logger:\n"
                "    @staticmethod\n"
                "    def write(value):\n"
                "        return value\n"
                "\n"
                "class Gateway:\n"
                "    @staticmethod\n"
                "    def write(value):\n"
                "        return value\n"
                "\n"
                "class Service:\n"
                "    if enabled:\n"
                "        def choose(self, flag: bool):\n"
                "            return Logger.write(flag)\n"
                "\n"
                "def ignored_choice(flag: bool):\n"
                "    return Logger.write(flag)\n"
                "\n"
                "def active_choice(flag: bool):\n"
                "    return Gateway.write(flag)\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                "<ruleset><rule ref=\"cleancode\"><properties>"
                "<property name=\"exceptions\" value=\"Service,Logger\"/>"
                "<property name=\"ignorepattern\" value=\"^ignored_\"/>"
                "</properties></rule></ruleset>",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertEqual(1, report.count("BooleanArgumentFlag"))
        self.assertEqual(1, report.count("StaticAccess"))
        self.assertIn("active_choice", report)
        self.assertIn("Gateway", report)
        self.assertNotIn("ignored_choice", report)

    def test_method_count_rules_treat_empty_ignorepattern_as_no_exclusions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "five_methods.py"
            source.write_text(
                "class Service:\n"
                "    def alpha(self):\n"
                "        return 1\n"
                "\n"
                "    def beta(self):\n"
                "        return 2\n"
                "\n"
                "    def gamma(self):\n"
                "        return 3\n"
                "\n"
                "    def delta(self):\n"
                "        return 4\n"
                "\n"
                "    def epsilon(self):\n"
                "        return 5\n",
                encoding="utf-8",
            )
            for pattern in ("", "   "):
                with self.subTest(pattern=pattern):
                    ruleset = directory / "five_methods.xml"
                    ruleset.write_text(
                        "<ruleset>"
                        "<rule ref=\"TooManyMethods\"><properties>"
                        "<property name=\"maxmethods\" value=\"1\"/>"
                        f"<property name=\"ignorepattern\" value=\"{pattern}\"/>"
                        "</properties></rule>"
                        "<rule ref=\"TooManyPublicMethods\"><properties>"
                        "<property name=\"maxmethods\" value=\"1\"/>"
                        f"<property name=\"ignorepattern\" value=\"{pattern}\"/>"
                        "</properties></rule>"
                        "</ruleset>",
                        encoding="utf-8",
                    )
                    stdout = StringIO()
                    stderr = StringIO()

                    status = run([str(source), "text", str(ruleset)], stdout, stderr)

                self.assertEqual(2, status)
                self.assertEqual("", stderr.getvalue())
                report = stdout.getvalue()
                self.assertIn(
                    "TooManyMethods [priority 3] The class Service has 5 non-getter- and setter-methods. "
                    "Consider refactoring Service to keep number of methods under 1.",
                    report,
                )
                self.assertIn(
                    "TooManyPublicMethods [priority 3] The class Service has 5 public methods. "
                    "Consider refactoring Service to keep number of public methods under 1.",
                    report,
                )

    def test_method_count_rules_honor_nonempty_ignorepattern(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "five_methods.py"
            ruleset = directory / "five_methods.xml"
            source.write_text(
                "class Service:\n"
                "    def alpha(self):\n"
                "        return 1\n"
                "\n"
                "    def beta(self):\n"
                "        return 2\n"
                "\n"
                "    def gamma(self):\n"
                "        return 3\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                "<ruleset>"
                "<rule ref=\"TooManyMethods\"><properties>"
                "<property name=\"maxmethods\" value=\"1\"/>"
                "<property name=\"ignorepattern\" value=\"^gamma$\"/>"
                "</properties></rule>"
                "</ruleset>",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn(
            "TooManyMethods [priority 3] The class Service has 2 non-getter- and setter-methods. "
            "Consider refactoring Service to keep number of methods under 1.",
            report,
        )

    def test_python_policy_permits_ordinary_idioms_and_opinionated_selects_every_strict_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            ordinary_source = directory / "ordinary_policy.py"
            hazard_source = directory / "opinionated_policy.py"
            logger = (
                "class Logger:\n"
                "    @staticmethod\n"
                "    def write(value):\n"
                "        return value\n"
                "\n"
            )
            ordinary_source.write_text(
                logger
                + "def choose(flag: bool):\n"
                "    if flag:\n"
                "        return Logger.write(flag)\n"
                "    else:\n"
                "        return 0\n",
                encoding="utf-8",
            )
            hazard_source.write_text(
                "import sys\n\n"
                + logger
                + "def choose(values, unused_parameter, flag: bool):\n"
                "    ab = len(values)\n"
                "    Logger.write(ab)\n"
                "    while len(values) > ab:\n"
                "        break\n"
                "    if flag:\n"
                "        return ab\n"
                "    else:\n"
                "        sys.exit(1)\n",
                encoding="utf-8",
            )
            python_stdout = StringIO()
            python_stderr = StringIO()
            python_status = run(
                [str(ordinary_source), "text", "python"], python_stdout, python_stderr
            )
            selected_reports = []
            for rule_name in [
                "ShortVariable",
                "UnusedFormalParameter",
                "BooleanArgumentFlag",
                "ElseExpression",
                "StaticAccess",
                "CountInLoopExpression",
                "ExitExpression",
            ]:
                stdout = StringIO()
                stderr = StringIO()
                status = run(
                    [str(hazard_source), "text", "opinionated", "--only", rule_name],
                    stdout,
                    stderr,
                )
                selected_reports.append((rule_name, status, stdout.getvalue(), stderr.getvalue()))

        self.assertEqual(0, python_status)
        self.assertEqual("", python_stdout.getvalue())
        self.assertEqual("", python_stderr.getvalue())
        for rule_name, status, report, errors in selected_reports:
            self.assertEqual(2, status)
            self.assertEqual("", errors)
            self.assertIn(rule_name, report)

    def test_design_finds_direct_python_hazards_and_keeps_idioms_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "design_hazards.py"
            source.write_text(
                "import contextlib\n"
                "import sys\n"
                "\n"
                "# TODO: remove diagnostic path\n"
                "def stop(values):\n"
                "    while len(values):\n"
                "        breakpoint()\n"
                "        sys.exit(1)\n"
                "\n"
                "def placeholders():\n"
                "    try:\n"
                "        work()\n"
                "    except LookupError:\n"
                "        pass\n"
                "    try:\n"
                "        work()\n"
                "    except RuntimeError:\n"
                "        ...\n"
                "    try:\n"
                "        work()\n"
                "    except OSError:\n"
                "        logger.warning(\"ignored\")\n"
                "    with contextlib.suppress(FileNotFoundError):\n"
                "        work()\n"
                "\n"
                "import sys as platform\n"
                "from sys import exit as stop_alias\n"
                "\n"
                "def rebound_alias(platform):\n"
                "    platform.exit()\n"
                "\n"
                "def rebound_function_alias(stop_alias):\n"
                "    stop_alias()\n"
                "\n"
                "def shadowed(exit, breakpoint, len, values):\n"
                "    exit()\n"
                "    breakpoint()\n"
                "    while len(values):\n"
                "        break\n"
                "\n"
                "def idioms(values):\n"
                "    size = len(values)\n"
                "    while size:\n"
                "        size -= 1\n"
                "    for index in range(len(values)):\n"
                "        print(index)\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "design"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertEqual(1, report.count("ExitExpression"))
        self.assertEqual(1, report.count("CountInLoopExpression"))
        self.assertEqual(2, report.count("DevelopmentCodeFragment"))
        self.assertEqual(2, report.count("EmptyCatchBlock"))
        self.assertNotIn("GotoStatement", report)
        self.assertNotIn("logger.warning", report)

    def test_exit_expression_ignores_module_rebindings_of_imported_names(self) -> None:
        cases = [
            (
                "rebound_function_alias",
                "from sys import exit\n"
                "def exit(code=None):\n"
                "    return code\n"
                "exit(0)\n",
                0,
            ),
            (
                "rebound_module_alias",
                "import sys\n"
                "class Fake:\n"
                "    def exit(self, code=None):\n"
                "        return code\n"
                "sys = Fake()\n"
                "sys.exit(0)\n",
                0,
            ),
            (
                "ordinary_import",
                "import sys\n"
                "sys.exit(0)\n",
                2,
            ),
            (
                "ordinary_function_alias",
                "from sys import exit\n"
                "exit(0)\n",
                2,
            ),
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            for name, source_text, expected_status in cases:
                source = Path(temporary_directory) / f"{name}.py"
                source.write_text(source_text, encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()

                status = run(
                    [str(source), "text", "design", "--only", "ExitExpression"],
                    stdout,
                    stderr,
                )

                self.assertEqual(expected_status, status, name)
                self.assertEqual("", stderr.getvalue(), name)
                if expected_status == 0:
                    self.assertEqual("", stdout.getvalue(), name)
                else:
                    self.assertIn("ExitExpression", stdout.getvalue(), name)

    def test_exit_expression_follows_function_local_exit_imports(self) -> None:
        cases = [
            (
                "local_module_import",
                "def stop():\n"
                "    import sys\n"
                "    sys.exit(1)\n",
                2,
            ),
            (
                "local_function_import",
                "def stop():\n"
                "    from sys import exit\n"
                "    exit(1)\n",
                2,
            ),
            (
                "local_low_level_import",
                "def stop():\n"
                "    import os\n"
                "    os._exit(1)\n",
                2,
            ),
            (
                "local_aliased_import",
                "def stop():\n"
                "    import sys as platform\n"
                "    platform.exit(1)\n",
                2,
            ),
            (
                "local_rebinding_of_local_import",
                "def stop(fake):\n"
                "    import sys\n"
                "    sys = fake\n"
                "    sys.exit(1)\n",
                0,
            ),
            (
                "local_parameter_shadowing",
                "def stop(sys):\n"
                "    sys.exit(1)\n",
                0,
            ),
            (
                "local_import_of_unrelated_module",
                "def stop():\n"
                "    import fake_sys as sys\n"
                "    sys.exit(1)\n",
                0,
            ),
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            for name, source_text, expected_status in cases:
                source = Path(temporary_directory) / f"{name}.py"
                source.write_text(source_text, encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()

                status = run(
                    [str(source), "text", "design", "--only", "ExitExpression"],
                    stdout,
                    stderr,
                )

                self.assertEqual(expected_status, status, name)
                self.assertEqual("", stderr.getvalue(), name)
                if expected_status == 0:
                    self.assertEqual("", stdout.getvalue(), name)
                else:
                    self.assertIn("ExitExpression", stdout.getvalue(), name)

    def test_design_honors_custom_markers_calls_and_priorities_without_importing_target_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "configured_design.py"
            ruleset = directory / "configured-design.xml"
            source.write_text(
                "# REVIEW before release\n"
                "def inspect(items):\n"
                "    acme.trace(items)\n"
                "    ACME.TRACE(items)\n"
                "    while len(items):\n"
                "        sys.exit()\n"
                "    try:\n"
                "        consume(items)\n"
                "    except Exception:\n"
                "        pass\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                "<ruleset><rule ref=\"design\"><priority>4</priority><properties>"
                "<property name=\"unwanted-functions\" value=\"acme.trace\"/>"
                "<property name=\"markers\" value=\"REVIEW\"/>"
                "</properties></rule></ruleset>",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        for rule_name in [
            "ExitExpression",
            "CountInLoopExpression",
            "DevelopmentCodeFragment",
            "EmptyCatchBlock",
        ]:
            self.assertIn(f"{rule_name} [priority 4]", report)
        self.assertEqual(2, report.count("DevelopmentCodeFragment"))
        self.assertNotIn("TODO", report)

    def test_development_code_fragment_matches_markers_as_whole_words_only(self) -> None:
        flagged = [
            "# TODO: later\n",
            "# FIXME now\n",
            "# fixme!\n",
            "# hack above the fold\n",
            "# TODO/FIXME\n",
            "# Todo: later\n",
        ]
        quiet = [
            "# The hacker was here\n",
            "# todolist\n",
            "# fixment\n",
            "# todone with this\n",
        ]
        for source in flagged + quiet:
            expected_status = 2 if source in flagged else 0
            with tempfile.TemporaryDirectory() as temporary_directory:
                source_path = Path(temporary_directory) / "markers.py"
                source_path.write_text(f"def walk():\n    {source}    return 1\n", encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()

                status = run(
                    [str(source_path), "text", "python", "--only", "DevelopmentCodeFragment"],
                    stdout,
                    stderr,
                )

            self.assertEqual(
                expected_status,
                status,
                f"wrong status for comment {source!r}: {stdout.getvalue()!r}",
            )
            self.assertEqual("", stderr.getvalue())
            if expected_status == 0:
                self.assertNotIn("DevelopmentCodeFragment", stdout.getvalue())
            else:
                self.assertIn(
                    "DevelopmentCodeFragment [priority 2]",
                    stdout.getvalue(),
                    f"comment {source!r} should be reported",
                )

    def test_development_code_fragment_honors_custom_markers_as_whole_words(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "custom_markers.py"
            ruleset = directory / "custom-markers.xml"
            source.write_text(
                "def walk():\n"
                "    # REVIEW before release\n"
                "    # reviewed by qc\n"
                "    # REVIEWMENT pending\n"
                "    return 1\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                "<ruleset><rule ref=\"design\"><properties>"
                "<property name=\"markers\" value=\"REVIEW\"/>"
                "</properties></rule></ruleset>",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset), "--only", "DevelopmentCodeFragment"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertEqual(1, report.count("DevelopmentCodeFragment"))
        self.assertIn(":2:", report)
        self.assertNotIn(":3:", report)
        self.assertNotIn(":4:", report)

    def test_development_code_fragment_reports_aliased_debug_calls(self) -> None:
        cases = [
            (
                "direct_module_call",
                "import pdb\n"
                "def compute_total():\n"
                "    pdb.set_trace()\n",
                "pdb.set_trace()",
            ),
            (
                "from_imported_function",
                "from pdb import set_trace\n"
                "def compute_total():\n"
                "    set_trace()\n",
                "pdb.set_trace()",
            ),
            (
                "aliased_module_import",
                "import pdb as debug\n"
                "def compute_total():\n"
                "    debug.set_trace()\n",
                "pdb.set_trace()",
            ),
            (
                "aliased_from_import",
                "from pdb import set_trace as trace\n"
                "def compute_total():\n"
                "    trace()\n",
                "pdb.set_trace()",
            ),
            (
                "function_local_import",
                "def compute_total():\n"
                "    from pdb import set_trace\n"
                "    set_trace()\n",
                "pdb.set_trace()",
            ),
            (
                "builtins_attribute_call",
                "import builtins\n"
                "def compute_total():\n"
                "    builtins.breakpoint()\n",
                "builtins.breakpoint()",
            ),
            (
                "builtins_from_import",
                "from builtins import breakpoint\n"
                "def compute_total():\n"
                "    breakpoint()\n",
                "builtins.breakpoint()",
            ),
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            for name, source_text, debug_call in cases:
                source = Path(temporary_directory) / f"{name}.py"
                source.write_text(source_text, encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()

                status = run(
                    [str(source), "text", "design", "--only", "DevelopmentCodeFragment"],
                    stdout,
                    stderr,
                )

                self.assertEqual(2, status, name)
                self.assertEqual("", stderr.getvalue(), name)
                self.assertIn(
                    f"calls the typical debug function {debug_call} which is mostly only used during development.",
                    stdout.getvalue(),
                    name,
                )

    def test_development_code_fragment_keeps_shadowed_and_unrelated_calls_quiet(self) -> None:
        cases = [
            (
                "user_defined_breakpoint",
                "def breakpoint():\n"
                "    pass\n"
                "\n"
                "def compute_total():\n"
                "    breakpoint()\n",
            ),
            (
                "parameter_shadow",
                "def compute_total(breakpoint):\n"
                "    breakpoint()\n",
            ),
            (
                "rebound_alias",
                "import pdb as debug\n"
                "\n"
                "debug = object()\n"
                "\n"
                "def compute_total():\n"
                "    debug.set_trace()\n",
            ),
            (
                "unrelated_method_call",
                "class Recorder:\n"
                "    def set_trace(self):\n"
                "        ...\n"
                "\n"
                "recorder = Recorder()\n"
                "\n"
                "def compute_total():\n"
                "    recorder.set_trace()\n",
            ),
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            for name, source_text in cases:
                source = Path(temporary_directory) / f"{name}.py"
                source.write_text(source_text, encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()

                status = run(
                    [str(source), "text", "design", "--only", "DevelopmentCodeFragment"],
                    stdout,
                    stderr,
                )

                self.assertEqual(0, status, name)
                self.assertEqual("", stderr.getvalue(), name)
                self.assertEqual("", stdout.getvalue(), name)

    def test_design_policies_keep_goto_loadable_and_strict_rules_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "policy_design.py"
            goto_ruleset = directory / "goto.xml"
            source.write_text(
                "def stop(items):\n"
                "    while len(items):\n"
                "        sys.exit()\n",
                encoding="utf-8",
            )
            goto_ruleset.write_text(
                "<ruleset><rule ref=\"GotoStatement\"/></ruleset>", encoding="utf-8"
            )
            python_stdout = StringIO()
            python_stderr = StringIO()
            python_status = run([str(source), "text", "python"], python_stdout, python_stderr)
            selected = []
            for rule_name in ["ExitExpression", "CountInLoopExpression"]:
                stdout = StringIO()
                stderr = StringIO()
                status = run(
                    [str(source), "text", "opinionated", "--only", rule_name], stdout, stderr
                )
                selected.append((rule_name, status, stdout.getvalue(), stderr.getvalue()))
            goto_stdout = StringIO()
            goto_stderr = StringIO()
            goto_status = run(
                [str(source), "text", str(goto_ruleset)], goto_stdout, goto_stderr
            )

        self.assertEqual((0, "", ""), (python_status, python_stdout.getvalue(), python_stderr.getvalue()))
        for rule_name, status, report, errors in selected:
            self.assertEqual(2, status)
            self.assertEqual("", errors)
            self.assertIn(rule_name, report)
        self.assertEqual((0, "", ""), (goto_status, goto_stdout.getvalue(), goto_stderr.getvalue()))

    def test_design_metrics_find_dependency_state_and_cohesion_hazards(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "design_metrics.py"
            imports = "".join(f"from dependency{index} import Type{index}\n" for index in range(13))
            source.write_text(
                imports
                + "\nshared = {}\n"
                "if runtime_enabled:\n"
                "    conditional_state = {}\n"
                "conditional_state[\"value\"] = 1\n"
                "if registry := {}:\n"
                "    registry.update(value=1)\n"
                "\ndef mutate():\n"
                "    shared[\"value\"] = 1\n"
                "\nclass Coupled(Type0):\n"
                "    @Type1.decorate\n"
                "    def build(self, value: Type2) -> Type3:\n"
                "        return (Type4(), Type5(), Type6(), Type7(), Type8(), Type9(), Type10(), Type11(), Type12())\n"
                "\nclass NonTrivialSetters:\n"
                "    def load_left(self): self.left_state = left_factory.build()\n"
                "    def load_right(self): self.right_state = right_factory.build()\n"
                "\nclass Disconnected:\n"
                "    def left(self):\n"
                "        self.left_state += 1\n"
                "        return self.left_state\n"
                "\n    def right(self):\n"
                "        self.right_state += 1\n"
                "        return self.right_state\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "design"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("CouplingBetweenObjects [priority 2]", report)
        self.assertIn("value of 13", report)
        self.assertIn("GlobalVariable [priority 1]", report)
        self.assertIn("shared", report)
        self.assertIn("conditional_state", report)
        self.assertIn("registry", report)
        self.assertIn("class NonTrivialSetters", report)
        self.assertIn("LackOfCohesionOfMethods [priority 3]", report)
        self.assertIn("value of 2", report)

    def test_design_metrics_keep_exact_boundaries_and_python_idioms_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "clean_design_metrics.py"
            imports = "".join(f"from dependency{index} import Type{index}\n" for index in range(12))
            source.write_text(
                imports
                + "from abc import abstractmethod\n"
                "from typing import Final, Protocol as Proto\n"
                "\nTOKEN: Final = \"stable\"\n"
                "read_only = {}\n"
                "\nclass Connected:\n"
                "    def first(self):\n"
                "        self.state = 1\n"
                "\n    def second(self):\n"
                "        return self.first() + self.state\n"
                "\n    @property\n"
                "    def value(self):\n"
                "        return self.state\n"
                "\n    @abstractmethod\n"
                "    def required(self):\n"
                "        self.unrelated += 1\n"
                "        return self.unrelated\n"
                "\n    def stub(self): ...\n"
                "\n    @staticmethod\n"
                "    def helper():\n"
                "        return Type0()\n"
                "\n    @classmethod\n"
                "    def construct(cls):\n"
                "        return cls()\n"
                "\nclass AccessorConnected:\n"
                "    @property\n"
                "    def item(self):\n"
                "        return self._item\n"
                "\n    def through_property(self):\n"
                "        self.total = self.item\n"
                "        return self.total\n"
                "\n    def through_field(self):\n"
                "        self.total = self._item\n"
                "        return self.total\n"
                "\nclass Contract(Proto):\n"
                "    def first(self): self.first_state += 1; return self.first_state\n"
                "    def second(self): self.second_state += 1; return self.second_state\n"
                "\nclass Twelve(Type0, Type1, Type2, Type3, Type4, Type5, Type6, Type7, Type8, Type9, Type10, Type11):\n"
                "    pass\n",
                encoding="utf-8",
            )
            reports = {}
            for rule_name in ["CouplingBetweenObjects", "GlobalVariable", "LackOfCohesionOfMethods"]:
                stdout = StringIO()
                stderr = StringIO()
                status = run([str(source), "text", "design", "--only", rule_name], stdout, stderr)
                reports[rule_name] = (status, stdout.getvalue(), stderr.getvalue())

        for result in reports.values():
            self.assertEqual((0, "", ""), result)

    def test_design_metrics_honor_configured_thresholds_and_immutable_state_option(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "configured_metrics.py"
            ruleset = directory / "configured-metrics.xml"
            source.write_text(
                "from first import First\n"
                "from second import Second\n"
                "from typing import Final\n"
                "\nTOKEN: Final = 1\n"
                "read_only = {}\n"
                "\n@First.decorate\n"
                "class Coupled(First):\n"
                "    field: Second\n"
                "    duplicate: Second\n"
                "\nclass SyntaxDependencies:\n"
                "    def build(self, value: \"quoted.Dependency\"):\n"
                "        from local_dep import Local\n"
                "        return Local(), external.Dependency(), value\n"
                "\nclass ScopedDependencies:\n"
                "    def shadow(self, External): return External\n"
                "    def build(self): return External(), Other()\n"
                "\nclass AliasedModuleDependencies:\n"
                "    def build(self):\n"
                "        import package.module as dependency\n"
                "        return dependency.First(), dependency.Second()\n"
                "\nclass RelativeDependencies:\n"
                "    def build(self, value: \"quoted.Other\"):\n"
                "        from . import Relative\n"
                "        return Relative(), value\n"
                "\nclass ThreeParts:\n"
                "    def first(self): self.first_state += 1; return self.first_state\n"
                "    def second(self): self.second_state += 1; return self.second_state\n"
                "    def third(self): self.third_state += 1; return self.third_state\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                "<ruleset>"
                "<rule ref=\"CouplingBetweenObjects\"><properties><property name=\"maximum\" value=\"2\"/></properties></rule>"
                "<rule ref=\"GlobalVariable\"><properties><property name=\"report-immutable\" value=\"true\"/></properties></rule>"
                "<rule ref=\"LackOfCohesionOfMethods\"><properties><property name=\"maximum\" value=\"2\"/></properties></rule>"
                "</ruleset>",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("value of 2", report)
        self.assertIn("read_only", report)
        self.assertIn("TOKEN", report)
        self.assertIn("class SyntaxDependencies has a coupling between objects value of 3", report)
        self.assertIn("class ScopedDependencies has a coupling between objects value of 2", report)
        self.assertIn("class AliasedModuleDependencies has a coupling between objects value of 2", report)
        self.assertIn("class RelativeDependencies has a coupling between objects value of 2", report)
        self.assertIn("value of 3", report)

    def test_controversial_adapts_stable_camel_case_rules_to_python_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "strict_names.py"
            source.write_text(
                "ordinary_ = 1\n"
                "transform = lambda badLambdaParameter: badLambdaParameter\n"
                "\ndef build_callback(callback=lambda badDefaultParameter: None):\n"
                "    return callback\n"
                "\nclass bad_class:\n"
                "    BadProperty = 1\n"
                "\n    def badMethod(self, badParameter):\n"
                "        self.OtherProperty = badParameter\n"
                "        localValue = self.OtherProperty\n"
                "        return localValue\n"
                "\n    @property\n"
                "    def BadAccessor(self):\n"
                "        return self.OtherProperty\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "controversial"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        expected = {
            "CamelCaseClassName [priority 1] The class bad_class is not named in CapWords.",
            "CamelCaseMethodName [priority 1] The method badMethod is not named in snake_case.",
            "CamelCasePropertyName [priority 1] The property BadProperty is not named in snake_case.",
            "CamelCasePropertyName [priority 1] The property OtherProperty is not named in snake_case.",
            "CamelCasePropertyName [priority 1] The property BadAccessor is not named in snake_case.",
            "CamelCaseParameterName [priority 1] The parameter badParameter is not named in snake_case.",
            "CamelCaseParameterName [priority 1] The parameter badLambdaParameter is not named in snake_case.",
            "CamelCaseParameterName [priority 1] The parameter badDefaultParameter is not named in snake_case.",
            "CamelCaseVariableName [priority 1] The variable ordinary_ is not named in snake_case.",
            "CamelCaseVariableName [priority 1] The variable localValue is not named in snake_case.",
        }
        for finding in expected:
            self.assertIn(finding, report)
        self.assertEqual(len(expected), len(report.splitlines()))

    def test_controversial_accepts_capwords_and_role_appropriate_snake_case(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "clean_strict_names.py"
            source.write_text(
                "class HTTP2Client:\n"
                "    retry_count = 0\n"
                "\n    def fetch_value(self, item_count, *, default_value=None):\n"
                "        current_value = item_count\n"
                "        self.last_value = current_value\n"
                "        return current_value if current_value else default_value\n"
                "\n    @property\n"
                "    def display_name(self):\n"
                "        return self.last_value\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "controversial"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_controversial_keeps_idiomatic_private_generic_and_computed_names_quiet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "idiomatic_names.py"
            source.write_text(
                "from typing import TypeVar\n"
                "\nValueType = TypeVar(\"ValueType\")\n"
                "DEFAULT_VALUE = 1\n"
                "\nclass _private_helper:\n"
                "    pass\n"
                "\nclass PublicAPI:\n"
                "    def __init__(self, value, /, *args, keyword_only=None, **kwargs):\n"
                "        self.__privateValue = value\n"
                "        class_ = keyword_only\n"
                "        setattr(self, \"runtimeName\", class_)\n"
                "        for i in args:\n"
                "            self._privateValue = i\n"
                "\n    def _privateMethod(self, cls):\n"
                "        try:\n"
                "            return cls\n"
                "        except Exception as e:\n"
                "            return e\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()

            status = run([str(source), "text", "controversial"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_complete_python_policies_compose_catalogue_and_project_behavior(self) -> None:
        fixture = Path(__file__).parent / "fixtures" / "policy_project"
        idiomatic = fixture / "idiomatic.py"
        strict = fixture / "strict_hazards.py"
        recommended = fixture / "recommended_hazards.py"
        components = {
            "codesize": [
                "CyclomaticComplexity", "NPathComplexity", "ExcessiveMethodLength",
                "ExcessiveClassLength", "ExcessiveParameterList", "ExcessivePublicCount",
                "TooManyFields", "TooManyMethods", "TooManyPublicMethods", "ExcessiveClassComplexity",
            ],
            "naming": [
                "ShortClassName", "LongClassName", "ShortVariable", "LongVariable",
                "ShortMethodName", "ConstantNamingConventions", "BooleanGetMethodName",
                "ConstructorWithNameAsEnclosingClass",
            ],
            "unusedcode": [
                "UnusedPrivateField", "UnusedLocalVariable", "UnusedPrivateMethod", "UnusedFormalParameter",
            ],
            "cleancode": [
                "BooleanArgumentFlag", "ElseExpression", "StaticAccess",
                "IfStatementAssignment", "DuplicatedArrayKey",
            ],
            "design": [
                "ExitExpression", "GotoStatement", "CountInLoopExpression",
                "DevelopmentCodeFragment", "EmptyCatchBlock", "CouplingBetweenObjects",
                "GlobalVariable", "LackOfCohesionOfMethods",
            ],
            "controversial": [
                "CamelCaseClassName", "CamelCaseMethodName", "CamelCasePropertyName",
                "CamelCaseParameterName", "CamelCaseVariableName",
            ],
        }
        for component, names in components.items():
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(idiomatic), "text", component, "--verbose"], stdout, stderr)
            self.assertEqual(2 if component == "naming" else 0, status, component)
            if component != "naming":
                self.assertEqual("", stdout.getvalue(), component)
            self.assertEqual(f"Loaded rules: {', '.join(names)}\n", stderr.getvalue(), component)

        python_names = [
            *components["codesize"],
            "ShortClassName", "LongClassName", "LongVariable", "ShortMethodName",
            "ConstantNamingConventions", "BooleanGetMethodName", "UnusedPrivateField",
            "UnusedLocalVariable", "UnusedPrivateMethod", "IfStatementAssignment",
            "DuplicatedArrayKey", "DevelopmentCodeFragment", "EmptyCatchBlock",
            "CouplingBetweenObjects", "GlobalVariable", "LackOfCohesionOfMethods",
            *components["controversial"],
        ]
        stdout = StringIO()
        stderr = StringIO()
        status = run([str(idiomatic), "text", "python", "--verbose"], stdout, stderr)
        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual(f"Loaded rules: {', '.join(python_names)}\n", stderr.getvalue())

        strict_names = [
            "ShortVariable", "UnusedFormalParameter", "BooleanArgumentFlag", "ElseExpression",
            "StaticAccess", "CountInLoopExpression", "ExitExpression",
        ]
        stdout = StringIO()
        stderr = StringIO()
        status = run([str(strict), "text", "opinionated", "--verbose"], stdout, stderr)
        self.assertEqual(2, status)
        self.assertEqual(f"Loaded rules: {', '.join(strict_names)}\n", stderr.getvalue())
        for name in strict_names:
            self.assertIn(name, stdout.getvalue())

        stdout = StringIO()
        stderr = StringIO()
        status = run([str(fixture), "text", "python,opinionated", "--verbose"], stdout, stderr)
        self.assertEqual(2, status)
        self.assertEqual(f"Loaded rules: {', '.join([*python_names, *strict_names])}\n", stderr.getvalue())
        self.assertIn("DuplicatedArrayKey", stdout.getvalue())
        for name in strict_names:
            self.assertIn(name, stdout.getvalue())

        stdout = StringIO()
        stderr = StringIO()
        status = run(
            [str(fixture), "text", "python,opinionated", "--maximum-priority", "1"],
            stdout,
            stderr,
        )
        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        self.assertIn("BooleanArgumentFlag [priority 1]", stdout.getvalue())
        self.assertIn("IfStatementAssignment [priority 1]", stdout.getvalue())
        self.assertNotIn("[priority 2]", stdout.getvalue())
        self.assertNotIn("[priority 3]", stdout.getvalue())

        stdout = StringIO()
        stderr = StringIO()
        status = run([str(strict), "text", "python"], stdout, stderr)
        self.assertEqual(0, status)
        self.assertEqual("", stderr.getvalue())
        for name in strict_names:
            self.assertNotIn(name, stdout.getvalue())

        stdout = StringIO()
        stderr = StringIO()
        status = run([str(recommended), "text", "python"], stdout, stderr)
        self.assertEqual(2, status)
        self.assertIn("descriptive_name_exactly_boundaryxxx", stdout.getvalue())

        stdout = StringIO()
        stderr = StringIO()
        status = run([str(idiomatic), "text", str(fixture / "custom-python.xml")], stdout, stderr)
        self.assertEqual(2, status)
        self.assertIn("descriptive_name_exactly_boundaryxx", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

        for ruleset, name in [
            ("naming", "ConstructorWithNameAsEnclosingClass"),
            ("design", "GotoStatement"),
        ]:
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(fixture), "text", ruleset, "--only", name], stdout, stderr)
            self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_help_describes_command_shape_and_exit_codes(self) -> None:
        stdout = StringIO()
        stderr = StringIO()

        status = run(["--help"], stdout, stderr)

        self.assertEqual(0, status)
        self.assertIn("messpy <paths> <format> <ruleset[,ruleset...]> [options]", stdout.getvalue())
        self.assertIn("text, xml, json, html, ansi, github, gitlab, checkstyle, sarif", stdout.getvalue())
        self.assertIn("--suffixes", stdout.getvalue())
        self.assertIn("--exclude", stdout.getvalue())
        self.assertIn("--ignore-tests", stdout.getvalue())
        self.assertIn("--reportfile", stdout.getvalue())
        self.assertIn("--strict", stdout.getvalue())
        self.assertIn("--color <auto|always|never>", stdout.getvalue())
        self.assertIn("--ignore-errors-on-exit", stdout.getvalue())
        self.assertIn("--ignore-violations-on-exit", stdout.getvalue())
        self.assertIn("Input directory symlinks are scanned; nested directory symlinks are skipped.", stdout.getvalue())
        self.assertIn("0 clean", stdout.getvalue())
        self.assertIn("2 findings", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_multiple_generator_expressions_on_same_line_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "genexps.py"
            source.write_text(
                "def g():\n"
                "    return f((a for a in (x for x in y)), (c for c in d))\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"], stdout, stderr)
            self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_walrus_in_nested_scope_within_comprehension_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "walrus_nested.py"
            source.write_text(
                "def outer():\n"
                "    return [(lambda: (inner_var := 1))() for _ in range(5)]\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"], stdout, stderr)
            self.assertEqual(2, status)
            self.assertIn("UnusedLocalVariable [priority 3] Avoid unused local variables such as 'inner_var'.", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())

    def test_multiple_lambdas_on_same_line_with_differing_depths_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "same_line_lambdas.py"
            source.write_text(
                "def test_fn():\n"
                "    g(lambda a: (lambda b: 1)(), lambda c: 2)\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "unusedcode", "--only", "UnusedFormalParameter"], stdout, stderr)
            self.assertEqual(2, status)
            self.assertIn("Avoid unused parameters such as 'a'.", stdout.getvalue())
            self.assertIn("Avoid unused parameters such as 'b'.", stdout.getvalue())
            self.assertIn("Avoid unused parameters such as 'c'.", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())

    def test_class_with_base_inside_match_case_and_except_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "nested_classes.py"
            source.write_text(
                "match x:\n"
                "    case 1:\n"
                "        class InnerMatch(Base):\n"
                "            pass\n"
                "try:\n"
                "    pass\n"
                "except Exception:\n"
                "    class InnerExcept(Base):\n"
                "        pass\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "codesize"], stdout, stderr)
            self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_functions_inside_except_and_match_case_analyzed_for_codesize(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "nested_callables.py"
            source.write_text(
                "try:\n"
                "    pass\n"
                "except Exception:\n"
                "    def handler_func(a, b, c, d, e, f, g, h, i, j, k):\n"
                "        pass\n"
                "match x:\n"
                "    case 1:\n"
                "        def match_func(a, b, c, d, e, f, g, h, i, j, k):\n"
                "            pass\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "codesize", "--only", "ExcessiveParameterList"], stdout, stderr)
            self.assertEqual(2, status)
            self.assertIn("The function handler_func has 11 parameters.", stdout.getvalue())
            self.assertIn("The function match_func has 11 parameters.", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())

    def test_match_mapping_rest_pattern_analyzed_for_unused_and_naming(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "match_mapping.py"
            source.write_text(
                "def parse_payload(payload):\n"
                "    match payload:\n"
                "        case {'type': 'event', **unused_rest}:\n"
                "            pass\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"], stdout, stderr)
            self.assertEqual(2, status)
            self.assertIn("UnusedLocalVariable [priority 3] Avoid unused local variables such as 'unused_rest'.", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())

    def test_starred_unpacking_targets_analyzed_for_unused_variables(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "starred_unpacking.py"
            source.write_text(
                "def f(items):\n"
                "    return [a for a, *unused_b in items]\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "unusedcode", "--only", "UnusedLocalVariable"], stdout, stderr)
            self.assertEqual(2, status)
            self.assertIn("UnusedLocalVariable [priority 3] Avoid unused local variables such as 'unused_b'.", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())

    @unittest.skipIf(sys.version_info < (3, 12), "PEP 695 type aliases require Python 3.12+")
    def test_pep695_type_alias_not_flagged_as_snake_case_variable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "pep695_type.py"
            source.write_text(
                "type Point = tuple[float, float]\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "python", "--only", "CamelCaseVariableName"], stdout, stderr)
            self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_type_alias_annotation_not_flagged_as_snake_case_variable(self) -> None:
        sources = [
            "from typing import TypeAlias\nPoint: TypeAlias = tuple[int, int]\n",
            "import typing\nPoint: typing.TypeAlias = tuple[int, int]\n",
        ]
        for source_text in sources:
            with tempfile.TemporaryDirectory() as temporary_directory:
                source = Path(temporary_directory) / "typealias.py"
                source.write_text(source_text, encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()
                status = run([str(source), "text", "python", "--only", "CamelCaseVariableName"], stdout, stderr)
                self.assertEqual(
                    (0, "", ""),
                    (status, stdout.getvalue(), stderr.getvalue()),
                    f"wrong result for {source_text!r}",
                )

    def test_aliased_type_alias_annotation_not_flagged_as_snake_case_variable(self) -> None:
        sources = [
            "from typing import TypeAlias as TA\nPoint: TA = tuple[int, int]\n",
            "import typing as t\nPoint: t.TypeAlias = tuple[int, int]\n",
        ]
        for source_text in sources:
            with tempfile.TemporaryDirectory() as temporary_directory:
                source = Path(temporary_directory) / "aliased_typealias.py"
                source.write_text(source_text, encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()
                status = run([str(source), "text", "python", "--only", "CamelCaseVariableName"], stdout, stderr)
                self.assertEqual(
                    (0, "", ""),
                    (status, stdout.getvalue(), stderr.getvalue()),
                    f"wrong result for {source_text!r}",
                )

    def test_snake_case_type_alias_annotation_matches_pep695_class_role(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "typealias_snake.py"
            source.write_text(
                "from typing import TypeAlias\npoint: TypeAlias = tuple[int, int]\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "python", "--only", "CamelCaseClassName"], stdout, stderr)
            self.assertEqual(2, status)
            self.assertIn("The class point is not named in CapWords.", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())
        if sys.version_info < (3, 12):
            return
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "pep695_snake.py"
            source.write_text("type point = tuple[int, int]\n", encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "python", "--only", "CamelCaseClassName"], stdout, stderr)
            self.assertEqual(2, status)
            self.assertIn("The class point is not named in CapWords.", stdout.getvalue())
            self.assertEqual("", stderr.getvalue())

    def test_plain_annotated_assignment_still_flagged_as_camel_case_variable(self) -> None:
        still_variable = [
            "Point: int = 1\n",
            "Point: TypeAliasType = tuple[int, int]\n",
            "Point: foo.TypeAlias = tuple[int, int]\n",
        ]
        for source_text in still_variable:
            with tempfile.TemporaryDirectory() as temporary_directory:
                source = Path(temporary_directory) / "plain_ann.py"
                source.write_text(source_text, encoding="utf-8")
                stdout = StringIO()
                stderr = StringIO()
                status = run([str(source), "text", "python", "--only", "CamelCaseVariableName"], stdout, stderr)
                self.assertEqual(2, status, f"wrong status for {source_text!r}: {stdout.getvalue()!r}")
                self.assertIn("The variable Point is not named in snake_case.", stdout.getvalue())
                self.assertEqual("", stderr.getvalue())
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "plain_snake.py"
            source.write_text("point: int = 1\n", encoding="utf-8")
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "python", "--only", "CamelCaseClassName"], stdout, stderr)
            self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_nested_scopes_do_not_leak_bindings_into_outer_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "nested_scope_leak.py"
            source.write_text(
                "shared = [1]\n"
                "\n"
                "def check_count_in_loop(items):\n"
                "    def helper():\n"
                "        len = 1\n"
                "    while len(items):\n"
                "        pass\n"
                "\n"
                "def check_exit_expression():\n"
                "    class Helper:\n"
                "        sys = 1\n"
                "    sys.exit()\n"
                "\n"
                "def check_development_fragment():\n"
                "    async def async_helper():\n"
                "        breakpoint = 1\n"
                "    breakpoint()\n"
                "\n"
                "def check_global_variable():\n"
                "    def inner():\n"
                "        shared = 2\n"
                "    shared.append(3)\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run(
                [
                    str(source),
                    "text",
                    "design",
                    "--only",
                    "CountInLoopExpression,ExitExpression,DevelopmentCodeFragment,GlobalVariable",
                ],
                stdout,
                stderr,
            )
            self.assertEqual(2, status)
            report = stdout.getvalue()
            self.assertIn("CountInLoopExpression", report)
            self.assertIn("ExitExpression", report)
            self.assertIn("DevelopmentCodeFragment", report)
            self.assertIn("GlobalVariable", report)
            self.assertEqual("", stderr.getvalue())

    def test_global_variable_ignores_nested_global_for_outer_local_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "nested_global.py"
            source.write_text(
                "state = {}\n"
                "async_state = {}\n"
                "class_state = {}\n"
                "\n"
                "def outer():\n"
                "    def inner():\n"
                "        global state\n"
                "        return state\n"
                "    state = {}\n"
                "\n"
                "async def async_outer():\n"
                "    def inner():\n"
                "        global async_state\n"
                "        return async_state\n"
                "    async_state = {}\n"
                "\n"
                "def class_outer():\n"
                "    class Inner:\n"
                "        global class_state\n"
                "        value = class_state\n"
                "    class_state = {}\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run(
                [str(source), "text", "design", "--only", "GlobalVariable"],
                stdout,
                stderr,
            )
            self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_global_variable_ignores_class_attribute_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "class_attributes.py"
            source.write_text(
                "state = 0\n"
                "typed_state = None\n"
                "\n"
                "class Container:\n"
                "    state = 1\n"
                "    typed_state: str = \"active\"\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "design", "--only", "GlobalVariable"], stdout, stderr)

        self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_global_variable_reports_explicit_global_assignments_in_class_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "class_globals.py"
            source.write_text(
                "state = {}\n"
                "nested_state = {}\n"
                "\n"
                "class Container:\n"
                "    global state\n"
                "    state = {}\n"
                "\n"
                "def outer():\n"
                "    class Nested:\n"
                "        global nested_state\n"
                "        nested_state = {}\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", "design", "--only", "GlobalVariable"], stdout, stderr)

        self.assertEqual(2, status)
        self.assertEqual("", stderr.getvalue())
        report = stdout.getvalue()
        self.assertIn("state", report)
        self.assertIn("nested_state", report)

    def test_global_variable_reports_same_scope_and_nested_mutations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "scoped_global.py"
            source.write_text(
                "mutated = {}\n"
                "inner_mutated = {}\n"
                "guarded = {}\n"
                "\n"
                "def outer():\n"
                "    global mutated\n"
                "    mutated = {}\n"
                "\n"
                "def nested():\n"
                "    def inner():\n"
                "        global inner_mutated\n"
                "        inner_mutated = {}\n"
                "\n"
                "def guarded_outer():\n"
                "    if True:\n"
                "        global guarded\n"
                "    guarded = {}\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run(
                [str(source), "text", "design", "--only", "GlobalVariable"],
                stdout,
                stderr,
            )
            self.assertEqual(2, status)
            report = stdout.getvalue()
            self.assertIn("mutated", report)
            self.assertIn("inner_mutated", report)
            self.assertIn("guarded", report)
            self.assertEqual("", stderr.getvalue())

    def test_nested_function_or_class_name_itself_binds_in_outer_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "nested_name_binds.py"
            source.write_text(
                "def check_exit_shadowed_by_nested_func():\n"
                "    def exit():\n"
                "        pass\n"
                "    exit()\n"
                "\n"
                "def check_exit_shadowed_by_nested_class():\n"
                "    class exit:\n"
                "        pass\n"
                "    exit()\n",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run(
                [str(source), "text", "design", "--only", "ExitExpression"],
                stdout,
                stderr,
            )
            self.assertEqual((0, "", ""), (status, stdout.getvalue(), stderr.getvalue()))

    def test_direct_bindings_isolates_nested_scopes(self) -> None:
        module = ast.parse(
            "def outer(param):\n"
            "    outer_var = 1\n"
            "    def inner_func(inner_param):\n"
            "        inner_var = 2\n"
            "        import inner_mod\n"
            "    async def inner_async(async_param):\n"
            "        async_var = 3\n"
            "        from async_pkg import async_mod\n"
            "    class InnerClass:\n"
            "        class_attr = 4\n"
            "        def method(self):\n"
            "            method_var = 5\n"
        )
        outer_scope = module.body[0]
        outer_bindings = _direct_bindings(outer_scope)
        self.assertEqual(
            {"param", "outer_var", "inner_func", "inner_async", "InnerClass"},
            outer_bindings,
        )

    def test_is_protocol_recognizes_generic_and_subscripted_protocols(self) -> None:
        module = ast.parse(
            "from typing import Protocol, TypeVar, Generic\n"
            "import typing\n"
            "import typing as t\n"
            "T = TypeVar('T')\n"
            "U = TypeVar('U')\n"
            "class PlainProtocol(Protocol):\n"
            "    pass\n"
            "class GenericProtocolDirect(Protocol[T]):\n"
            "    pass\n"
            "class GenericProtocolMulti(Protocol[T, U]):\n"
            "    pass\n"
            "class GenericProtocolTyping(typing.Protocol[T]):\n"
            "    pass\n"
            "class GenericProtocolAlias(t.Protocol[T]):\n"
            "    pass\n"
            "class RegularGeneric(Generic[T]):\n"
            "    pass\n"
            "class SubscriptList(list[int]):\n"
            "    pass\n"
        )
        protocol_names = _protocol_base_names(module)
        classes = {node.name: node for node in module.body if isinstance(node, ast.ClassDef)}

        self.assertTrue(_is_protocol(classes["PlainProtocol"], protocol_names))
        self.assertTrue(_is_protocol(classes["GenericProtocolDirect"], protocol_names))
        self.assertTrue(_is_protocol(classes["GenericProtocolMulti"], protocol_names))
        self.assertTrue(_is_protocol(classes["GenericProtocolTyping"], protocol_names))
        self.assertTrue(_is_protocol(classes["GenericProtocolAlias"], protocol_names))
        self.assertFalse(_is_protocol(classes["RegularGeneric"], protocol_names))
        self.assertFalse(_is_protocol(classes["SubscriptList"], protocol_names))

    def test_generic_protocols_recognized_and_exempt_from_class_and_parameter_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "generic_proto.py"
            ruleset = Path(temporary_directory) / "ruleset.xml"
            source.write_text(
                "from typing import Protocol, TypeVar\n"
                "import typing\n"
                "import typing as t\n"
                "T = TypeVar('T')\n"
                "class DirectGenericProto(Protocol[T]):\n"
                "    def default_method(self, unused_param: int) -> int:\n"
                "        return 1\n"
                "    def m2(self): self.a = 1; return self.a\n"
                "    def m3(self): self.b = 2; return self.b\n"
                "class TypingGenericProto(typing.Protocol[T]):\n"
                "    def method(self, arg: str) -> str:\n"
                "        return arg\n"
                "    def extra(self, unused_extra: int) -> int:\n"
                "        return 2\n"
                "class AliasedGenericProto(t.Protocol[T]):\n"
                "    def transform(self, value: int) -> int:\n"
                "        return 0\n",
                encoding="utf-8",
            )
            ruleset.write_text(
                """<ruleset name="test_generic_protocols">
    <rule ref="TooManyMethods"><properties><property name="maxmethods" value="1" /></properties></rule>
    <rule ref="TooManyPublicMethods"><properties><property name="maxmethods" value="1" /></properties></rule>
    <rule ref="LackOfCohesionOfMethods"><properties><property name="maximum" value="1" /></properties></rule>
    <rule ref="UnusedFormalParameter" />
</ruleset>
""",
                encoding="utf-8",
            )
            stdout = StringIO()
            stderr = StringIO()
            status = run([str(source), "text", str(ruleset)], stdout, stderr)

        self.assertEqual(0, status)
        self.assertEqual("", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())


def _long_function(name: str) -> str:
    return f"def {name}():\n" + "    pass\n" * 100


def _function_with_passes(name: str, count: int) -> str:
    return f"def {name}():\n" + "    pass\n" * count


def _finding_for(path: Path, name: str, line: int = 1) -> str:
    return (
        f"{path.resolve().as_posix()}:{line}: ExcessiveMethodLength "
        "[priority 3] "
        f"The function {name}() has 101 lines of code. Current threshold is set to 100. Avoid really long methods."
    )
