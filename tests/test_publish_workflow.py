"""Exercise the tag and release-status gates actually shipped in the workflow."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap

import pytest

WORKFLOW = (Path(__file__).resolve().parents[1] / '.github/workflows/publish.yml').read_text()
TAG_PATTERN = re.search(r'\[\[ "\$RELEASE_TAG" =~ (.*?) \]\]', WORKFLOW).group(1)
STATUS_SCRIPT = textwrap.dedent(WORKFLOW.split("python - <<'PYCODE'\n", 1)[1].split('          PYCODE', 1)[0])


@pytest.mark.parametrize('tag,valid', [
    ('v3.1.0', True), ('v4.0.0.dev12', True), ('v4.0.0rc1', True),
    ('v4.0.0rc12', True), ('4.0.0rc1', False), ('v4.0.0.rc1', False),
    ('v4.0.0rc', False), ('v4.0.0.dev1rc1', False),
    ('v4.0.0rc1/../other', False), ('v4.0.0rc1\n', False),
])
def test_tag_gate(tag, valid):
    result = subprocess.run(['bash', '-c', '[[ "$RELEASE_TAG" =~ $TAG_PATTERN ]]'],
                            env={**os.environ, 'RELEASE_TAG': tag, 'TAG_PATTERN': TAG_PATTERN})
    assert (result.returncode == 0) == valid


@pytest.mark.parametrize('tag,prerelease', [
    ('v3.1.0', False), ('v4.0.0.dev12', True), ('v4.0.0rc1', True),
])
@pytest.mark.parametrize('draft,correct_status', [(False, True), (True, True), (False, False)])
def test_release_status_gate(tag, prerelease, draft, correct_status, tmp_path):
    (tmp_path / 'release.json').write_text(json.dumps({
        'isDraft': draft, 'isPrerelease': prerelease if correct_status else not prerelease,
    }))
    result = subprocess.run([sys.executable, '-c', STATUS_SCRIPT], capture_output=True,
                            env={**os.environ, 'RELEASE_TAG': tag, 'RUNNER_TEMP': str(tmp_path)})
    assert (result.returncode == 0) == (not draft and correct_status), result.stderr
