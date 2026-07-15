# Contributing

## Python development setup

PyZNN requires Python 3.12 or newer.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pre-commit install
```

No live Zenon node is needed for development or CI. For the complete vectors and
transport fixture, clone the stable specification at the revision pinned in
`.github/workflows/ci.yml`:

```bash
git clone https://github.com/0x3639/zenon-sdk-spec.git ../zenon-sdk-spec
git -C ../zenon-sdk-spec checkout 69f2ecf955bafa4037c73f4b858619ef834e738b
```

## Required checks

Run the same substantive checks as CI:

```bash
python -m compileall -q znn tests
ruff check --select E9,F63,F7,F82 znn tests

ZNN_SPEC_ROOT=../zenon-sdk-spec \
  python -m coverage run -m pytest -q
python -m coverage report

python -m znn.conformance \
  ../zenon-sdk-spec/conformance/vectors \
  --output znn-sdk-results.json
python ../zenon-sdk-spec/tools/znn_spec.py \
  check-results znn-sdk-results.json
python ../zenon-sdk-spec/tools/znn_spec.py \
  check-manifest conformance/manifest.json
```

Coverage is branch-enabled and must remain at or above the configured 95.00%
combined floor. Tests and vectors must remain deterministic and offline; use
fakes or the specification's localhost fixture rather than a node.

## Generated files

`znn/model/models.py` and `znn/api/_response.py` are generated from the pinned
stable specification:

```bash
python tools/generate_models.py \
  ../zenon-sdk-spec/spec/models.json \
  --output /tmp/models.py
diff -u znn/model/models.py /tmp/models.py

python tools/generate_rpc_responses.py \
  ../zenon-sdk-spec/spec/rpc.json \
  --output /tmp/rpc_response.py
diff -u znn/api/_response.py /tmp/rpc_response.py
```

Do not hand-edit generated inventories. Update the generator, regenerate, and
verify byte-for-byte output instead.

## Documentation site

The Docusaurus site lives in `documentation/website`.

Regenerate the exact API/model references and LLM-readable artifacts first:

```bash
python tools/generate_documentation.py
python tools/generate_documentation.py --check
```

```bash
cd documentation/website
npm install
npm run start
```

Before opening a pull request, run the production build so broken internal
links, invalid front matter, and MDX errors fail locally:

```bash
npm run build
```

The production build also creates the local full-text search index. Use
`npm run serve` after a build when testing search locally.

After changes reach `master`, `.github/workflows/pages.yml` repeats the clean
production build and deploys its output through GitHub Pages. Repository Pages
settings must use **GitHub Actions** as the deployment source.

Keep examples explicit about endpoint trust, avoid embedding live public-node
addresses, and ensure snippets match the current Python signatures.

## Pull requests

- Work from a focused feature branch.
- Add offline regression coverage for behavior changes.
- Update the capability manifest when the stable surface changes.
- Regenerate model or RPC inventories when their specification inputs change.
- Update both the root README and Docusaurus guides when user-facing behavior
  changes.
- Regenerate and check the API reference, model reference, Markdown mirrors,
  `llms.txt`, and `llms-full.txt`.
- Include the complete verification results in the pull-request description.
