import json
import logging
import os
import subprocess
from logging import INFO, Logger, DEBUG, ERROR
from traceback import format_exc

from swebench.constants import KEY_INSTANCE_ID, PatchType, APPLY_PATCH_FAIL, APPLY_PATCH_PASS, TESTS_FAILED, \
    TESTS_PASSED, TESTS_TIMEOUT, TESTS_ERROR, KEY_MODEL

base_dir = "/home/swe-bench"

logger_taskenv = logging.getLogger("taskenv")


class LogWrapper:
    def __init__(
        self,
        log_file: str,
        logger: Logger = None,
        prefix: str = None,
    ):
        self.log_file = log_file
        self.logger = logger
        self.prefix = prefix

    def write(
            self,
            message: str,
            mode: str = "a",
            level: int = INFO):
        with open(self.log_file, mode) as f:
            log = f"{self.prefix} {message} \n" if self.prefix \
                is not None else f"{message} \n"
            f.write(log)
        if self.logger is not None:
            self.logger.log(level, message)


class ExecWrapper:
    def __init__(
        self,
        subprocess_args: dict = None,
        logger: LogWrapper = None,
    ):
        self.logger = logger
        if subprocess_args is None:
            self.subprocess_args = {}
        else:
            self.subprocess_args = subprocess_args

    def __call__(self, cmd, raise_error=True, **kwargs):
        try:
            if isinstance(cmd, list):
                self.logger.write(f"Command: {' '.join(cmd)}", level=DEBUG)
            else:
                self.logger.write(f"Command: {cmd}", level=DEBUG)
            combined_args = {**self.subprocess_args, **kwargs}
            self.logger.write(f"Subprocess args: {json.dumps(combined_args)}", level=DEBUG)
            output = subprocess.run(cmd, **combined_args)
            self.logger.write(f"Std. Output:\n{output.stdout}", level=DEBUG)
            if output.stderr:
                self.logger.write(f"Std. Error:\n{output.stderr}", level=DEBUG)
            self.logger.write(f"Return Code: {output.returncode}", level=DEBUG)
            return output
        except subprocess.CalledProcessError as e:
            if raise_error and self.logger is not None:
                self.logger.write(f"Error: {e}", level=ERROR)
                self.logger.write(f"Error stdout: {e.stdout}", level=ERROR)
                if e.stderr:
                    self.logger.write(f"Error stderr: {e.stderr}", level=ERROR)
                self.logger.write(f"Error traceback: {format_exc()}", level=ERROR)
                raise e


