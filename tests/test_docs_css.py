from pathlib import Path
import re

STYLES = Path(__file__).resolve().parents[1] / 'docs/stylesheets/inklet.css'


def rule_body(css, selector):
    match = re.search(re.escape(selector) + r'\s*\{([^}]*)\}', css)
    assert match, f'{selector} rule is missing from inklet.css'
    return match.group(1)


def test_wide_blocks_scroll_inside_their_own_box_on_phones():
    # Code and tables must scroll in their own box, not widen a phone page.
    css = STYLES.read_text()
    assert 'overflow-x:auto' in rule_body(css, '.codehilite pre')
    assert 'overflow-x:auto' in rule_body(css, '.prose table')
    # A long unbroken link (a DOI) must wrap, not set the minimum column width.
    assert 'overflow-wrap:anywhere' in rule_body(css, '.prose a')
