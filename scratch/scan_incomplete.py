import os
import sys
import ast
import re

results = {
    'todos': [],
    'not_implemented': [],
    'empty_stubs': [],
    'syntax_errors': [],
    'empty_files': [],
    'empty_dirs': []
}

for root, dirs, files in os.walk('.'):
    if any(p in root for p in ['.git', '.venv', 'node_modules', '__pycache__', '.pytest_cache', 'scratch']):
        continue
    if not dirs and not files:
        results['empty_dirs'].append(root)
    for f in files:
        path = os.path.join(root, f)
        if os.path.getsize(path) == 0:
            results['empty_files'].append(path)
        if f.endswith('.py'):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as fp:
                    content = fp.read()
                    lines = content.splitlines()
                
                for idx, line in enumerate(lines, 1):
                    if re.search(r'\b(TODO|FIXME|XXX|HACK)\b', line, re.I):
                        results['todos'].append((path, idx, line.strip()))
                    if 'NotImplemented' in line:
                        results['not_implemented'].append((path, idx, line.strip()))

                tree = ast.parse(content, filename=path)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if len(node.body) == 1 and isinstance(node.body[0], (ast.Pass, ast.Expr)):
                            if isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and node.body[0].value.value is ...:
                                results['empty_stubs'].append((path, node.lineno, node.name))
                            elif isinstance(node.body[0], ast.Pass):
                                results['empty_stubs'].append((path, node.lineno, node.name))

            except SyntaxError as e:
                results['syntax_errors'].append((path, str(e)))

print('=== SCAN RESULTS ===')
print(f"Empty Dirs: {len(results['empty_dirs'])}")
for d in results['empty_dirs']:
    print(f"  [DIR] {d}")

print(f"\nEmpty Files: {len(results['empty_files'])}")
for f in results['empty_files']:
    print(f"  [FILE] {f}")

print(f"\nSyntax Errors: {len(results['syntax_errors'])}")
for s in results['syntax_errors']:
    print(f"  [SYNTAX] {s}")

print(f"\nTODO / FIXME comments: {len(results['todos'])}")
for t in results['todos']:
    print(f"  [TODO] {t[0]}:{t[1]} -> {t[2]}")

print(f"\nNotImplemented occurrences: {len(results['not_implemented'])}")
for n in results['not_implemented']:
    print(f"  [NOT_IMPLEMENTED] {n[0]}:{n[1]} -> {n[2]}")

print(f"\nEmpty stubs (pass / ... only): {len(results['empty_stubs'])}")
for s in results['empty_stubs']:
    print(f"  [STUB] {s[0]}:{s[1]} -> {s[2]}()")
