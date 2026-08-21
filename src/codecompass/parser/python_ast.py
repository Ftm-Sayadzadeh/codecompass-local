"""Python AST parser for deterministic source metadata."""

from __future__ import annotations

import ast
import tokenize
from collections.abc import Iterable, Sequence

from codecompass.parser.models import ImportInfo, ParseError, ParseResult, Symbol
from codecompass.scanner import SourceFile


class PythonASTParser:
    """Extract structural metadata from scanned Python source files."""

    def parse_file(self, source_file: SourceFile) -> ParseResult:
        """Parse one scanned Python file."""
        try:
            with tokenize.open(source_file.absolute_path) as file:
                source = file.read()
            tree = ast.parse(source, filename=source_file.relative_path)
        except SyntaxError as error:
            return self._error_result(source_file, error, error.lineno, error.offset)
        except (OSError, UnicodeError) as error:
            return self._error_result(source_file, error)

        return ParseResult(
            source_file=source_file,
            imports=self._imports(tree),
            symbols=tuple(self._symbols(tree.body)),
            errors=(),
        )

    def parse_files(self, source_files: Iterable[SourceFile]) -> tuple[ParseResult, ...]:
        """Parse many scanned Python files without aborting on a bad file."""
        return tuple(self.parse_file(source_file) for source_file in source_files)

    def _imports(self, tree: ast.AST) -> tuple[ImportInfo, ...]:
        imports: list[ImportInfo] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(
                    ImportInfo(
                        module=None,
                        name=alias.name,
                        alias=alias.asname,
                        kind="import",
                        line=node.lineno,
                    )
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                module = "." * node.level + (node.module or "")
                imports.extend(
                    ImportInfo(
                        module=module or None,
                        name=alias.name,
                        alias=alias.asname,
                        kind="from_import",
                        line=node.lineno,
                    )
                    for alias in node.names
                )
        return tuple(sorted(imports, key=lambda item: (item.line, item.kind, item.module or "", item.name)))

    def _symbols(
        self,
        body: Sequence[ast.stmt],
        parents: tuple[str, ...] = (),
        direct_class: str | None = None,
    ) -> list[Symbol]:
        symbols: list[Symbol] = []
        for node in body:
            if isinstance(node, ast.ClassDef):
                qualified_name = self._qualified_name(parents, node.name)
                symbols.append(
                    Symbol(
                        kind="class",
                        name=node.name,
                        qualified_name=qualified_name,
                        parent_qualified_name=self._parent_name(parents),
                        parameters=(),
                        returns=None,
                        decorators=self._decorators(node.decorator_list),
                        bases=tuple(self._unparse(base) for base in node.bases),
                        docstring=ast.get_docstring(node),
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        is_async=False,
                    )
                )
                symbols.extend(self._symbols(node.body, parents + (node.name,), direct_class=qualified_name))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified_name = self._qualified_name(parents, node.name)
                is_method = direct_class is not None
                symbols.append(
                    Symbol(
                        kind="method" if is_method else "function",
                        name=node.name,
                        qualified_name=qualified_name,
                        parent_qualified_name=direct_class if is_method else self._parent_name(parents),
                        parameters=self._parameters(node.args),
                        returns=self._unparse(node.returns) if node.returns else None,
                        decorators=self._decorators(node.decorator_list),
                        bases=(),
                        docstring=ast.get_docstring(node),
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        is_async=isinstance(node, ast.AsyncFunctionDef),
                    )
                )
                symbols.extend(self._symbols(node.body, parents + (node.name,), direct_class=None))
        return symbols

    def _parameters(self, args: ast.arguments) -> tuple[str, ...]:
        names = [arg.arg for arg in args.posonlyargs + args.args]
        if args.vararg:
            names.append(f"*{args.vararg.arg}")
        names.extend(arg.arg for arg in args.kwonlyargs)
        if args.kwarg:
            names.append(f"**{args.kwarg.arg}")
        return tuple(names)

    def _decorators(self, decorators: Sequence[ast.expr]) -> tuple[str, ...]:
        return tuple(self._unparse(decorator) for decorator in decorators)

    def _qualified_name(self, parents: tuple[str, ...], name: str) -> str:
        return ".".join(parents + (name,))

    def _parent_name(self, parents: tuple[str, ...]) -> str | None:
        return ".".join(parents) if parents else None

    def _unparse(self, node: ast.AST) -> str:
        return ast.unparse(node).strip()

    def _error_result(
        self,
        source_file: SourceFile,
        error: Exception,
        line: int | None = None,
        column: int | None = None,
    ) -> ParseResult:
        return ParseResult(
            source_file=source_file,
            imports=(),
            symbols=(),
            errors=(
                ParseError(
                    relative_path=source_file.relative_path,
                    absolute_path=source_file.absolute_path,
                    error_type=type(error).__name__,
                    message=str(error),
                    line=line,
                    column=column,
                ),
            ),
        )
