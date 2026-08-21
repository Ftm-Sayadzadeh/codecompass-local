from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

from codecompass.chunker import CodeChunker
from codecompass.parser import ParseError, ParseResult, PythonASTParser
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


def parse(tmp_path: Path, content: str, name: str = "sample.py") -> ParseResult:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))
    return PythonASTParser().parse_file(source_file(path, name))


def chunks(tmp_path: Path, content: str) -> tuple:
    return CodeChunker().chunk_parse_result(parse(tmp_path, content)).chunks


def test_function_chunk_has_exact_source_and_metadata(tmp_path: Path) -> None:
    result = chunks(
        tmp_path,
        """
def greet(name):
    \"\"\"Say hi.\"\"\"
    return f"hi {name}"
""".lstrip(),
    )

    chunk = result[0]

    assert chunk.chunk_type == "function"
    assert chunk.symbol.qualified_name == "greet"
    assert chunk.start_line == 1
    assert chunk.end_line == 3
    assert chunk.code == 'def greet(name):\n    """Say hi."""\n    return f"hi {name}"\n'
    assert chunk.content_hash == hashlib.sha256(chunk.code.encode("utf-8")).hexdigest()
    assert len(chunk.chunk_id) == 64
    assert "path: sample.py" in chunk.embedding_text
    assert "qualified_name: greet" in chunk.embedding_text
    assert "docstring: Say hi." in chunk.embedding_text
    assert "source:\n" in chunk.embedding_text


def test_method_and_class_overview_chunks_for_class_with_methods(tmp_path: Path) -> None:
    result = chunks(
        tmp_path,
        """
@model
class User:
    \"\"\"A user model.\"\"\"
    table = "users"

    def save(self):
        return self.table

    async def load(self):
        return self.table
""".lstrip(),
    )

    assert [(chunk.chunk_type, chunk.symbol.qualified_name) for chunk in result] == [
        ("class_overview", "User"),
        ("method", "User.save"),
        ("method", "User.load"),
    ]

    overview = result[0]
    assert "@model\nclass User:" in overview.code
    assert '"""A user model."""' in overview.code
    assert 'table = "users"' in overview.code
    assert "def save" not in overview.code
    assert "async def load" not in overview.code

    method = result[1]
    assert method.code == "    def save(self):\n        return self.table\n"
    assert method.symbol.parent_qualified_name == "User"


def test_class_overview_preserves_exact_decorator_source(tmp_path: Path) -> None:
    result = chunks(
        tmp_path,
        """
@route("/x")
class X:
    value = 1
""".lstrip(),
    )

    chunk = result[0]

    assert chunk.chunk_type == "class_overview"
    assert chunk.start_line == 1
    assert chunk.code == '@route("/x")\nclass X:\n    value = 1\n'


def test_nested_class_body_is_excluded_from_parent_overview(tmp_path: Path) -> None:
    result = chunks(
        tmp_path,
        """
class Outer:
    label = "outer"

    class Inner:
        label = "inner"
""".lstrip(),
    )

    outer = result[0]
    inner = result[1]

    assert outer.chunk_type == "class_overview"
    assert 'label = "outer"' in outer.code
    assert "class Inner" not in outer.code
    assert inner.chunk_type == "class_overview"
    assert "class Inner:" in inner.code


def test_multiple_symbols_are_deterministic_and_stable(tmp_path: Path) -> None:
    parse_result = parse(
        tmp_path,
        """
def b():
    pass

def a():
    pass
""".lstrip(),
    )
    chunker = CodeChunker()

    first = chunker.chunk_parse_result(parse_result).chunks
    second = chunker.chunk_parse_result(parse_result).chunks

    assert [chunk.symbol.qualified_name for chunk in first] == ["b", "a"]
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]


def test_chunk_id_changes_when_content_changes(tmp_path: Path) -> None:
    first = chunks(tmp_path, "def value():\n    return 1\n")[0]
    second = chunks(tmp_path, "def value():\n    return 2\n")[0]

    assert first.chunk_id != second.chunk_id
    assert first.content_hash != second.content_hash


def test_parser_errors_are_propagated_as_chunk_errors(tmp_path: Path) -> None:
    path = tmp_path / "bad.py"
    path.write_text("def bad(:\n", encoding="utf-8")
    parse_result = ParseResult(
        source_file=source_file(path, "bad.py"),
        imports=(),
        symbols=(),
        errors=(
            ParseError(
                relative_path="bad.py",
                absolute_path=path.resolve(),
                error_type="SyntaxError",
                message="invalid syntax",
                line=1,
                column=9,
            ),
        ),
    )

    result = CodeChunker().chunk_parse_result(parse_result)

    assert result.chunks == ()
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "SyntaxError"
    assert result.errors[0].symbol_name is None


def test_missing_file_returns_chunk_error(tmp_path: Path) -> None:
    parse_result = parse(tmp_path, "def gone():\n    pass\n")
    parse_result.source_file.absolute_path.unlink()

    result = CodeChunker().chunk_parse_result(parse_result)

    assert result.chunks == ()
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "FileNotFoundError"


def test_invalid_encoding_cookie_during_chunking_returns_chunk_error(tmp_path: Path) -> None:
    parse_result = parse(tmp_path, "def ok():\n    pass\n", "bad_encoding.py")
    parse_result.source_file.absolute_path.write_bytes(b"# coding: does-not-exist\ndef ok():\n    pass\n")

    result = CodeChunker().chunk_parse_result(parse_result)

    assert result.chunks == ()
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "SyntaxError"


def test_invalid_symbol_range_errors_only_that_symbol(tmp_path: Path) -> None:
    parse_result = parse(
        tmp_path,
        """
def ok():
    pass

def bad():
    pass
""".lstrip(),
    )
    bad_symbol = replace(parse_result.symbols[1], end_line=99)
    parse_result = replace(parse_result, symbols=(parse_result.symbols[0], bad_symbol))

    result = CodeChunker().chunk_parse_result(parse_result)

    assert [chunk.symbol.qualified_name for chunk in result.chunks] == ["ok"]
    assert len(result.errors) == 1
    assert result.errors[0].symbol_name == "bad"


def test_unicode_path_and_source_are_supported(tmp_path: Path) -> None:
    name = "\u067e\u06cc\u0627\u0645.py"
    result = CodeChunker().chunk_parse_result(
        parse(tmp_path, "def سلام():\n    return 'درود'\n", name)
    )

    assert result.errors == ()
    assert result.chunks[0].source_file.relative_path == name
    assert "سلام" in result.chunks[0].code


def test_chunk_parse_results_continues_after_error(tmp_path: Path) -> None:
    good = parse(tmp_path, "def ok():\n    pass\n", "good.py")
    bad_path = tmp_path / "bad.py"
    bad_path.write_text("x = 1\n", encoding="utf-8")
    bad = ParseResult(
        source_file=source_file(bad_path, "bad.py"),
        imports=(),
        symbols=(),
        errors=(
            ParseError("bad.py", bad_path.resolve(), "SyntaxError", "invalid", 1, 1),
        ),
    )

    results = CodeChunker().chunk_parse_results((good, bad))

    assert [len(result.chunks) for result in results] == [1, 0]
    assert [len(result.errors) for result in results] == [0, 1]
