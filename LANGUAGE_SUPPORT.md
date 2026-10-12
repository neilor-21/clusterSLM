# Multi-language parser support (current stage)

## Implemented

- Python: parsed with Python's built-in `ast` module.
- JavaScript / JSX: parsed with Tree-sitter when `tree-sitter-language-pack` is installed.
- TypeScript / TSX: parsed with Tree-sitter when `tree-sitter-language-pack` is installed.
- Other recognized extensions are reported as detected-only until their adapters are implemented.

The JavaScript/TypeScript adapter extracts syntax-level class names, function/method names, import module strings, and call expressions into the shared `FileInfo` model. This is not full name resolution, type analysis, taint analysis, or proof of vulnerability. In particular, imports and calls are currently syntactic references; cross-language HTTP and SQL data-flow relationships remain future work.

## Install / test

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

If `tree-sitter-language-pack` cannot be installed because the machine is offline, Python parsing continues to work. JavaScript/TypeScript files are detected and reported as not analyzed; they are not silently claimed as parsed.

## Scan a repository

```powershell
python main.py C:\path\to\repository
```

The CLI reports detected languages and which files were parsed. The existing analysis worker is still a mock unless an external findings file is supplied with `--findings PATH`.
