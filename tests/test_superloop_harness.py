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
        command = [sys.executable, str(HARNESS), *args]
        merged_env = os.environ.copy()
        merged_env["SUPERLOOP_STATE_HOME"] = str(self.state_home)
        if env:
            merged_env.update(env)

        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            env=merged_env,
        )
        return json.loads(result.stdout)

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


if __name__ == "__main__":
    unittest.main()
