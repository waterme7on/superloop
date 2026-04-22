# Goal Contract

Use this reference when the user knows the destination but not the setup for Superloop.

The loop works only when the target is constrained enough to guide tactics.

Important:

- This is primarily for Codex to construct internally
- The user does not need to manually fill every field
- When possible, derive the contract from a short conversation plus repo context

## Fast intake mode

If the user gives only a rough goal, collect the contract with the smallest useful batch of questions.

Suggested sequence:

1. What are we trying to validate right now?
2. What surface are we changing?
3. What absolutely must work in this phase?
4. What hard constraints should I respect?
5. When should I stop optimizing and just unblock the path?

After that, Codex should translate the answers into:

- `Goal`
- `Metric`
- `Direction`
- `Stage Gate`
- `Scope`
- `Constraints`
- `Stop Rule`

Once that contract is clear enough, Codex should execute the current round inside it without asking for per-step approval, and continue into later rounds until the stop condition is met.

The stage gate is the current milestone inside the contract. Passing it usually promotes the next gate. It does not, by itself, mean the loop should stop or ask for fresh permission.

## Default inference rules

When the user does not provide all fields, prefer these defaults:

- `Direction`
  - higher for conversion, activation, signup, add-to-cart
  - lower for errors, drop-offs, latency, friction
- `Stage Gate`
  - if the business metric is slow or noisy, use the nearest mechanical gate first
- `Scope`
  - infer from repo structure and the named artifact
- `Constraints`
  - infer common MVP constraints if the user is clearly in speed mode
- `Stop Rule`
  - if the user does not specify one, default to unblocking the main path before optimization

## Required fields

- `Goal`: what outcome matters
- `Metric`: what number represents progress
- `Direction`: higher or lower
- `Stage Gate`: what counts as success for this phase
- `Scope`: where changes may happen
- `Constraints`: time, budget, brand, legal, infra, or staffing limits
- `Stop Rule`: when to stop, pivot, or ask for help

These fields define the boundary of autonomous action for the current round and any later rounds that stay inside the same contract.

Crossing into the next stage gate is normal progression when it follows the same goal, scope, constraints, and stop rule. Ask again only when the next move would exceed those boundaries.

## Default framing

Convert a broad product wish into:

1. **North-star goal**
   - the larger result the user wants
2. **Current phase goal**
   - the next gate that can be verified now
3. **Round hypothesis**
   - the single thing this iteration is trying to improve

## Good examples

### Storefront

- Goal: validate if families will click through to a water-play product offer
- Metric: product-page-to-add-to-cart rate
- Direction: higher
- Stage Gate: product page, cart, checkout entry, and key commerce events all work end to end
- Scope: landing page, product page, cart, analytics
- Constraints: ship in one night, no CMS, no redesign of the full brand system
- Stop Rule: if three instrumented traffic rounds show no improvement, revisit offer or traffic angle

### App

- Goal: validate whether users complete the first useful action
- Metric: first-session primary-action completion rate
- Direction: higher
- Stage Gate: 5 of 10 test users can complete the action without help
- Scope: onboarding, primary action flow, event logging
- Constraints: single-platform MVP, no advanced account system
- Stop Rule: if the main action remains unclear after two UX simplification rounds, revisit the product promise

## Heuristics

- Prefer one primary metric, at most one guard metric
- Make the current phase gate easier than the final business goal
- If the real business metric is slow, define a shorter proxy for the current round
- If the user only gives a final outcome, infer a staged gate and say so explicitly

## Anti-patterns

- Goal without metric
- Metric without stage gate
- One round trying to change product, messaging, audience, and pricing at once
- Optimization without clear constraints
- Using vanity metrics when a funnel metric is available
