import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "scripts" / "superloop_harness.py"


class SuperloopHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        self.root = Path(tempdir.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.state_home = self.root / "state"

    def run_harness(self, *args: str, env: dict[str, str] | None = None) -> dict:
        result = self.run_harness_process(*args, env=env, check=True)
        return json.loads(result.stdout)

    def run_harness_process(
        self,
        *args: str,
        env: dict[str, str] | None = None,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(HARNESS), *args]
        merged_env = os.environ.copy()
        merged_env["SUPERLOOP_STATE_HOME"] = str(self.state_home)
        if env:
            merged_env.update(env)

        return subprocess.run(
            command,
            check=check,
            capture_output=True,
            text=True,
            env=merged_env,
        )

    def test_init_archives_old_run_when_starting_new_mission(self) -> None:
        first = self.run_harness(
            "init",
            "--workspace",
            str(self.workspace),
            "--goal",
            "Mission A",
            "--workstream",
            "agent harness",
            "--max-rounds",
            "3",
        )
        first_run_id = first["state"]["run_id"]

        self.run_harness(
            "record",
            "--workspace",
            str(self.workspace),
            "--hypothesis",
            "The first mission still needs work",
            "--change",
            "Saved a next-round handoff",
            "--round-gate",
            "One round is captured safely",
            "--round-gate-result",
            "hard-pass",
            "--gate-status",
            "gate-in-progress",
            "--next-round",
            "Keep tightening the first mission",
            "--remaining-gap",
            "Another round is still needed",
        )

        second = self.run_harness(
            "init",
            "--workspace",
            str(self.workspace),
            "--goal",
            "Mission B",
            "--workstream",
            "agent harness",
        )

        self.assertEqual(second["status_card"]["classification"], "new-mission")
        self.assertNotEqual(second["state"]["run_id"], first_run_id)
        self.assertEqual(second["state"]["parent_run_id"], first_run_id)
        self.assertEqual(second["budget_status"]["rounds_used"], 0)
        archived_previous_run = second["archived_previous_run"]
        self.assertEqual(archived_previous_run["run_id"], first_run_id)

        archived_state = json.loads(Path(archived_previous_run["archive_path"]).read_text())
        self.assertEqual(archived_state["contract"]["goal"], "Mission A")
        self.assertEqual(len(archived_state["rounds"]), 1)

    def test_continue_existing_requires_explicit_flag(self) -> None:
        first = self.run_harness(
            "init",
            "--workspace",
            str(self.workspace),
            "--goal",
            "Mission A",
            "--workstream",
            "agent harness",
            "--current-gate",
            "Initial gate",
        )
        first_run_id = first["state"]["run_id"]

        continued = self.run_harness(
            "init",
            "--workspace",
            str(self.workspace),
            "--goal",
            "Mission A refined",
            "--workstream",
            "agent harness",
            "--current-gate",
            "Updated gate",
            "--continue-existing",
        )

        self.assertEqual(continued["status_card"]["classification"], "continue-existing")
        self.assertEqual(continued["state"]["run_id"], first_run_id)
        self.assertEqual(continued["state"]["contract"]["goal"], "Mission A refined")
        self.assertEqual(continued["state"]["contract"]["current_gate"], "Updated gate")

    def test_resume_surfaces_new_mission_hint(self) -> None:
        self.run_harness(
            "init",
            "--workspace",
            str(self.workspace),
            "--goal",
            "Mission A",
            "--workstream",
            "agent harness",
        )

        resumed = self.run_harness("resume", "--workspace", str(self.workspace))

        self.assertIn("freshness", resumed)
        self.assertTrue(
            any("--continue-existing" in action for action in resumed["next_actions"]),
            resumed["next_actions"],
        )

    def test_preflight_classifies_required_and_optional_env(self) -> None:
        error_payload = self.run_harness(
            "preflight",
            "--workspace",
            str(self.workspace),
            "--stage",
            "deploy",
            "--require-env",
            "REQUIRED_ALPHA",
            "--optional-env",
            "OPTIONAL_BETA",
        )
        self.assertEqual(error_payload["status"], "error")
        self.assertEqual(
            error_payload["status_card"]["classification"],
            "config-missing-required",
        )
        self.assertEqual(
            error_payload["preflight"]["missing_required_env"],
            ["REQUIRED_ALPHA"],
        )

        warning_payload = self.run_harness(
            "preflight",
            "--workspace",
            str(self.workspace),
            "--stage",
            "deploy",
            "--require-env",
            "REQUIRED_ALPHA",
            "--optional-env",
            "OPTIONAL_BETA",
            env={"REQUIRED_ALPHA": "set"},
        )
        self.assertEqual(warning_payload["status"], "warning")
        self.assertEqual(
            warning_payload["status_card"]["classification"],
            "config-missing-optional",
        )
        self.assertEqual(
            warning_payload["preflight"]["missing_optional_env"],
            ["OPTIONAL_BETA"],
        )

        success_payload = self.run_harness(
            "preflight",
            "--workspace",
            str(self.workspace),
            "--stage",
            "deploy",
            "--require-env",
            "REQUIRED_ALPHA",
            "--optional-env",
            "OPTIONAL_BETA",
            env={"REQUIRED_ALPHA": "set", "OPTIONAL_BETA": "set"},
        )
        self.assertEqual(success_payload["status"], "success")
        self.assertEqual(success_payload["status_card"]["classification"], "ready")

    def test_status_card_renders_migration_and_github_dry_run(self) -> None:
        payload = self.run_harness(
            "status-card",
            "--workspace",
            str(self.workspace),
            "--stage",
            "deploy",
            "--require-env",
            "SUPERLOOP_TEST_REQUIRED_TOKEN",
            "--platform",
            "cloudflare",
            "--migration-from",
            "vercel",
            "--migration-to",
            "cloudflare",
            "--disabled-platform",
            "vercel",
            "--locale",
            "zh",
            "--github-repo",
            "waterme7on/superloop",
            "--github-issue",
            "4",
            "--dry-run",
        )

        self.assertEqual(payload["status"], "success")
        self.assertEqual(
            payload["status_card"]["classification"],
            "config-missing-required",
        )
        self.assertEqual(payload["status_card"]["locale"], "zh")
        self.assertEqual(payload["status_card"]["platform"]["current"], "cloudflare")
        self.assertEqual(payload["status_card"]["platform"]["migration_from"], "vercel")
        self.assertEqual(payload["github_sync"][0]["status"], "dry-run")
        self.assertIn("迁移模式", payload["status_card_markdown"])

    def test_status_card_uses_github_env_defaults(self) -> None:
        payload = self.run_harness(
            "status-card",
            "--workspace",
            str(self.workspace),
            "--stage",
            "deploy",
            "--classification",
            "external-service",
            "--dry-run",
            env={
                "GITHUB_REPOSITORY": "waterme7on/superloop",
                "SUPERLOOP_GITHUB_ISSUE": "4",
            },
        )

        self.assertEqual(payload["github_sync"][0]["number"], 4)
        self.assertEqual(payload["github_sync"][0]["target"], "issue")

    def test_status_card_classifies_failure_text_with_stable_codes(self) -> None:
        payload = self.run_harness(
            "status-card",
            "--workspace",
            str(self.workspace),
            "--stage",
            "build",
            "--failure-text",
            "GitHub Actions workflow YAML syntax is invalid",
        )

        self.assertEqual(payload["status_card"]["classification"], "workflow-syntax")

    def test_context_renders_next_round_runtime_context(self) -> None:
        self.run_harness(
            "init",
            "--workspace",
            str(self.workspace),
            "--goal",
            "Make the agent harness operator-ready",
            "--workstream",
            "agent harness",
            "--max-rounds",
            "3",
        )
        self.run_harness(
            "record",
            "--workspace",
            str(self.workspace),
            "--hypothesis",
            "A first focused round will expose the next gap",
            "--change",
            "Captured the initial gate and next round",
            "--round-gate",
            "The initial state is recorded",
            "--round-gate-result",
            "hard-pass",
            "--gate-status",
            "gate-in-progress",
            "--next-round",
            "Render runtime context before the next round",
            "--remaining-gap",
            "Next round context is not yet generated",
        )

        payload = self.run_harness(
            "context",
            "--workspace",
            str(self.workspace),
            "--format",
            "json",
        )

        context = payload["context"]
        self.assertEqual(context["contract"]["goal"], "Make the agent harness operator-ready")
        self.assertEqual(context["next_round"], "Render runtime context before the next round")
        self.assertEqual(context["budget_status"]["rounds_used"], 1)
        self.assertTrue(context["completion_audit_checklist"])
        self.assertTrue(any("do not shrink" in directive for directive in context["directives"]))

        markdown = self.run_harness_process(
            "context",
            "--workspace",
            str(self.workspace),
            check=True,
        ).stdout
        self.assertIn("## Completion Audit", markdown)
        self.assertIn("Do not claim mission completion", markdown)

    def test_start_round_persists_in_flight_state_and_record_uses_it(self) -> None:
        self.run_harness(
            "init",
            "--workspace",
            str(self.workspace),
            "--goal",
            "Make the harness resumable",
            "--workstream",
            "agent harness",
        )

        started = self.run_harness(
            "start-round",
            "--workspace",
            str(self.workspace),
            "--hypothesis",
            "An in-flight marker makes interrupted work recoverable",
            "--change",
            "Persist active round metadata before execution",
            "--round-gate",
            "Resume shows the active round",
        )
        self.assertEqual(started["active_round"]["round_number"], 1)

        resumed = self.run_harness("resume", "--workspace", str(self.workspace))
        self.assertEqual(
            resumed["state"]["active_round"]["hypothesis"],
            "An in-flight marker makes interrupted work recoverable",
        )

        recorded = self.run_harness(
            "record",
            "--workspace",
            str(self.workspace),
            "--round-gate-result",
            "hard-pass",
            "--gate-status",
            "gate-in-progress",
            "--next-round",
            "Use context before the next implementation round",
            "--remaining-gap",
            "Completion evidence is not wired yet",
        )

        self.assertIsNone(recorded["state"]["active_round"])
        report = self.run_harness(
            "report",
            "--workspace",
            str(self.workspace),
            "--format",
            "json",
        )
        first_round = report["state"]["rounds"][0]
        self.assertEqual(
            first_round["round_gate"],
            "Resume shows the active round",
        )

    def test_mission_complete_requires_completion_evidence(self) -> None:
        self.run_harness(
            "init",
            "--workspace",
            str(self.workspace),
            "--goal",
            "Finish the mission with proof",
            "--workstream",
            "agent harness",
        )

        failed = self.run_harness_process(
            "record",
            "--workspace",
            str(self.workspace),
            "--hypothesis",
            "The mission is complete",
            "--change",
            "Verified all requirements",
            "--round-gate",
            "All checks pass",
            "--round-gate-result",
            "hard-pass",
            "--gate-status",
            "gate-complete",
            "--mission-complete",
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(
            json.loads(failed.stdout)["summary"],
            "Mission completion requires explicit completion evidence.",
        )

        completed = self.run_harness(
            "record",
            "--workspace",
            str(self.workspace),
            "--hypothesis",
            "The mission is complete",
            "--change",
            "Verified all requirements",
            "--round-gate",
            "All checks pass",
            "--round-gate-result",
            "hard-pass",
            "--gate-status",
            "gate-complete",
            "--mission-complete",
            "--completion-evidence",
            "unit tests passed",
            "--completion-evidence",
            "runtime context includes completion audit",
        )

        self.assertEqual(completed["verdict"], "stop")
        self.assertEqual(completed["state"]["stop_reason"], "mission-complete")
        self.assertEqual(
            completed["state"]["completion_evidence"],
            ["unit tests passed", "runtime context includes completion audit"],
        )

    def test_no_gap_sentinel_clears_previous_remaining_gaps(self) -> None:
        self.run_harness(
            "init",
            "--workspace",
            str(self.workspace),
            "--goal",
            "Close existing gaps with proof",
            "--workstream",
            "agent harness",
        )
        self.run_harness(
            "record",
            "--workspace",
            str(self.workspace),
            "--hypothesis",
            "A first round leaves one gap",
            "--change",
            "Captured the gap",
            "--round-gate",
            "Gap ledger exists",
            "--round-gate-result",
            "soft-pass",
            "--gate-status",
            "gate-in-progress",
            "--next-round",
            "Close the final proof gap",
            "--remaining-gap",
            "final proof is missing",
        )

        completed = self.run_harness(
            "record",
            "--workspace",
            str(self.workspace),
            "--hypothesis",
            "The final proof gap is closed",
            "--change",
            "Verified the completion proof",
            "--round-gate",
            "No gaps remain",
            "--round-gate-result",
            "hard-pass",
            "--gate-status",
            "gate-complete",
            "--remaining-gap",
            "none",
            "--mission-complete",
            "--completion-evidence",
            "final proof command passed",
        )

        self.assertEqual(completed["verdict"], "stop")
        self.assertEqual(completed["state"]["remaining_gap_ledger"], [])

    def test_cli_module_is_importable(self) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import superloop.cli as cli; print(cli.repo_root())",
            ],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

        self.assertEqual(Path(result.stdout.strip()), REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
