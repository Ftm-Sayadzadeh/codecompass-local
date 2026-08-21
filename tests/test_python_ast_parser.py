from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from codecompass.parser import PythonASTParser
from codecompass.scanner import SourceFile


def source_file(path: Path, relative_path: str = "sample.py") -> SourceFile:
    data = path.read_bytes()
    stat = path.stat()
    return SourceFile(
        relative_path=relative_path,
        absolute_path=path.resolve(),
        size_bytes=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def write_source(tmp_path: Path, content: str, name: str = "sample.py") -> SourceFile:
    path = tmp_path / name
    path.write_bytes(content.encode("utf-8"))
    return source_file(path, name)


def test_simple_function_metadata(tmp_path: Path) -> None:
    source = write_source(
        tmp_path,
        '''
def greet(name: str, times=1, *args, loud=False, **kwargs) -> str:
    """Return a greeting."""
    return name
'''.lstrip(),
    )

    result = PythonASTParser().parse_file(source)

    assert result.errors == ()
    symbol = result.symbols[0]
    assert symbol.kind == "function"
    assert symbol.name == "greet"
    assert symbol.qualified_name == "greet"
    assert symbol.parent_qualified_name is None
    assert symbol.parameters == ("name", "times", "*args", "loud", "**kwargs")
    assert symbol.returns == "str"
    assert symbol.docstring == "Return a greeting."
    assert symbol.start_line == 1
    assert symbol.end_line == 3
    assert symbol.is_async is False


def test_async_function_uses_function_kind_and_async_flag(tmp_path: Path) -> None:
    source = write_source(
        tmp_path,
        """
async def fetch(url):
    return url
""".lstrip(),
    )

    symbol = PythonASTParser().parse_file(source).symbols[0]

    assert symbol.kind == "function"
    assert symbol.is_async is True


def test_class_and_method_metadata(tmp_path: Path) -> None:
    source = write_source(
        tmp_path,
        """
@entity
class UserService(BaseService, Mixin):
    \"\"\"User operations.\"\"\"

    @route("/users")
    def get_user(self, user_id: int):
        \"\"\"Load one user.\"\"\"
        return user_id

    async def save(self):
        return None
""".lstrip(),
    )

    symbols = PythonASTParser().parse_file(source).symbols

    assert [(symbol.kind, symbol.qualified_name, symbol.is_async) for symbol in symbols] == [
        ("class", "UserService", False),
        ("method", "UserService.get_user", False),
        ("method", "UserService.save", True),
    ]
    class_symbol = symbols[0]
    assert class_symbol.bases == ("BaseService", "Mixin")
    assert class_symbol.decorators == ("entity",)
    assert class_symbol.docstring == "User operations."
    assert class_symbol.start_line == 2
    assert class_symbol.end_line == 11

    method = symbols[1]
    assert method.parent_qualified_name == "UserService"
    assert method.parameters == ("self", "user_id")
    assert method.decorators == ("route('/users')",)
    assert method.docstring == "Load one user."
    assert method.start_line == 6
    assert method.end_line == 8


def test_imports_are_extracted_without_resolution(tmp_path: Path) -> None:
    source = write_source(
        tmp_path,
        """
import os
import pathlib as pl
from collections import defaultdict as dd
from .local import thing
""".lstrip(),
    )

    imports = PythonASTParser().parse_file(source).imports

    assert [(item.kind, item.module, item.name, item.alias, item.line) for item in imports] == [
        ("import", None, "os", None, 1),
        ("import", None, "pathlib", "pl", 2),
        ("from_import", "collections", "defaultdict", "dd", 3),
        ("from_import", ".local", "thing", None, 4),
    ]


def test_nested_symbols_naturally_get_qualified_names(tmp_path: Path) -> None:
    source = write_source(
        tmp_path,
        """
class Outer:
    class Inner:
        def method(self):
            def helper():
                return 1
            return helper()
""".lstrip(),
    )

    symbols = PythonASTParser().parse_file(source).symbols

    assert [(symbol.kind, symbol.qualified_name, symbol.parent_qualified_name) for symbol in symbols] == [
        ("class", "Outer", None),
        ("class", "Outer.Inner", "Outer"),
        ("method", "Outer.Inner.method", "Outer.Inner"),
        ("function", "Outer.Inner.method.helper", "Outer.Inner.method"),
    ]


def test_multiple_symbols_keep_source_order(tmp_path: Path) -> None:
    source = write_source(
        tmp_path,
        """
def b():
    pass

class A:
    pass

def c():
    pass
""".lstrip(),
    )

    assert [symbol.qualified_name for symbol in PythonASTParser().parse_file(source).symbols] == ["b", "A", "c"]


def test_empty_file_has_no_symbols_imports_or_errors(tmp_path: Path) -> None:
    source = write_source(tmp_path, "")

    result = PythonASTParser().parse_file(source)

    assert result.imports == ()
    assert result.symbols == ()
    assert result.errors == ()


def test_syntax_error_returns_structured_error(tmp_path: Path) -> None:
    source = write_source(tmp_path, "def broken(:\n    pass\n")

    result = PythonASTParser().parse_file(source)

    assert result.imports == ()
    assert result.symbols == ()
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "SyntaxError"
    assert result.errors[0].line == 1
    assert result.errors[0].relative_path == "sample.py"


def test_encoding_error_returns_structured_error(tmp_path: Path) -> None:
    path = tmp_path / "bad_encoding.py"
    path.write_bytes(b"\xff\xfe\x00")

    result = PythonASTParser().parse_file(source_file(path, "bad_encoding.py"))

    assert result.imports == ()
    assert result.symbols == ()
    assert len(result.errors) == 1
    assert result.errors[0].error_type in {"SyntaxError", "UnicodeDecodeError"}


def test_unreadable_file_error_returns_structured_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = write_source(tmp_path, "def ok():\n    pass\n")

    def fail_open(path: Path):
        raise OSError("cannot read")

    monkeypatch.setattr("codecompass.parser.python_ast.tokenize.open", fail_open)

    result = PythonASTParser().parse_file(source)

    assert result.symbols == ()
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "OSError"


def test_parse_files_continues_after_bad_file(tmp_path: Path) -> None:
    good = write_source(tmp_path, "def ok():\n    pass\n", "good.py")
    bad = write_source(tmp_path, "def bad(:\n", "bad.py")

    results = PythonASTParser().parse_files((good, bad))

    assert [len(result.symbols) for result in results] == [1, 0]
    assert [len(result.errors) for result in results] == [0, 1]


def test_unicode_identifier_is_supported(tmp_path: Path) -> None:
    name = "\u0633\u0644\u0627\u0645"
    source = write_source(tmp_path, f"def {name}():\n    return 1\n")

    symbol = PythonASTParser().parse_file(source).symbols[0]

    assert symbol.name == name
    assert symbol.qualified_name == name
