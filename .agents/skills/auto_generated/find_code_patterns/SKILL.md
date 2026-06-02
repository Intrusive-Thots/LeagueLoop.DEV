# SKILL: find_code_patterns

## Description
Provides a platform-independent, Windows-safe text pattern matching utility written in pure Python. Use this to locate specific code patterns, TODO/FIXME comments, or variable references across the codebase when standard `grep` or `ripgrep` utilities are missing or failing in the execution environment.

## Usage
When `grep_search` fails with a missing executable error on Windows, run a simple Python script from command line or inside a temporary file.

### Powershell Inline Command (Windows-safe parsing)
```powershell
python -c "import os; [print(f'{r}\\{f}:{i+1}:{l.strip()}') for r, d, fs in os.walk('src') for f in fs if f.endswith('.py') for i, l in enumerate(open(os.path.join(r, f), encoding='utf-8')) if 'TODO' in l or 'FIXME' in l]"
```

### Pure Python Script Template
```python
import os

def find_patterns(search_dir, target_patterns, file_extension=".py"):
    found = False
    for root, dirs, files in os.walk(search_dir):
        for file in files:
            if file.endswith(file_extension):
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            for pattern in target_patterns:
                                if pattern in line:
                                    print(f"{path}:{line_num}: {line.strip()}")
                                    found = True
                except Exception as e:
                    pass
    return found
```

## Optimization Notes
- Standard Python `os.walk` and list comprehensions are used to scan files.
- Specifying `encoding='utf-8'` is critical on Windows systems where the system default encoding (e.g. cp1252) might fail on special characters in source files.
- The script ignores files that fail to read (such as binary or lock files) by wrapping the open in a try-except block.
