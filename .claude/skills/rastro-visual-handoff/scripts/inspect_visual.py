#!/usr/bin/env python3
"""Inventário estático de CSS/HTML local; não executa JS, rede ou cascata CSS."""
from __future__ import annotations
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys

MAX_BYTES = 20 * 1024 * 1024


class Sections(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.current: str | None = None
        self.styles: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag in ('style', 'script'):
            self.current = tag

    def handle_endtag(self, tag) -> None:
        if tag == self.current:
            self.current = None

    def handle_data(self, data) -> None:
        if self.current == 'style':
            self.styles.append(data)
        elif self.current == 'script':
            self.scripts.append(data)


def blocks(css: str, pattern: str) -> list[dict]:
    result = []
    for match in re.finditer(pattern, css, re.I):
        start = css.find('{', match.end())
        if start < 0:
            continue
        depth, end = 1, start + 1
        while end < len(css) and depth:
            depth += (css[end] == '{') - (css[end] == '}')
            end += 1
        if not depth:
            result.append({'name': match.group(1), 'body': css[start+1:end-1],
                           'order': len(result)+1})
    return result


def inspect(raw: bytes, kind: str, label: str = 'local-reference') -> dict:
    if kind not in ('css', 'html'):
        raise ValueError('Tipo não suportado; informar css ou html.')
    if len(raw) > MAX_BYTES:
        raise ValueError('Entrada excede o limite de 20 MiB.')
    text = raw.decode('utf-8-sig')
    if kind == 'html':
        parser = Sections(); parser.feed(text)
        css, js = '\n'.join(parser.styles), '\n'.join(parser.scripts)
    else:
        css, js = text, ''
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    variables = [
        {'name': match.group(1), 'value': match.group(2).strip(), 'order': i+1}
        for i, match in enumerate(re.finditer(r'(--[A-Za-z0-9_-]+)\s*:\s*([^;{}]+)', css))
        if 'url(' not in match.group(2).lower()
    ]
    properties = ('animation(?:-[\\w-]+)?|transition(?:-[\\w-]+)?|scroll-behavior')
    declarations = [
        {'property': m.group(1).lower(), 'value': m.group(2).strip()}
        for m in re.finditer(r'(?<![\w-])(' + properties + r')\s*:\s*([^;{}]+)', css, re.I)
    ]
    return {
        'schema_version': '1.1', 'classification': 'observado_estatico',
        'source': {'label': label, 'kind': kind, 'sha256': hashlib.sha256(raw).hexdigest()},
        'css_custom_property_definitions': variables,
        'keyframe_definitions': blocks(css, r'@(?:-webkit-)?keyframes\s+([\w-]+)'),
        'motion_declarations': declarations,
        'media_query_headers': [m.group(1).strip() for m in re.finditer(r'@media\s+([^{}]+)\{', css)],
        'reduced_motion_blocks': blocks(css, r'@media\s*(\([^{}]*prefers-reduced-motion[^{}]*\))'),
        'javascript_marker_counts': {name: js.count(name) for name in (
            'requestAnimationFrame', 'cancelAnimationFrame', 'matchMedia', 'scrollIntoView',
            'MutationObserver', 'localStorage', 'sessionStorage')},
        'limitations': [
            'Não executa JS, browser, rede, imports CSS ou dados da aplicação.',
            'Não resolve cascata, especificidade, herança ou media queries efetivas.',
            'HTML: só estilos/script inline; TSX/JS da aplicação não é interpretado.',
            'Blocos complexos/strings CSS exigem revisão; não é parser CSS completo.',
            'Duplicatas preservadas em ordem textual, sem afirmar valor computado.',
            'Contagens JS não provam funcionalidade/cancelamento ou aprovação.',
            'Não reproduz o JS/dataset; conteúdo CSS requer revisão antes de publicar.',
            'Não mede suavidade, foco, acessibilidade ou segurança no runtime.'
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        kind = {'.css': 'css', '.html': 'html', '.htm': 'html'}.get(args.input.suffix.lower())
        if not kind or not args.input.is_file() or args.input.is_symlink():
            raise ValueError('Entrada deve ser CSS/HTML local regular, não symlink.')
        if args.input.stat().st_size > MAX_BYTES:
            raise ValueError('Entrada excede o limite de 20 MiB.')
        if any(p.is_symlink() for p in (args.output, *args.output.parents)):
            raise ValueError('Saída não pode atravessar symlink.')
        result = inspect(args.input.read_bytes(), kind, args.input.name)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        print(f'Inventário estático salvo em {args.output}; runtime não observado.')
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
