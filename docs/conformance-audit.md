# Python SDK conformance audit

Audit date: 2026-07-15

Authority: stable `zenon-sdk-spec` 1.0 plus its canonical-node corrections.
All verification was deterministic and offline.

## Before and after

| Surface | Baseline audit | Final result |
|---|---:|---:|
| Upstream/unit tests | 16/16 | 62/62 |
| Portable vectors | no complete adapter | 764/764 |
| ABI boundary profile | 459/491 | 491/491 |
| All ABI cases | 477/512 | 512/512 |
| RPC methods | 49/76, one stale extra | 76/76, no extras |
| Models | 5/72 | 72/72 field-aware schemas and runtime types |
| Enums | 0/6 | 6/6 |
| Embedded ABI functions | 26/84 | 84/84 |
| Embedded builders | 28/68 matched | 68/68 |
| Full capability manifest | absent | valid `full`, 309 mappings |

The full vector adapter emitted `znn-sdk-results/1` with `complete: true`; the
specification checker reported `all submitted vector results match`. The three
stateful transport cases are computed through `HttpClient`, `LedgerApi`, and
`WsClient` against the specification's localhost fixture. They are not literal
or transcript echoes.

The model corpus contains identity-only examples and uses intentionally invalid
placeholder text for primitive binary cores and the AccountBlock nonce. The
adapter therefore applies the generated wire schema to those five schema-only
fixtures while the public `Address`, `Hash`, `TokenStandard`, and `AccountBlock`
parsers enforce their actual encodings. Runtime RPC results use strict generated
models, including required keys, canonical decimals, nested model construction,
and wire-key aliases. This limitation belongs to the current corpus and is not
counted as stronger behavioral evidence than it provides.

## Transaction and transport audit

Offline tests cover prepare-before-publish behavior, fused plasma, generated
PoW, preselected difficulty validation, raw-hash Ed25519 signatures, send,
receive validation/publication, contract calls, and successful-null publish
results. The canonical account-block hash and signature vectors match.

The stable localhost transcript exercises HTTP reads, structured errors,
pagination errors, null publication, WebSocket subscription normalization,
disconnect, reconnect, resubscribe, and post-reconnect updates. In-flight
requests are failed explicitly on connection loss instead of hanging. A
deterministic regression covers notifications delivered in the same read batch
as a resubscribe response, and orphan notification buffers are bounded.

## Final validation

- SDK pytest suite: 62 passed, including the live localhost transport checks.
- Exhaustive generated-model regression: all 305 removable required wire
  fields are rejected when absent.
- Ruff fatal/static checks: passed.
- Stable spec validation: passed.
- Stable spec unittest suite: 15 passed, including its transport fixture.
- Capability manifest checker: passed at `full` level.
- Result checker: all 764 submitted vector results matched.
- Source inventory: 76 RPCs, 72 models, 84 ABI functions, and 68 builders;
  no RPC count/order, model wire-key, ABI, or builder inventory gaps.
- Every capability-manifest symbol resolves; RPC entries point to concrete
  methods, and generated model/RPC inventories reproduce from the pinned spec.
- CI pins the specification checkout to commit
  `69f2ecf955bafa4037c73f4b858619ef834e738b` and runs the manifest checker.

## Independent review corrections

An independent review after the initial implementation identified weaknesses
that the original vector totals did not expose. Corrections include real-client
transport conformance, reconnect orphan draining, clean-close pending failure,
send-error normalization, strict primitive JSON reconstruction, hashability,
field-aware generated models, typed RPC results, strict ABI hash inputs,
normalized malformed-key-file errors, immediate nonce rejection, bounded
WebSocket orphan buffers, resolvable manifest symbols, and a compatible
`websockets>=10,<11` dependency range. A subsequent audit also normalized HTTP
connection/JSON failures and verifies JSON-RPC response correlation.

A fresh review directly against every stable specification requirement then
corrected response-only `AccountBlock` fields and nested response parsing,
required and configurable key-file KDF fields, canonical RPC method aliases,
subscription topic/arity/identifier validation, ABI error normalization,
unsigned-64 and canonical amount/PoW boundaries, minimum preselected PoW
difficulty, the specified 16/32-byte entropy profile, bytes-like primitive
cores, SDK lifecycle argument validation, WebSocket connection timeouts, and
single-flight reconnect shutdown behavior. The reconnect transcript now
verifies three consecutive subscription delivery/recovery cycles.

A second independent re-review exposed a partial-resubscribe failure mode: one
transient error could discard subscriptions that had not yet been restored.
Recovery now snapshots the complete subscription set once, retries that full
set after every failed attempt, closes each failed socket, ignores stale
listener recovery signals, and delivers terminal `TransportError` failures to
subscription consumers when recovery is exhausted. Model parsing also accepts
both padded and unpadded standard base64 as required, while continuing to reject
malformed alphabets and padding. The literal one- and two-argument subscription
call sites again make the stable source inventory report all 76 RPC methods.

## Legacy audit-tool limitations

The older focused Python probe contains hard-coded maps for only the original
eight ABI catalogs and seven builder API classes. It therefore still labels the
new Bridge, HTLC, Liquidity, and Spork cases as missing even though the complete
portable adapter executes and matches them. Similarly, the legacy source audit
unconditionally emits the two historical page-default findings, sets its enum
inventory to an empty list, and uses a fixed 31-operation API map. Direct source
inventory, the validated full manifest, and the 764-case adapter supersede those
stale diagnostic fields. The underlying page defaults are both zero, all six
`IntEnum` classes exist, and all 55 public operations are implemented.

No known conformance failures remain.
