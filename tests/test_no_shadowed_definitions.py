import ast
import pathlib
import unittest


class TestNoShadowedDefinitions(unittest.TestCase):
    def test_no_shadowed_definitions_in_src(self):
        """Fails if any class or module defines the same name twice across src/.

        Excludes properties (getter/setter/deleter), @overload stubs, and
        definitions inside conditional blocks (if/try).
        """
        src_dir = pathlib.Path(__file__).resolve().parent.parent / "src"
        duplicates = []

        for py_file in src_dir.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8-sig")
            try:
                tree = ast.parse(text, filename=str(py_file))
            except SyntaxError:
                continue

            # Process module level and class levels
            containers = [(f"{py_file.name}:module", tree.body)]

            # Find classes in tree
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    containers.append((f"{py_file.name}:{node.name}", node.body))

            for container_name, statements in containers:
                seen_names = {}
                for stmt in statements:
                    # Ignore statements inside if/try blocks (which are in separate sub-bodies)
                    # We only inspect direct child statements of module or ClassDef
                    names = []

                    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Check decorators for @overload or @*.setter / @*.deleter
                        is_excluded = False
                        for dec in stmt.decorator_list:
                            dec_name = ""
                            if isinstance(dec, ast.Name):
                                dec_name = dec.id
                            elif isinstance(dec, ast.Attribute):
                                dec_name = dec.attr
                            if dec_name in ("overload", "setter", "deleter"):
                                is_excluded = True
                                break
                        if not is_excluded:
                            names.append(stmt.name)

                    elif isinstance(stmt, ast.ClassDef):
                        names.append(stmt.name)

                    elif isinstance(stmt, ast.Assign):
                        for target in stmt.targets:
                            if isinstance(target, ast.Name):
                                names.append(target.id)

                    elif isinstance(stmt, ast.AnnAssign):
                        if isinstance(stmt.target, ast.Name):
                            names.append(stmt.target.id)

                    for name in names:
                        if name in seen_names:
                            first_line = seen_names[name]
                            duplicates.append(
                                f"{container_name} defines '{name}' twice (lines {first_line} and {stmt.lineno})"
                            )
                        else:
                            seen_names[name] = stmt.lineno

        self.assertEqual(duplicates, [], "Found shadowed duplicate definitions in src:\n" + "\n".join(duplicates))


if __name__ == "__main__":
    unittest.main()
