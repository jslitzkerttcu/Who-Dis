"""Phase 9 Task 3 helper — AST cross-check for `editor` role usage.

Authoritative scan that does not depend on regex tricks. Prints `path:line:reason`
for every site that references the `editor` role token (decorator, comparison, or
`User.ROLE_EDITOR` attribute access). Excludes the role_resolver and auth modules
— those legitimately reference the token in the safety shim.
"""
import ast, pathlib, sys

EXCLUDE = {"role_resolver.py", "auth.py"}

for path in pathlib.Path("app").rglob("*.py"):
    if path.name in EXCLUDE:
        continue
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        # require_role("editor") / require_role('editor')
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "require_role":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and arg.value == "editor":
                    print(f"{path}:{node.lineno}:AST require_role(editor)")
        # role == "editor" / role != "editor"
        if isinstance(node, ast.Compare):
            for cmp in [node.left, *node.comparators]:
                if isinstance(cmp, ast.Constant) and cmp.value == "editor":
                    print(f"{path}:{node.lineno}:AST compare-with-editor")
        # User.ROLE_EDITOR attribute access
        if isinstance(node, ast.Attribute) and node.attr == "ROLE_EDITOR":
            print(f"{path}:{node.lineno}:AST ROLE_EDITOR attribute")
