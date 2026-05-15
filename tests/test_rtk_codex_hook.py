#!/usr/bin/env python3

from __future__ import annotations

import base64
import json
import os
import shlex
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
HOOK = PLUGIN_ROOT / "hooks" / "rtk-codex-hook"
OUTPUT_GUARD = PLUGIN_ROOT / "hooks" / "rtk-output-guard"
BYPASS_ENV = [
    "RTK_CODEX_HOOK_DISABLE",
    "RTK_CODEX_BYPASS",
    "RTK_DISABLE",
    "RTK_DISABLED",
]

LEGACY_WRAPPER_BYPASS_ENV = [
    "RTK_DISABLE_WRAPPERS",
    "RTK_WRAPPERS_DISABLE",
]


def payload(command: str) -> str:
    return json.dumps(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": command},
        }
    )


class RtkCodexHookTest(unittest.TestCase):
    def run_hook(
        self,
        command: str,
        *,
        rtk_body: str | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            if rtk_body is not None:
                rtk = fake_bin / "rtk"
                rtk.write_text(rtk_body, encoding="utf8")
                rtk.chmod(rtk.stat().st_mode | stat.S_IXUSR)

            process_env = {
                **os.environ,
                "PATH": f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}",
            }
            for name in BYPASS_ENV:
                process_env.pop(name, None)
            if env:
                process_env.update(env)

            return subprocess.run(
                [str(HOOK)],
                input=payload(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                env=process_env,
                timeout=5,
            )

    def assert_no_output(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def rewritten_command(self, result: subprocess.CompletedProcess[str]) -> str:
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)["hookSpecificOutput"]["updatedInput"]["command"]

    def guarded_command_payload(self, command: str) -> str:
        tokens = shlex.split(command)
        self.assertIn(str(OUTPUT_GUARD), tokens)
        index = tokens.index("--b64")
        return base64.b64decode(tokens[index + 1].encode("ascii"), validate=True).decode("utf8")

    def test_rewrites_eligible_command(self) -> None:
        result = self.run_hook(
            "ls -la",
            rtk_body=textwrap.dedent(
                """\
                #!/usr/bin/env sh
                shift
                printf 'rtk %s\\n' "$*"
                """
            ),
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "updatedInput": {"command": "rtk ls -la"},
                }
            },
        )

    def test_accepts_rtk_rewrite_success_code_three(self) -> None:
        result = self.run_hook(
            "git status",
            rtk_body=textwrap.dedent(
                """\
                #!/usr/bin/env sh
                shift
                printf 'rtk %s\\n' "$*"
                exit 3
                """
            ),
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            json.loads(result.stdout),
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "updatedInput": {"command": "rtk git status"},
                }
            },
        )

    def test_rewrites_literal_backslash_n_quotes_and_backslashes(self) -> None:
        for command in [
            r"printf 'literal\nvalue'",
            r"python -c 'print(\"x\\y\")'",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\nexit 3\n",
                )

                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    json.loads(result.stdout),
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "updatedInput": {"command": f"rtk {command}"},
                        }
                    },
                )

    def test_passes_through_machine_readable_split_flags(self) -> None:
        for command in [
            "kubectl get pods -o json",
            "kubectl get pods -ojson",
            "kubectl get pods -o=json",
            "kubectl get pods -o jsonpath={.items[*].metadata.name}",
            "kubectl get pods -o=jsonpath={.items[*].metadata.name}",
            "kubectl get pods --output=yaml",
            "aws ec2 describe-instances --output json",
            "fd foo --format json",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                )
                self.assert_no_output(result)

    def test_passes_through_control_rg_files_and_tests(self) -> None:
        for command in [
            "rg --files",
            "rg --json needle",
            "rg -l needle .",
            "rg -L needle .",
            "rg --count needle .",
            "rg --stats needle .",
            "rg --vimgrep needle .",
            "rg --null needle .",
            "rg -0 needle .",
            "rg foo.bar src",
            "rg foo-bar src",
            "rg simpleIdentifier src",
            "grep foo.bar src/app.py",
            "grep foo-bar src/app.py",
            "grep simpleIdentifier src/app.py",
            "grep -c alpha file.txt",
            "grep -l alpha file.txt",
            "grep -q alpha file.txt",
            "grep -cl alpha file.txt",
            "grep -m1 alpha file.txt",
            "grep -m 1 alpha file.txt",
            "grep --max-count 1 alpha file.txt",
            "git status --short",
            "git status -s",
            "git status -sb",
            "git status --branch --short",
            "git status --porcelain",
            "git status --porcelain=v2 -z",
            "git diff --name-only",
            "git diff --name-only -z",
            "git show --name-only --format=",
            "git log --name-only -z",
            "git ls-files -z",
            "jq -r .foo file.json",
            "jq -c . file.json",
            "find . -type f",
            "base64 binary.bin",
            "file binary.bin",
            "hexdump -C binary.bin",
            "xxd binary.bin",
            "cargo test",
            "go test ./...",
            "pytest -q",
            "python -m pytest",
            "make test",
            "make check",
            "make build",
            "npm run test",
            "npm run build",
            "pnpm check",
            "pnpm build",
            "yarn test",
            "yarn build",
            "cargo build",
            "go build ./...",
            "vitest run",
            "rspec spec",
            "echo hi | cat",
            "echo hi\npwd",
            "sleep 1 & echo done",
            "echo $(pwd)",
            "echo `pwd`",
            "(pwd)",
            "( echo hi )",
            "(cd /tmp; pwd)",
            "cat <(printf hi)",
            "cat <<EOF\nhi\nEOF",
            "echo hi > out.txt",
            "cat < input.txt",
            "true && echo ok",
            "false || echo ok",
            "echo one; echo two",
            "timeout 5 git status",
            "time (pwd)",
            "sh -c 'git status'",
            "bash -lc 'git status'",
            "RTK_DISABLE=1 git status",
            "RTK_DISABLED=1 git status",
            "RTK_CODEX_HOOK_DISABLE=1 git status",
            "env RTK_DISABLE=1 git status",
            "env RTK_DISABLED=1 git status",
            "ssh host.example ls",
            "vim file.txt",
            "docker ps",
            "docker compose ps",
            "docker exec -it container sh",
            "kubectl exec -it pod -- sh",
            "rg -cl needle .",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                )
                self.assert_no_output(result)

    def test_passes_through_pitlane_owned_navigation_shapes(self) -> None:
        for command in [
            "cat src/app.py",
            "cat hooks/rtk-codex-hook",
            "head -n 20 src/app.py",
            "head -n20 hooks/rtk-codex-hook",
            "sed -n '1,20p' src/app.py",
            "sed -n '1,20p' hooks/rtk-codex-hook",
            "ls -R src",
            "ls -laR hooks",
            "tree src",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                )
                self.assert_no_output(result)

    def test_passes_through_env_prefixed_exact_output_commands(self) -> None:
        for command in [
            "LC_ALL=C rg --files",
            "env LC_ALL=C rg --files",
            "env -i LC_ALL=C rg --files",
            "env -- LC_ALL=C rg --files",
            "LC_ALL=C grep -c alpha file.txt",
            "env LC_ALL=C grep -c alpha file.txt",
            "env -u FOO LC_ALL=C grep -c alpha file.txt",
            "LC_ALL=C git status --short",
            "LC_ALL=C git diff --name-only",
            "env LC_ALL=C jq -c . file.json",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\nexit 3\n",
                )
                self.assert_no_output(result)

    def test_guards_line_limited_long_line_pipelines_without_rtk(self) -> None:
        for command in [
            "rg session_meta session.jsonl | head -n 5",
            "grep session_meta session.jsonl | tail -n 5",
            "sed -n '1,20p' session.jsonl | head -n 5",
            "codex debug prompt-input | rg -m 3 atlas-data-inspection",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(command)
                rewritten = self.rewritten_command(result)
                self.assertEqual(self.guarded_command_payload(rewritten), command)

    def test_guards_direct_long_line_file_limiters_without_rtk(self) -> None:
        for command in [
            "head -n 5 session.jsonl",
            "tail -n 20 teledex.log",
            "sed -n '1,5p' exchange.ndjson",
            "codex debug prompt-input",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(command)
                rewritten = self.rewritten_command(result)
                self.assertEqual(self.guarded_command_payload(rewritten), command)

    def test_does_not_guard_non_limited_shell_control_or_plain_text_head(self) -> None:
        for command in [
            "echo hi | cat",
            "rg needle . | wc -l",
            "head -n 5 README.md",
        ]:
            with self.subTest(command=command):
                result = self.run_hook(command)
                self.assert_no_output(result)

    def test_rewrites_safe_transparent_env_prefixes(self) -> None:
        for command, expected in [
            ("FOO=bar git status", "FOO=bar rtk git status"),
            ("env FOO=bar git status", "env FOO=bar rtk git status"),
        ]:
            with self.subTest(command=command):
                result = self.run_hook(
                    command,
                    rtk_body=textwrap.dedent(
                        """\
                        #!/usr/bin/env sh
                        shift
                        case "$1" in
                          "FOO=bar git status") printf 'FOO=bar rtk git status\\n' ;;
                          "env FOO=bar git status") printf 'env FOO=bar rtk git status\\n' ;;
                          *) printf 'unexpected command: %s\\n' "$1"; exit 42 ;;
                        esac
                        exit 3
                        """
                    ),
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    json.loads(result.stdout),
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "updatedInput": {"command": expected},
                        }
                    },
                )

    def test_bypass_envs_disable_hook(self) -> None:
        for name in BYPASS_ENV:
            with self.subTest(env=name):
                result = self.run_hook(
                    "ls -la",
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                    env={name: "1"},
                )
                self.assert_no_output(result)

    def test_legacy_wrapper_bypass_envs_do_not_disable_hook(self) -> None:
        for name in LEGACY_WRAPPER_BYPASS_ENV:
            with self.subTest(env=name):
                result = self.run_hook(
                    "ls -la",
                    rtk_body="#!/usr/bin/env sh\nshift\nprintf 'rtk %s\\n' \"$*\"\n",
                    env={name: "1"},
                )
                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    json.loads(result.stdout),
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "updatedInput": {"command": "rtk ls -la"},
                        }
                    },
                )

    def test_failed_rewrite_is_ignored(self) -> None:
        result = self.run_hook(
            "ls -la",
            rtk_body=textwrap.dedent(
                """\
                #!/usr/bin/env sh
                printf 'partial rewrite\\n'
                exit 42
                """
            ),
        )

        self.assert_no_output(result)

    def test_undecodable_rewrite_output_is_ignored(self) -> None:
        result = self.run_hook(
            "ls -la",
            rtk_body="#!/usr/bin/env sh\nshift\nprintf '\\377'\n",
        )

        self.assert_no_output(result)

    def test_binaryish_rewrite_output_is_ignored(self) -> None:
        result = self.run_hook(
            "ls -la",
            rtk_body=(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "sys.stdout.buffer.write(b'rtk ls -la \\x00')\n"
            ),
        )

        self.assert_no_output(result)

    def test_long_rewrite_output_is_ignored(self) -> None:
        result = self.run_hook(
            "ls -la",
            rtk_body=(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "sys.stdout.write('x' * 17000)\n"
            ),
        )

        self.assert_no_output(result)

    def test_output_guard_truncates_long_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "session.jsonl"
            log.write_text(f"session_meta {'x' * 5000}\nshort\n", encoding="utf8")
            encoded = base64.b64encode(f"cat {shlex.quote(str(log))}".encode("utf8")).decode(
                "ascii"
            )

            result = subprocess.run(
                [
                    str(OUTPUT_GUARD),
                    "--b64",
                    encoded,
                    "--max-line-bytes",
                    "64",
                    "--max-output-bytes",
                    "512",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=5,
            )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("[rtk-output-guard: line truncated]", result.stdout)
        self.assertIn("short", result.stdout)
        self.assertLess(len(result.stdout), 512)


if __name__ == "__main__":
    unittest.main()
