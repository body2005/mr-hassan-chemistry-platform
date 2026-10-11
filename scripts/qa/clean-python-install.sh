#!/bin/sh
# Execute in qa-tests with the current apps/api source mounted read-only at /srv.
# Deliberately fail on every install/check/build/metadata mismatch.
set -eu
cd /srv
python -m venv /tmp/qa-clean-install
runner=/tmp/qa-clean-install/bin/python
"$runner" -m pip install --disable-pip-version-check -e '.[dev]'
"$runner" -m pip check
"$runner" -m pip wheel --no-deps . -w /tmp/qa-wheel
set -- /tmp/qa-wheel/learning_website_api-*.whl
[ "$#" -eq 1 ] && [ -f "$1" ]
"$runner" scripts/verify_dependency_lock.py --wheel "$1"