class TaskEnvContextManager:

    def __init__(
        self,
        task_instance: dict,
        testbed_name: str,
        testbed: str,
        log_dir: str,
        log_suffix: str = None,
        timeout: int = None,
        is_eval: bool = True,
    ):
        self.instance_id = task_instance[KEY_INSTANCE_ID]
        self.instance = task_instance
        self.testbed_name = testbed_name
        self.testbed = testbed
        self.cwd = os.getcwd()
        self.is_eval = is_eval

        model = task_instance[KEY_MODEL]
        self.cmd_conda_run = f"conda run -n {testbed_name}"
        self.timeout = timeout

        log_file_name = f"{self.instance_id}.{model}.eval.log"

        if log_suffix:
            log_file_name = f"{self.instance_id}.{model}.{log_suffix}.eval.log"

        self.log_file = os.path.join(log_dir, log_file_name)
        self.log = LogWrapper(
            self.log_file, logger=logger_taskenv,
            prefix=f"[{testbed_name}] [{self.instance_id}]")

        self.exec = ExecWrapper(
            subprocess_args={
                "cwd": self.testbed,
                "check": True,
                "shell": False,
                "capture_output": False,
                "text": True,
                "stdout": subprocess.PIPE,
                "stderr": subprocess.STDOUT,
            },
            logger=self.log,
        )

    def __enter__(self):
        """
        Enter task environment, set up log file
        """
        os.chdir(self.testbed)
        enter_msg = (
            f"Task Metadata:\n\t- "
            f"Instance ID: {self.instance[KEY_INSTANCE_ID]}\n\t- "
            f"Testbed: {self.testbed_name}\n\t- "
        )
        if self.is_eval:
            enter_msg += f"\n\t- Evaluation Model: {self.instance[KEY_MODEL]}"
        self.log.write(enter_msg, mode="w")

        output = self.exec(["git", "status", "--porcelain"])
        if output.stdout:
            self.exec(["git", "stash", "push", "-m", "Temporarily stashed changes"])
            stash_used = True
        else:
            stash_used = False

        self.exec(
            f"git -c advice.detachedHead=false checkout {self.instance['base_commit']}".split(
                " "
            )
        )
        if stash_used:
            self.exec(["git", "stash", "pop"])

        return self

    def apply_patch(
        self, patch: str, patch_type: PatchType = "", revert: bool = False
    ) -> bool:
        """
        Apply patch to task environment

        Args:
            patch (str): Plaintext of patch to apply
            patch_type (str): Type of patch (e.g. "eval", "test")
        Returns:
            bool: True if patch applied successfully, False otherwise
        """
        # If patch is `None`, indicate in log and skip
        if patch is None:
            self.log.write(f"Patch is `None` ({patch_type})")
            with open(self.log_file, "a") as f:
                f.write(f"{APPLY_PATCH_FAIL}; Prediction patch is `None`")
            return False

        # Write patch to temporary patch file in parent directory
        patch_path = os.path.join(
            os.path.dirname(self.testbed.rstrip("/")),
            f"temp_{self.instance_id}_{patch_type}.patch",
        )

        with open(patch_path, "w") as f:
            f.write(patch)

        # Restore test files before applying if patch_type is 'test'
        if patch_type == PatchType.PATCH_TEST.value:
            for test in self.instance["test_directives"]:
                if os.path.exists(test):
                    self.exec(f"git restore {test}".split(" "))

        # Apply patch to testbed directory
        apply_cmd = (
            f"git apply -v -R {patch_path}" if revert else f"git apply -v {patch_path}"
        )
        out_patch = self.exec(apply_cmd.split(" "), raise_error=False, check=False)
        # TODO os.remove(patch_path)

        log_cmd = "Revert" if revert else "Apply"
        if out_patch.returncode != 0:
            # Patch apply failed
            self.log.write(f"{log_cmd} patch failed ({patch_type})", level=ERROR)
            with open(self.log_file, "a") as f:
                f.write(f"{APPLY_PATCH_FAIL}; ({patch_type})\nOutput:\n")
                f.write(out_patch.stdout)
                if out_patch.stderr:
                    f.write(out_patch.stderr)
            return False

        # Patch apply succeeded
        self.log.write(f"{log_cmd} patch successful ({patch_type})")
        with open(self.log_file, "a") as f:
            f.write(f"{APPLY_PATCH_PASS} ({patch_type})\n")
        return True

    def run_tests_task(self, instance: dict):
        """
        Run tests for task instance

        Args:
            instance (dict): Task instance
        Returns:
            bool: True if test script ran successfully, False otherwise
        """
        try:
            # Run test command for task instance
            test_cmd = f"{self.cmd_conda_run} {instance['test_cmd']}"
            with open(self.log_file, "a") as f:
                f.write(f"Test Script: {test_cmd};\n")

            out_test = self.exec(
                test_cmd.split(), shell=False, timeout=self.timeout, check=False
            )

            # Write pass/fail status to log file
            with open(self.log_file, "a") as f:
                if out_test.returncode != 0:
                    f.write(f"\n{TESTS_FAILED}\n")
                else:
                    f.write(f"\n{TESTS_PASSED}\n")

            self.log.write(f"Test script run successful")
            return True
        except subprocess.TimeoutExpired:
            # Test command run timed out
            self.log.write("Test script run timed out", level=ERROR)
            with open(self.log_file, "a") as f:
                f.write(f"{TESTS_TIMEOUT} after {self.timeout} seconds\n")
            return False
        except Exception as e:
            # Test command run failed
            self.log.write(f"Test script run failed", level=ERROR)
            with open(self.log_file, "a") as f:
                f.write(f"{TESTS_ERROR}: {e}")
            return False

    def __exit__(self, exc_type, exc_value, exc_traceback):
        os.chdir(self.cwd)