# Artifact Gates

Use this reference when the user has clearly named the artifact but has not given a precise stage gate yet.

The rule is simple:

- pick the nearest gate that can be mechanically verified now
- prefer flow completion before conversion optimization
- if the target metric cannot be observed yet, add the instrumentation gate before trying to optimize that metric
- do not optimize copy, trust, or design until the core path works
- when a gate passes, promote the next gate instead of stopping the loop unless the top-level goal is already met

## Storefront

Default gate progression:

1. product page renders correctly
2. variant or quantity selection works if applicable
3. add-to-cart works
4. cart renders correctly
5. checkout entry works
6. analytics for key commerce actions fire
7. only then optimize conversion surfaces

Good phase-gate examples:

- `A visitor can land on a product page and add the item to cart without errors`
- `Cart drawer opens, updates quantity, and reaches checkout`
- `view_item`, `add_to_cart`, and `begin_checkout` events fire`

## Landing page

Default gate progression:

1. page loads fast and without broken sections
2. primary CTA is above the fold and obvious
3. CTA destination works
4. signup, waitlist, or lead form submits successfully
5. confirmation state is visible
6. event tracking exists
7. only then test messaging or trust variations

Good phase-gate examples:

- `Primary CTA is visible and leads to a working form`
- `Lead form submits successfully on desktop and mobile`
- `Hero, social proof, and CTA render cleanly with no blocking layout issues`

## App onboarding or activation flow

Default gate progression:

1. first-run path opens without errors
2. user can complete the primary action once
3. success or completion state is visible
4. activation event is logged
5. obvious friction points are reduced
6. only then optimize completion rate

Good phase-gate examples:

- `A new user can reach the first useful action in one session`
- `Primary action completes without manual intervention`
- `Activation event fires on successful completion`

## Content or audience-driven MVP

Default gate progression:

1. core offer is visible
2. audience lands on the correct page or funnel entry
3. primary capture action works
4. attribution or source tagging exists
5. only then test channel-specific message variants

Good phase-gate examples:

- `Traffic from a post lands on a matching offer page and can join the waitlist`
- `The main opt-in flow works and source is recorded`

## Selection heuristics

If several gates are possible, prefer:

1. the one closest to revenue or activation
2. the one with the least external dependency
3. the one that can be verified today

Avoid these mistakes:

- choosing a final business outcome as the first gate
- testing copy before the destination flow works
- trying to improve a live metric before the event or attribution path exists
- adding analytics after several rounds of untracked changes
