"""
Highlight básico e sem dependências para blocos `<pre><code class="language-x">`
produzidos pela conversão ODT→HTML (ver converter.py / o estilo
"Preformatted Text" do LibreOffice).

Isto NÃO é um parser de linguagem — é uma varredura única com uma regex
combinada, em ordem de prioridade (comentário > string > número >
keyword > heurística de atribuição > chamada de função > pontuação >
texto puro). Mesmo espírito de toc.py: um pós-processamento leve sobre o
HTML já pronto, sem estado entre builds, sem dependência nova (o
`yaml` usado aqui já é uma dependência do projeto via config.py).

Duas camadas:

- "Genérica" (Camada 0) — se aplica a QUALQUER bloco `<pre><code>`,
  mesmo sem uma classe `language-x` reconhecida: fonte monoespaçada e
  numeração de linha (via CSS, ver o tema), strings entre aspas,
  números, chamadas de função (identificador seguido de "(") e
  parênteses/colchetes/chaves.
- "Consciente da linguagem" (Camada 1) — só quando a classe
  `language-x` bate com uma entrada em `highlight-languages.yaml` (ou
  em `source/highlight.yaml`, que sobrescreve/estende o arquivo
  bundled): + comentários (linha e bloco), + palavras-chave, +
  heurística de "identificador no início da linha antes de um '=' vira
  variável" (quando a linguagem declara suporte).

Isso não tenta rivalizar com Pygments/highlight.js — é regex, então
alguns casos ambíguos (ex: literais de regex em JS, f-strings aninhadas
em Python) podem ocasionalmente colorir errado. Um `language-x` não
reconhecido não quebra nada: cai para a Camada 0 sozinha.
"""

from __future__ import annotations

import re
from html import escape, unescape
from pathlib import Path
from typing import Any

import yaml

from .config import deep_merge

DEFAULT_LANGUAGES_PATH = Path(__file__).parent / "highlight-languages.yaml"

CODE_BLOCK_RE = re.compile(
    r'<pre(?P<pre_attrs>[^>]*)><code(?P<code_attrs>[^>]*)>(?P<code>.*?)</code></pre>',
    re.DOTALL,
)
LANGUAGE_CLASS_RE = re.compile(r'\blanguage-([\w+-]+)\b')

_NUMBER_RE = r'\b\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d+)?\b'
_BRACKETS = "()[]{}"

_TOKEN_CLASS = {
    "comment": "tok-com",
    "string": "tok-str",
    "number": "tok-num",
    "keyword": "tok-kw",
    "call": "tok-fn",
    "bracket": "tok-punc",
}


def load_languages(project_root: Path | None = None) -> dict[str, dict[str, Any]]:
    """Carrega as definições de linguagem bundled, com deep-merge de um
    `source/highlight.yaml` opcional do projeto por cima (mesma regra de
    merge de theme.params sobre theme.yaml — ver
    theme_config.load_theme_config). Um projeto pode adicionar uma
    linguagem nova, ou complementar/sobrescrever uma existente, sem
    tocar em nenhum código Python.

    O retorno já resolve os aliases: `by_key["js"]` e
    `by_key["javascript"]` apontam para a mesma definição.
    """
    bundled: dict[str, Any] = {}
    if DEFAULT_LANGUAGES_PATH.exists():
        bundled = yaml.safe_load(DEFAULT_LANGUAGES_PATH.read_text(encoding="utf-8")) or {}

    overrides: dict[str, Any] = {}
    if project_root is not None:
        override_path = project_root / "source" / "highlight.yaml"
        if override_path.exists():
            overrides = yaml.safe_load(override_path.read_text(encoding="utf-8")) or {}

    merged = deep_merge(bundled, overrides) if overrides else bundled

    by_key: dict[str, dict[str, Any]] = {}
    for name, spec in merged.items():
        if not isinstance(spec, dict):
            continue
        by_key[name] = spec
        for alias in spec.get("aliases", []) or []:
            by_key[alias] = spec
    return by_key


