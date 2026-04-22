# Superloop Visual Map

Use this file when you want to explain the skill quickly to a human, align on the operating model, or show how the loop differs from a normal coding task.

## 1. Skill at a glance

```mermaid
flowchart TD
    A["User sets north-star goal"] --> B["Goal contract\nGoal + Maturity Target + Metric"]
    B --> C["Gate stack\nRound Gate + Stage Gate + Stop Rule"]
    C --> D["Constraints + scope"]
    D --> E["Codex picks next best experiment"]
    E --> F["Make one focused change"]
    F --> G["Mechanical verification"]
    G --> H{"Round gate passed?"}
    H -- Yes --> I["Keep change"]
    H -- No --> J["Discard or revise"]
    I --> K{"Stage gate advanced?"}
    J --> K
    K --> L["Summarize result\nUpdate gap ledger\nChoose next round"]
    L --> M{"Explicit stop rule met\nand critical gaps closed?"}
    M -- No --> N{"Can continue inside contract?"}
    M -- Yes --> O["Goal complete\nFinish and report why"]
    N -- Yes --> E
    N -- No --> P["Pause\nBlocked by + resume condition"]
```

## 2. Two-loop model

```mermaid
flowchart LR
    subgraph OUTER["Outer loop: product learning"]
        O1["North-star goal"]
        O2["Live metric\nsignup, add-to-cart, activation"]
        O3["Stage decision\ncontinue, refine, pivot"]
        O1 --> O2 --> O3
    end

    subgraph INNER["Inner loop: Codex execution"]
        I1["Hypothesis"]
        I2["Implement one vertical slice"]
        I3["Build, browser, analytics, tests"]
        I4["Keep or discard"]
        I1 --> I2 --> I3 --> I4
    end

    O3 --> I1
    I4 --> O2
```

## 3. Goal contract

```mermaid
flowchart TD
    GC["Goal contract"] --> G1["Goal\nWhat outcome matters"]
    GC --> G0["Maturity target\nDemo / Shape / Beta / Production"]
    GC --> G2["Metric\nWhat number moves"]
    GC --> G3["Direction\nHigher or lower"]
    GC --> G4["Stage gate\nCurrent success threshold"]
    GC --> G5["Scope\nWhat may change"]
    GC --> G6["Constraints\nTime, budget, brand, legal"]
    GC --> G7["Stop rule\nWhen to stop or pivot"]
```

## 4. Round anatomy

```mermaid
flowchart TD
    R1["Round start"] --> R2["Review current state"]
    R2 --> R3["Choose one hypothesis"]
    R3 --> R4["Implement minimal change"]
    R4 --> R5["Verify mechanically"]
    R5 --> R6{"Result type"}
    R6 -- "Hard pass" --> R7["Keep"]
    R6 -- "Soft pass" --> R8["Keep carefully\nNeeds more data"]
    R6 -- "Fail" --> R9["Discard or tighten scope"]
    R7 --> R10["Pick next round\nthen continue by default"]
    R8 --> R10
    R9 --> R10
```

## 5. Storefront vs app

```mermaid
flowchart LR
    P["Superloop"] --> S["Storefront path"]
    P --> A["App path"]

    S --> S1["Hero clarity"]
    S --> S2["Product page"]
    S --> S3["Cart and checkout"]
    S --> S4["Trust and event tracking"]

    A --> A1["Onboarding"]
    A --> A2["Primary action"]
    A --> A3["Activation event"]
    A --> A4["Retention proxy"]
```

## 6. Best-practice reading

- The user owns `goal`, `constraints`, and `stop rule`.
- Codex owns `path selection`, `implementation`, and `mechanical verification`.
- Calibrate the requested maturity before deciding what counts as done.
- Passing a stage gate usually promotes the next gate. It does not stop the loop by itself.
- `Round Gate`, `Stage Gate`, and `Stop Rule` are separate. Do not collapse them.
- `Gate passed?` means evidence was compared to the explicit current round gate. It is not a pure vibes call.
- `Stop condition hit?` should be evaluated from the explicit stop rule plus the remaining critical gaps for the chosen maturity target.
- If the loop cannot continue, prefer `pause + blocker + resume condition` over pretending the run is complete.
- If the metric cannot be observed yet, wire instrumentation before trying to optimize it.
- Each round should change one main variable.
- Product signals should be labeled honestly:
  - `hard pass`
  - `soft pass`
  - `needs real traffic`
  - `needs more sample`
