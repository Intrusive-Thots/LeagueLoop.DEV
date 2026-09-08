"""
The container builds every service. Its calls must match their constructors.

`ApplicationContainer.create_account_manager()` passed `state_manager=` to an
`AccountManager.__init__` that did not accept it. Result:

    TypeError: AccountManager.__init__() got an unexpected keyword argument
    'state_manager'

Because `bootstrap()` catches per-service, this did not crash the app — it
degraded, exactly as designed. But the degraded thing was the entire accounts
subsystem: the account list, switching, and the Riot Client launcher that
hangs off it. The app came up looking fine and could not sign anyone in.

A signature mismatch is the cheapest possible bug to catch and it reached a
user, so it is checked here by inspection — no Windows, no services, no
network.
"""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def _module(path):
    return ast.parse(path.read_text(encoding="utf-8-sig"))


def _init_params(class_name, path):
    """The parameter names of one class's __init__, by source inspection."""
    for node in ast.walk(_module(path)):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    args = item.args
                    names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
                    return set(names), bool(args.kwarg)
    raise AssertionError("no %s.__init__ in %s" % (class_name, path.name))


def _keywords_passed_to(call_name, path):
    """Keyword names the container passes when constructing `call_name`."""
    passed = set()
    for node in ast.walk(_module(path)):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name != call_name:
            continue
        for keyword in node.keywords:
            if keyword.arg:
                passed.add(keyword.arg)
    return passed


class ContainerConstructorTests(unittest.TestCase):
    CONTAINER = SRC / "core" / "container.py"

    #: class name -> the module that defines it.
    BUILDS = {
        "AccountManager": SRC / "services" / "account_manager.py",
        "AutomationEngine": SRC / "services" / "automation.py",
        "ClientStateService": SRC / "services" / "client_state_service.py",
    }

    def test_every_keyword_the_container_passes_is_accepted(self):
        for class_name, module in self.BUILDS.items():
            if not module.exists():
                continue
            accepted, takes_kwargs = _init_params(class_name, module)
            if takes_kwargs:
                continue  # **kwargs accepts anything
            passed = _keywords_passed_to(class_name, self.CONTAINER)
            unexpected = passed - accepted
            self.assertEqual(
                unexpected, set(),
                "container passes %s to %s.__init__, which does not accept "
                "it — the whole service fails to start"
                % (sorted(unexpected), class_name),
            )

    def test_the_account_manager_takes_the_state_manager(self):
        """The specific mismatch that shipped."""
        accepted, _ = _init_params("AccountManager", self.BUILDS["AccountManager"])
        self.assertIn("state_manager", accepted)

    def test_the_container_does_not_import_modules_that_are_gone(self):
        """A container that imports a deleted module fails that service on
        every launch, quietly, because bootstrap catches per-service."""
        missing = []
        for node in ast.walk(_module(self.CONTAINER)):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if not node.module.startswith(("services.", "core.", "utils.", "ui.")):
                continue
            path = SRC.joinpath(*node.module.split("."))
            if not (path.with_suffix(".py").exists() or (path / "__init__.py").exists()):
                missing.append(node.module)
        self.assertEqual(missing, [], "container imports missing module(s): %s" % missing)


class ClientLaunchTests(unittest.TestCase):
    """`RiotClientServices.exe` started bare does not open anything.

    It initialises, finds no product to show, and exits — which looks exactly
    like the Launch Client button doing nothing, and was.
    """

    MAIN = SRC / "core" / "main.py"

    def test_league_is_launched_with_a_product_and_a_patchline(self):
        body = self.MAIN.read_text(encoding="utf-8-sig")
        self.assertIn("--launch-product=league_of_legends", body)
        self.assertIn("--launch-patchline=live", body)

    def test_the_riot_client_is_preferred_over_launching_league_directly(self):
        """Launching League directly makes the Riot Client start it anyway,
        but skips the account layer — so it is the fallback, not the default."""
        body = self.MAIN.read_text(encoding="utf-8-sig")
        riot = body.index("get_riot_executable_path()")
        league = body.index("get_league_executable_path()", riot)
        self.assertLess(riot, league)

    def test_a_missing_executable_says_where_it_looked(self):
        """"No executable found" on its own gives the user nothing to check."""
        body = self.MAIN.read_text(encoding="utf-8-sig")
        self.assertIn("Checked the standard install path and the registry", body)


if __name__ == "__main__":
    unittest.main()


class SuiteHygieneTests(unittest.TestCase):
    """No test may construct the whole application.

    `LeagueLoopApp()` starts the system tray, the connection and docking
    loops, and `keyboard.add_hotkey`. On Linux those
    fail quietly, so a test doing it looked harmless. On Windows they succeed,
    and `keyboard`'s listener runs on a non-daemon thread — so the interpreter
    could not exit and **pytest hung after the last test finished**, with no
    failing test to point at.

    A hang is the worst failure mode a suite can have: it reports nothing at
    all. This is the guard.
    """

    TESTS = ROOT / "tests"

    def _others(self):
        """Every test file but this one — it names the very things it bans."""
        return [
            path for path in sorted(self.TESTS.glob("test_*.py"))
            if path.name != Path(__file__).name
        ]

    def test_no_test_constructs_the_full_application(self):
        offenders = []
        for path in self._others():
            for number, line in enumerate(
                path.read_text(encoding="utf-8-sig").splitlines(), 1
            ):
                if "LeagueLoopApp(" in line and not line.lstrip().startswith("#"):
                    offenders.append("%s:%d" % (path.name, number))
        self.assertEqual(
            offenders, [],
            "these build the whole app, which leaves non-daemon threads "
            "running and hangs the suite on Windows: %s" % offenders,
        )

    def test_the_mobile_companion_stays_removed(self):
        """The mobile companion and its HTTP server were dropped deliberately.

        This used to be a narrower guard: a test could *name*
        `start_api_server` but not let one really run, because a live call
        bound port 8337 and left a non-daemon thread behind, hanging the
        suite on Windows. The feature is gone now, so the stronger and
        simpler guarantee is that none of it comes back — which makes the
        original hang impossible rather than merely unlikely.

        If the companion is ever revived, delete this test in the same
        change that revives it, and restore the port-binding guard with it.
        """
        banned = ("local_api", "start_api_server", "LeagueLoopMobile")

        offenders = []
        for directory in (ROOT / "src", self.TESTS):
            for path in sorted(directory.rglob("*.py")):
                if path.name == Path(__file__).name:
                    continue
                for number, line in enumerate(
                    path.read_text(encoding="utf-8-sig").splitlines(), 1
                ):
                    if line.lstrip().startswith("#"):
                        continue
                    for name in banned:
                        if name in line:
                            offenders.append(
                                "%s:%d (%s)" % (path.name, number, name)
                            )
        self.assertEqual(
            offenders, [],
            "the mobile companion was removed; these bring it back: %s"
            % offenders,
        )

    def test_the_mobile_app_directory_stays_removed(self):
        self.assertFalse(
            (ROOT / "LeagueLoopMobile").exists(),
            "LeagueLoopMobile/ was removed deliberately; it is back",
        )
