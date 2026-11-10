"""Fail-closed browser renderer check for the three P0005 Mermaid diagrams.

This is a thin evidence wrapper around the pinned renderer implementation owned by
Hub PR #1175. It is not a second Mermaid parser or an admission controller.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--html', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--screenshot', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
    verdict = {'schema': 'gmic.p0005.mermaid_render.v1',
               'github_head_sha': args.source_sha,
               'method_owner': 'Hub PR #1175',
               'method_source_sha': '468d80196fbeaaaaaf3fe9a72956e871eb03bc43',
               'mermaid_version': '11.4.1',
               'expected_diagrams': 3,
               'result': 'FAIL_CLOSED', 'results': []}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            page = browser.new_page(viewport={'width': 1440, 'height': 1000})
            page_errors: list[str] = []
            page.on('pageerror', lambda err: page_errors.append(str(err)))
            page.goto(args.html.resolve().as_uri(), wait_until='load', timeout=90000)
            page.wait_for_function('Array.isArray(window.__results) && window.__results.length === 3',
                                   timeout=90000)
            results = page.evaluate('window.__results')
            page.screenshot(path=str(args.screenshot), full_page=True)
            browser.close()
        verdict['results'] = results
        verdict['page_errors'] = page_errors
        verdict['result'] = ('PASS' if len(results) == 3
                             and all(row.get('ok') is True and not row.get('lint') for row in results)
                             and not page_errors else 'FAIL_RENDER_OR_LINT')
    except Exception as exc:
        verdict['error'] = f'{type(exc).__name__}: {exc}'
    args.receipt.write_text(json.dumps(verdict, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'result': verdict['result'], 'cases': len(verdict['results']),
                      'receipt': str(args.receipt)}))
    return 0 if verdict['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())