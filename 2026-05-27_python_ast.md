# Python AST Parser - Synthesized Learning Data

## Topic
Build a Python AST (Abstract Syntax Tree) parser that analyzes a Python source file and reports:
- All function definitions (name, line number, arguments)
- All class definitions (name, line number)
- All import statements

## Requirements
- Use Python's built-in `ast` module
- Accept a filename as a command-line argument
- Print a structured report to stdout
- Handle file-not-found and syntax errors gracefully

## Example Output
```
=== AST Report: example.py ===
Imports: os, sys, pathlib.Path
Classes: MyClass (line 10)
Functions: __init__ (line 11, args: self), run (line 15, args: self, data)
```