def _build_master_pattern(lang: dict[str, Any] | None) -> re.Pattern:
    """Monta a regex combinada para uma linguagem (ou para o modo
    genérico, quando `lang` é None). A ORDEM dos grupos importa: em cada
    posição do texto, a primeira alternativa que casar vence — por isso
    comentário vem antes de string (evita tratar aspas dentro de um
    comentário como string), e keyword vem antes da heurística de
    chamada de função (evita que `if (` vire uma "chamada" chamada
    "if")."""
    comment_alts: list[str] = []
    if lang:
        for start, end in lang.get("block_comments", []) or []:
            comment_alts.append(rf'{re.escape(start)}.*?{re.escape(end)}')
        line_comment = lang.get("line_comment")
        if line_comment:
            comment_alts.append(rf'{re.escape(line_comment)}[^\n]*')

    string_alts: list[str] = []
    for q in (lang.get("triple_quotes") if lang else []) or []:
        string_alts.append(
            rf'{re.escape(q)}(?:\\.|(?!{re.escape(q)})[\s\S])*?{re.escape(q)}'
        )
    # Aspas simples/duplas genéricas — sempre disponíveis (Camada 0),
    # mesmo sem uma linguagem reconhecida.
    string_alts.append(r'"(?:\\.|[^"\\\n])*"')
    string_alts.append(r"'(?:\\.|[^'\\\n])*'")

    parts: list[str] = []
    if comment_alts:
        parts.append(rf'(?P<comment>{"|".join(comment_alts)})')
    parts.append(rf'(?P<string>{"|".join(string_alts)})')
    parts.append(rf'(?P<number>{_NUMBER_RE})')

    if lang and lang.get("keywords"):
        kw_alt = "|".join(re.escape(str(k)) for k in lang["keywords"])
        parts.append(rf'\b(?P<keyword>{kw_alt})\b')

    # Heurística de "alvo de atribuição": identificador no início da
    # linha (após indentação) seguido de um "=" isolado — não "==",
    # "!=", "<=", ">=", "+=" etc. Só quando a linguagem declara suporte
    # (ver `assignment_style` no YAML); em YAML/SQL, por exemplo, isso
    # não faria sentido. Deliberadamente restrito ao início da linha:
    # não tenta resolver `a, b = 1, 2` nem atribuições no meio da
    # expressão — falsos negativos são preferíveis a falsos positivos
    # aqui (ver a conversa que motivou esta implementação).
    if lang and lang.get("assignment_style") == "equals":
        parts.append(
            r'(?:(?<=\n)|^)(?P<indent>[ \t]*)(?P<assign>[A-Za-z_]\w*)'
            r'(?=[ \t]*=(?![=~]))'
        )

    # Identificador seguido de "(" — heurística de chamada de função.
    # Camada 0: não depende de conhecer a linguagem.
    parts.append(r'(?P<call>[A-Za-z_]\w*)(?=\()')

    # Parênteses/colchetes/chaves — Camada 0.
    parts.append(rf'(?P<bracket>[{re.escape(_BRACKETS)}])')

    # Qualquer outro caractere — texto puro, consumido um a um (garante
    # que a regex combinada cobre 100% do texto, sem gaps).
    parts.append(r'(?P<plain>[\s\S])')

    return re.compile("|".join(parts))


def _highlight_code(code_text: str, lang: dict[str, Any] | None) -> str:
    """`code_text` é o código-fonte já des-escapado (HTML entities
    revertidas). Retorna HTML com `<span class="tok-...">` ao redor dos
    tokens reconhecidos; o restante volta escapado como texto puro."""
    pattern = _build_master_pattern(lang)
    out: list[str] = []
    for m in pattern.finditer(code_text):
        kind = m.lastgroup
        if kind == "assign":
            indent = m.group("indent")
            if indent:
                out.append(escape(indent))
            out.append(f'<span class="tok-var">{escape(m.group("assign"))}</span>')
            continue
        text = m.group(kind)
        css_class = _TOKEN_CLASS.get(kind)
        if css_class:
            out.append(f'<span class="{css_class}">{escape(text)}</span>')
        else:
            out.append(escape(text))
    return "".join(out)


def _wrap_lines(highlighted_html: str) -> str:
    """Envolve cada linha em `<span class="hl-line">`, sem embutir o
    número em si no HTML — o número é desenhado via CSS
    (counter-increment + ::before), ver a sugestão de CSS que acompanha
    este módulo. Mantém o HTML gerado enxuto."""
    lines = highlighted_html.split("\n")
    return "\n".join(f'<span class="hl-line">{line}</span>' for line in lines)


def _inject_class(attrs: str, extra: str) -> str:
    """Adiciona `extra` ao atributo `class="..."` já existente em
    `attrs` (criando um, se ainda não houver)."""
    match = re.search(r'class="([^"]*)"', attrs)
    if match:
        classes = f'{match.group(1)} {extra}'.strip()
        return attrs[: match.start()] + f'class="{classes}"' + attrs[match.end():]
    return f'{attrs} class="{extra}"'


def highlight_code_blocks(html: str, languages: dict[str, dict[str, Any]]) -> str:
    """Encontra todo bloco `<pre><code ...>...</code></pre>` em `html` e
    substitui seu conteúdo por uma versão destacada e numerada por
    linha. Um bloco cuja classe não bate com nenhuma linguagem
    configurada ainda recebe o tratamento genérico (Camada 0) — nunca
    fica "cru" feito hoje, mas também nunca quebra por linguagem
    desconhecida.

    Chamada uma vez por documento em discovery._load_document, depois
    da extração do front matter — roda em todo build (barato, sem
    estado, sem necessidade de cache), no mesmo espírito de
    toc.inject_heading_ids_and_build_toc.
    """

    def _replace(match: re.Match) -> str:
        pre_attrs = match.group("pre_attrs")
        code_attrs = match.group("code_attrs")
        raw_code = unescape(match.group("code"))
        # O odt2web normalmente fecha o bloco com uma quebra de linha
        # antes do `</code>` — sem isto sobraria uma última linha
        # numerada vazia, sem conteúdo nenhum.
        if raw_code.endswith("\n"):
            raw_code = raw_code[:-1]

        lang_match = LANGUAGE_CLASS_RE.search(code_attrs)
        lang_key = lang_match.group(1).lower() if lang_match else None
        lang = languages.get(lang_key) if lang_key else None

        highlighted = _highlight_code(raw_code, lang)
        numbered = _wrap_lines(highlighted)
        new_code_attrs = _inject_class(code_attrs, "hl")

        return f'<pre{pre_attrs}><code{new_code_attrs}>{numbered}</code></pre>'

    return CODE_BLOCK_RE.sub(_replace, html)