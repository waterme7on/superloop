# Maturity Ladders

Use this reference when the user's goal sounds broader than a single UX round, especially when they say things like:

- `真正的商业产品`
- `beta`
- `生产可用`
- `production-ready`
- `可运营`

The rule is simple:

- do not collapse a higher maturity target into a lower stage gate
- if the user did not specify a maturity target, infer the nearest one from their wording
- if the inferred stop rule is weaker than the implied maturity, tighten it

## Default maturity bands

### Demo-ready

This usually means:

- one convincing happy-path demo works
- manual setup is acceptable
- local-only state is acceptable
- missing monitoring is acceptable
- rough edges are okay if the demo story is clear

This does not mean:

- real users can rely on it
- cross-device continuity exists
- operations are safe

### Product-shape-ready

This usually means:

- the product has a credible brand and information architecture
- the main journey works on the target surfaces
- a skeptical user can understand what the product is for
- the artifact looks like a real product, not only a prototype fragment

This does not mean:

- real accounts exist
- cloud persistence exists
- reliability expectations are met

### Beta-ready

This usually means:

- real accounts or identity exist
- the core user data is persisted server-side
- the main journey works across sessions and usually across devices
- import or core data handling is reliable enough for limited real users
- basic analytics and error reporting exist
- the main path has automated verification or serious smoke coverage

### Production-ready

This usually means:

- the beta-ready requirements are met
- permissions, abuse boundaries, and security basics exist
- data durability and recovery are acceptable
- observability and incident debugging are in place
- deployment and rollback posture are real, not ad hoc
- operational ownership is believable

## Heuristics by wording

- `展示`, `demo`, `演示`, `一图流` usually imply `demo-ready`
- `像一个真正的产品`, `商业产品`, `可售卖` usually imply at least `product-shape-ready`, often `beta-ready`
- `给用户用`, `可用`, `真实用户` usually imply at least `beta-ready`
- `生产可用`, `production`, `线上可靠` imply `production-ready`

When in doubt, prefer the higher maturity target unless the user has also given hard constraints that clearly force a lower one.

## Stop-audit shortcut

Before stopping, ask:

1. Did we only finish the current stage, or the full maturity target?
2. Are critical gaps still open for this maturity band?
3. Would a skeptical operator still call this a prototype?

If yes, it is not `goal complete` yet.
