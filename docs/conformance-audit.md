# Python SDK conformance audit

Audit date: 2026-07-15

Authority: stable `zenon-sdk-spec` 1.0 plus its canonical-node corrections.
All verification was deterministic and offline.

## Before and after

| Surface | Baseline audit | Final result |
|---|---:|---:|
| Upstream/unit tests | 16/16 | 26/26 |
| Portable vectors | no complete adapter | 764/764 |
| ABI boundary profile | 459/491 | 491/491 |
| All ABI cases | 477/512 | 512/512 |
| RPC methods | 49/76, one stale extra | 76/76, no extras |
| Models | 5/72 | 72/72 |
| Enums | 0/6 | 6/6 |
| Embedded ABI functions | 26/84 | 84/84 |
| Embedded builders | 28/68 matched | 68/68 |
| Full capability manifest | absent | valid `full`, 309 mappings |

The full vector adapter emitted `znn-sdk-results/1` with `complete: true`; the
specification checker reported `all submitted vector results match`.

## Transaction and transport audit

Offline tests cover prepare-before-publish behavior, fused plasma, generated
PoW, preselected difficulty validation, raw-hash Ed25519 signatures, send,
receive validation/publication, contract calls, and successful-null publish
results. The canonical account-block hash and signature vectors match.

The stable localhost transcript exercises HTTP reads, structured errors,
pagination errors, null publication, WebSocket subscription normalization,
disconnect, reconnect, resubscribe, and post-reconnect updates. In-flight
requests are failed explicitly on connection loss instead of hanging.

## Final validation

- SDK pytest suite: 26 passed.
- Ruff fatal/static checks: passed.
- Stable spec validation: passed.
- Stable spec unittest suite: 15 passed, including its transport fixture.
- Capability manifest checker: passed at `full` level.
- Result checker: all 764 submitted vector results matched.
- Source inventory: 76 RPCs, 72 models, 84 ABI functions, and 68 builders;
  no RPC count/order, model wire-key, ABI, or builder inventory gaps.

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
