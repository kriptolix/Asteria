"""Command-line interface (spec section 15).

    odt2web artigo.odt
    odt2web artigo.odt -o dist/
    odt2web artigo.odt --css
    odt2web artigo.odt --assets assets/
    odt2web artigo.odt --fragment
    odt2web artigo.odt --config config.yaml
    odt2web --check artigo.odt
"""
from __future__ import annotations

import argparse
import sys

from . import __version__, check, convert
from .reader import InvalidOdtError
from .result import WarningLevel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="odt2web",
        description="Converte documentos OpenDocument Text (.odt) em HTML/CSS.",
    )
    parser.add_argument("input", help="Caminho para o arquivo .odt")
    parser.add_argument(
        "-o", "--output-dir", dest="output_dir", default=None,
        help="Diretorio de saida (grava index.html, style.css e assets/)",
    )
    parser.add_argument(
        "--css", dest="css", action=argparse.BooleanOptionalAction, default=None,
        help="Gera CSS automaticamente (padrao: ativado; use --no-css para desativar)",
    )
    parser.add_argument(
        "--extract-images", dest="extract_images", action=argparse.BooleanOptionalAction,
        default=None, help="Extrai imagens incorporadas (padrao: ativado)",
    )
    parser.add_argument(
        "--assets", dest="assets_dir", default=None,
        help="Subdiretorio para os assets extraidos (padrao: assets)",
    )
    parser.add_argument(
        "--allow-raw-html", dest="allow_raw_html", action=argparse.BooleanOptionalAction,
        default=None,
        help="Emite blocos ':::html' ... ':::' como HTML literal, sem escaping "
             "(padrao: desativado - so habilite para documentos de autores confiaveis)",
    )
    doc_group = parser.add_mutually_exclusive_group()
    doc_group.add_argument(
        "--fragment", dest="document", action="store_false", default=None,
        help="Gera apenas o fragmento HTML (sem doctype/html/head/body); "
             "sem esta opcao, um documento HTML completo e' gerado por padrao",
    )
    doc_group.add_argument(
        "--document", dest="document", action="store_true", default=None,
        help="Forca a geracao de um documento HTML completo (padrao do CLI)",
    )
    parser.add_argument(
        "--config", dest="config", default=None,
        help="Arquivo de configuracao YAML (secao 16)",
    )
    parser.add_argument(
        "--check", dest="check_only", action="store_true",
        help="Apenas valida o documento, sem gerar HTML",
    )
    parser.add_argument(
        "--html-filename", dest="html_filename", default="index.html",
        help="Nome do arquivo HTML gerado dentro de --output-dir (padrao: index.html)",
    )
    parser.add_argument(
        "--css-filename", dest="css_filename", default="style.css",
        help="Nome do arquivo CSS gerado dentro de --output-dir (padrao: style.css)",
    )
    parser.add_argument("--version", action="version", version=f"odt2web {__version__}")
    return parser


def _print_warnings(warnings, *, file=sys.stderr) -> None:
    for warning in warnings:
        prefix = {
            WarningLevel.INFO: "info",
            WarningLevel.WARNING: "aviso",
            WarningLevel.ERROR: "erro",
        }.get(warning.level, "aviso")
        source = f" ({warning.source})" if warning.source else ""
        print(f"[{prefix}]{source} {warning.message}", file=file)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.check_only:
            warnings = check(args.input)
            _print_warnings(warnings, file=sys.stdout)
            errors = [w for w in warnings if w.level == WarningLevel.ERROR]
            print(f"OK: {args.input} e' um documento .odt valido "
                  f"({len(warnings)} aviso(s))")
            return 1 if errors else 0

        kwargs: dict = {"output_dir": args.output_dir, "config": args.config}
        if args.css is not None:
            kwargs["css"] = args.css
        if args.extract_images is not None:
            kwargs["extract_images"] = args.extract_images
        if args.assets_dir is not None:
            kwargs["assets_dir"] = args.assets_dir
        if args.allow_raw_html is not None:
            kwargs["allow_raw_html"] = args.allow_raw_html
        # unlike the API, the CLI generates a full document by default
        # (more useful for standalone use); --fragment/--document override this.
        kwargs["document"] = args.document if args.document is not None else True

        result = convert(args.input, **kwargs)
    except InvalidOdtError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError:
        print(f"Erro: arquivo nao encontrado: {args.input}", file=sys.stderr)
        return 2

    if args.output_dir:
        result.write(args.output_dir, html_filename=args.html_filename,
                      css_filename=args.css_filename)
        print(f"Gravado em {args.output_dir}/{args.html_filename}"
              + (f" e {args.output_dir}/{args.css_filename}" if result.css else ""))
    else:
        sys.stdout.write(result.html)
        if not result.html.endswith("\n"):
            sys.stdout.write("\n")

    _print_warnings(result.warnings)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
