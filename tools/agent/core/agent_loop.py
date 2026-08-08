import time
import os
import logging
import json
import subprocess
from datetime import datetime
from pathlib import Path

from .llm_client import AgentLLMClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AutonomousAgent:
    def __init__(self):
        self.workspace_root = Path(os.getcwd()).resolve()
        self.memory_dir = self.workspace_root / ".agents" / "memory"
        self.logs_dir = self.workspace_root / ".agents" / "logs"
        self.task_queue_file = self.workspace_root / "TASK_QUEUE.md"
        self.implementation_plan_file = self.workspace_root / "IMPLEMENTATION_PLAN.md"

        self.memory = {}
        self.repo_index = {}
        self.knowledge_graph = {}
        self.implementation_plan = ""
        self.current_task = None
        self.llm = AgentLLMClient()

        # Ensure directories exist
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.memory_dir, exist_ok=True)

    def load_memory(self):
        logger.info("Loading memory...")
        memory_files = {
            'episodic.json': [],
            'failures.json': [],
            'loop_state.json': {},
            'optimizations.json': {},
            'procedural.json': {},
            'semantic.json': {}
        }
        for file, default_value in memory_files.items():
            path = self.memory_dir / file
            key = file.split('.')[0]
            if path.exists():
                with open(path, 'r') as f:
                    try:
                        self.memory[key] = json.load(f)
                    except json.JSONDecodeError:
                        logger.warning(f"Could not decode JSON from {path}")
                        self.memory[key] = default_value
            else:
                self.memory[key] = default_value

    def load_repository_index(self):
        logger.info("Loading repository index...")
        path = self.memory_dir / 'repo_index.json'
        if path.exists():
            with open(path, 'r') as f:
                try:
                    self.repo_index = json.load(f)
                except json.JSONDecodeError:
                    logger.warning("Could not decode repo_index.json")

    def load_knowledge_graph(self):
        logger.info("Loading knowledge graph...")
        # Assuming semantic.json holds knowledge graph or similar representation
        self.knowledge_graph = self.memory.get('semantic', {})

    def load_implementation_plan(self):
        logger.info("Loading implementation plan...")
        if self.implementation_plan_file.exists():
            with open(self.implementation_plan_file, 'r') as f:
                self.implementation_plan = f.read()

    def discover_next_task(self):
        logger.info("Discovering next task...")
        if self.task_queue_file.exists():
            with open(self.task_queue_file, 'r') as f:
                lines = f.readlines()

            for line in lines:
                if line.startswith('- [ ]'):
                    task_desc = line.strip()[6:]
                    self.current_task = task_desc
                    logger.info(f"Discovered task: {self.current_task}")
                    return self.current_task
        logger.info("No pending tasks found.")
        self.current_task = None
        return None

    def verify_dependencies(self):
        logger.info("Verifying dependencies...")
        req_file = self.workspace_root / "requirements.txt"
        if req_file.exists():
            logger.info("Checking requirements.txt...")
            result = subprocess.run(["pip", "check"], capture_output=True, cwd=self.workspace_root, text=True)
            if result.returncode != 0:
                logger.warning(f"Dependency issues detected: {result.stdout}")

    def _run_git_command(self, args, error_msg):
        result = subprocess.run(["git"] + args, capture_output=True, text=True, cwd=self.workspace_root)
        if result.returncode != 0:
            logger.error(f"{error_msg}: {result.stderr}")
            return False, result.stderr
        return True, result.stdout.strip()

    def _commit_state(self, message):
        """Helper to commit state files (memory, task queue) so working directory stays clean."""
        self._run_git_command(["add", str(self.memory_dir)], "Failed to stage memory dir")
        self._run_git_command(["add", str(self.task_queue_file)], "Failed to stage task queue")

        # Check if anything is staged to avoid empty commits
        success, output = self._run_git_command(["diff", "--cached", "--name-only"], "Failed to diff")
        if success and output:
            self._run_git_command(["commit", "-m", message], "Failed to commit state")

    def implement(self, task):
        logger.info(f"Implementing task: {task}...")

        # Get current branch to return to if things fail
        success, original_branch = self._run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], "Failed to get current branch")
        if not success:
            return False

        branch_name = f"auto-fix-{int(time.time())}"
        logger.info(f"Creating isolated branch: {branch_name}")

        success, _ = self._run_git_command(["checkout", "-b", branch_name], "Failed to create branch")
        if not success:
            return False

        # Use LLM to generate implementation
        context = {
            "repo_index": self.repo_index,
            "knowledge_graph": self.knowledge_graph
        }
        changes = self.llm.generate_code_implementation(task, context)

        if not changes:
            logger.warning("LLM failed to generate valid implementation changes. Marking task as failed.")
            self._run_git_command(["checkout", original_branch], "Failed to checkout original branch")
            self._run_git_command(["branch", "-D", branch_name], "Failed to delete failed branch")

            # Record failure in original branch state to persist
            self._record_failure(task, "LLM failed to generate changes")
            self._mark_task_failed()
            self._commit_state(f"Auto-Agent: Recorded failure for '{task[:50]}'")
            return False

        files_changed = []
        for filepath_str, content in changes.items():
            try:
                # Security: Ensure paths are strictly within the workspace
                target_path = (self.workspace_root / filepath_str).resolve()
                try:
                    rel_path = target_path.relative_to(self.workspace_root)
                except ValueError:
                    raise ValueError(f"Path traversal attempted: {filepath_str}")

                target_path.parent.mkdir(parents=True, exist_ok=True)
                with open(target_path, 'w') as f:
                    f.write(content)
                files_changed.append(str(rel_path))
            except Exception as e:
                logger.error(f"Failed to write changes to {filepath_str}: {e}")
                self._run_git_command(["reset", "--hard"], "Failed to reset")
                self._run_git_command(["checkout", original_branch], "Failed to checkout original branch")
                self._run_git_command(["branch", "-D", branch_name], "Failed to delete failed branch")
                self._record_failure(task, f"Failed to write changes: {e}")
                self._mark_task_failed()
                self._commit_state(f"Auto-Agent: Recorded failure for '{task[:50]}'")
                return False

        logger.info("Successfully applied code changes. Committing...")
        for f in files_changed:
            success, _ = self._run_git_command(["add", f], f"Failed to add {f}")
            if not success:
                 self._run_git_command(["reset", "--hard"], "Failed to reset")
                 self._run_git_command(["checkout", original_branch], "Failed to checkout original branch")
                 self._run_git_command(["branch", "-D", branch_name], "Failed to delete failed branch")
                 self._record_failure(task, "Git add failed")
                 self._mark_task_failed()
                 self._commit_state(f"Auto-Agent: Recorded failure for '{task[:50]}'")
                 return False

        commit_msg = f"Auto-implemented: {task[:50]}"
        success, _ = self._run_git_command(["commit", "-m", commit_msg], "Failed to commit changes")
        if not success:
             self._run_git_command(["reset", "--hard"], "Failed to reset")
             self._run_git_command(["checkout", original_branch], "Failed to checkout original branch")
             self._run_git_command(["branch", "-D", branch_name], "Failed to delete failed branch")
             self._record_failure(task, "Git commit failed")
             self._mark_task_failed()
             self._commit_state(f"Auto-Agent: Recorded failure for '{task[:50]}'")
             return False

        self.original_branch = original_branch
        self.temp_branch = branch_name
        return True

    def _record_failure(self, task, reason):
        failures = self.memory.get('failures', [])
        if isinstance(failures, list):
            failures.append({
                "task": task,
                "timestamp": datetime.now().isoformat(),
                "reason": reason
            })
            path = self.memory_dir / 'failures.json'
            with open(path, 'w') as f:
                json.dump(failures, f, indent=2)

    def _mark_task_failed(self):
        if self.current_task and self.task_queue_file.exists():
            with open(self.task_queue_file, 'r') as f:
                content = f.read()
            content = content.replace(f"- [ ] {self.current_task}", f"- [FAILED] {self.current_task}", 1)
            with open(self.task_queue_file, 'w') as f:
                f.write(content)

    def test(self):
        logger.info("Testing changes...")
        result = subprocess.run(["pytest"], capture_output=True, text=True, cwd=self.workspace_root)
        if result.returncode == 0:
            logger.info("Tests passed successfully.")
            return True
        else:
            logger.warning("Tests failed.")
            logger.error(result.stdout)
            self._run_git_command(["checkout", self.original_branch], "Failed to checkout original branch")

            # Now on original branch, record the failure
            self._record_failure(self.current_task, "Tests failed")
            self._mark_task_failed()
            self._commit_state(f"Auto-Agent: Recorded failure for '{self.current_task[:50]}'")

            self._run_git_command(["branch", "-D", self.temp_branch], "Failed to delete failed branch")
            return False

    def benchmark(self):
        logger.info("Benchmarking performance...")
        pass

    def learn(self):
        logger.info("Learning from execution...")
        if self.current_task:
            episodic = self.memory.get('episodic', [])
            if isinstance(episodic, list):
                episodic.append({
                    "task": self.current_task,
                    "timestamp": datetime.now().isoformat(),
                    "status": "completed"
                })
                path = self.memory_dir / 'episodic.json'
                with open(path, 'w') as f:
                    json.dump(episodic, f, indent=2)

    def update_plan(self):
        logger.info("Updating implementation plan...")
        if self.current_task and self.task_queue_file.exists():
            with open(self.task_queue_file, 'r') as f:
                content = f.read()
            content = content.replace(f"- [ ] {self.current_task}", f"- [x] {self.current_task}", 1)
            with open(self.task_queue_file, 'w') as f:
                f.write(content)

    def merge_and_cleanup(self):
         logger.info("Merging changes into original branch...")

         # Persist memory files before merge checkout
         self.update_plan()
         self.learn()

         success, _ = self._run_git_command(["checkout", self.original_branch], "Failed to checkout original branch")
         if not success:
              return False

         # Fast forward merge
         success, _ = self._run_git_command(["merge", "--ff-only", self.temp_branch], "Failed to merge changes")
         if success:
              self._run_git_command(["branch", "-d", self.temp_branch], "Failed to delete temp branch")
              # Commit the state files since we succeeded
              self._commit_state(f"Auto-Agent: Completed '{self.current_task[:50]}'")
              return True
         else:
             logger.error("Merge conflict or failure. Manual intervention required.")
             return False

    def schedule_next_run(self):
        logger.info("Scheduling next run in 1 hour...")
        time.sleep(3600)

    def run(self):
        while True:
            try:
                logger.info(f"--- Starting run at {datetime.now()} ---")
                self.load_memory()
                self.load_repository_index()
                self.load_knowledge_graph()
                self.load_implementation_plan()
                task = self.discover_next_task()
                if task:
                    self.verify_dependencies()
                    implementation_success = self.implement(task)
                    if implementation_success:
                        if self.test():
                            self.benchmark()
                            self.merge_and_cleanup()
                self.schedule_next_run()
            except Exception as e:
                logger.error(f"Error during run: {e}")
                time.sleep(60)

if __name__ == "__main__":
    agent = AutonomousAgent()
    logger.info("Agent script loaded successfully. Starting loop...")
    agent.run()
