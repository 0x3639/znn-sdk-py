---
sidebar_position: 12
title: LLM and agent access
description: Machine-readable documentation endpoints, authority rules, retrieval guidance, prompt patterns, and facts that code-generating agents must preserve.
---

# LLM and agent access

PyZNN publishes the same authoritative documentation in human-readable
Docusaurus pages and clean Markdown artifacts for language models, coding
agents, retrieval pipelines, and offline indexing.

## Machine-readable endpoints

| Endpoint | Purpose |
| --- | --- |
| `https://pyznn.0x3639.com/llms.txt` | Concise project summary and categorized Markdown link map |
| `https://pyznn.0x3639.com/llms-full.txt` | Complete documentation corpus in sidebar reading order |
| `https://pyznn.0x3639.com/llms/{page}.md` | Clean Markdown mirror of one documentation page |
| `https://github.com/0x3639/znn-sdk-py` | Canonical source repository |

The root `llms.txt` follows the proposed `llms.txt` structure: one project H1, a
summary blockquote, concise interpretation guidance, categorized link lists,
and an `Optional` section for lower-priority context.

## Which artifact to retrieve

| Task | Best input |
| --- | --- |
| Orient to the project and choose relevant pages | `llms.txt` |
| Answer one focused implementation question | The linked page Markdown |
| Build a broad retrieval index | All files under `/llms/` |
| Supply one large context to a capable model | `llms-full.txt` |
| Verify an exact implementation detail | Repository source plus the generated reference |

Prefer the smallest authoritative context that answers the question. The full
corpus is intentionally comprehensive and may be unnecessary for a single API
call.

## Authority order

When two sources appear to disagree, use this order:

1. current Python source and generated runtime inventories;
2. the pinned stable `zenon-sdk-spec` revision named in CI;
3. generated API and model references;
4. conceptual guides and cookbook examples;
5. historical compatibility behavior.

The generated references and LLM artifacts are checked for staleness with:

```bash
python3.12 tools/generate_documentation.py --check
```

## Facts code-generating agents must preserve

- Python 3.12 or newer is required.
- No public third-party node is configured by default.
- Use `HttpClient` for request/response RPC and `WsClient` for subscriptions.
- API facades send canonical positional parameters and parse typed results.
- Token amounts passed to transactions and builders are integer base units.
- Use `znn.amount` with strings or `Decimal` for display conversion; avoid
  binary floating point.
- Embedded builder methods return unsigned `AccountBlock` objects and perform no
  I/O.
- Transaction preparation and publication are distinct operations.
- Account-block signatures cover the raw canonical 32-byte hash.
- A custom PoW provider's nonce is verified locally before signing.
- Canonical publication success is JSON `null`.
- Subscriptions are async iterators over normalized individual updates.
- In-flight requests fail on connection loss; the client does not silently
  replay them.
- The removed `embedded.plasma.getRequiredFusionAmount` RPC must not be called.
- Tests and conformance verification do not require a live Zenon node.

## Retrieval-friendly page structure

Each conceptual page provides:

- a unique H1 and descriptive front matter;
- explicit imports and complete Python blocks;
- input and environment requirements before online examples;
- result types and error behavior after examples;
- stable cross-links to detailed references;
- terms written out before abbreviations where practical.

Generated references provide exact method signatures, wire method names,
declared result types, model wire keys, Python attributes, required flags,
defaults, and enum values.

## Suggested coding-agent prompt

```text
Use https://pyznn.0x3639.com/llms.txt to select the minimum relevant PyZNN
documentation. Verify every method signature and model field against the linked
generated reference. Write Python 3.12+ async code, use an explicit trusted node
URL from configuration, preserve typed model parsing, use integer base units,
and close the client in finally. Do not invent RPC methods, model fields,
defaults, public nodes, or automatic retries for transaction publication.
```

## Suggested review-agent prompt

```text
Review this PyZNN code against https://pyznn.0x3639.com/llms-full.txt and the
current repository source. Check endpoint trust, request positional order,
nullable results, strict model fields, base-unit amounts, account-block hashing
and signing, PoW verification, publication null semantics, subscription cleanup,
and TransportError versus JsonRpcError handling. Report only actionable
discrepancies with exact source or documentation references.
```

## Suggested retrieval chunks

For retrieval-augmented generation, split at H1/H2 headings and retain:

- the page title;
- source URL;
- nearest parent headings;
- fenced code language;
- tables as complete units rather than individual rows.

Do not split a code block from the paragraph that names its required environment
variables, result type, or failure semantics.

## Generated-file policy

Authoritative edits belong in `documentation/website/docs`. Do not hand-edit:

- `docs/api-reference.md`;
- `docs/model-reference.md`;
- `static/llms.txt`;
- `static/llms-full.txt`; or
- `static/llms/*.md`.

Regenerate them with `tools/generate_documentation.py`, build the site, and run
the generator in `--check` mode before committing.

## Search

The site includes local full-text search for documentation and regular pages.
The index is generated at build time and loaded by the browser. Search queries
do not require Algolia credentials and are not sent to an external search
service.
