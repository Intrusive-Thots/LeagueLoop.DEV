import py_compile
import os
import sys

errors = []
count = 0
for root, _, files in os.walk("src"):
    for fn in files:
        if fn.endswith(".py"):
            path = os.path.join(root, fn)
            count += 1
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as e:
                errors.append(str(e))

if errors:
    print(f"FAILED: {len(errors)} of {count} files have errors:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print(f"All {count} Python files compile OK")
