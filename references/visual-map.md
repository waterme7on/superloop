# Superloop Visual Map

Use this file when you want to explain the skill quickly to a human, align on the operating model, or show how the loop differs from a one-shot coding task.

## 1. Skill at a glance

```mermaid
flowchart TD
    A["User as CEO sets mission"] --> B["Mission contract\nGoal + Finish Standard + Budget"]
    B --> C["Gate stack\nRound Gate + Current Gate + Stop Rule"]
    C --> D["Scope + constraints"]
    D --> E["Agent picks next round"]
    E --> F["Make one focused change"]
    F --> G["Mechanical verification"]
    G --> H{"Round gate passed?"}
    H -- Yes --> I["Keep change"]
    H -- No --> J["Discard or revise"]
    I --> K{"Mission complete,\nstop rule hit,\nor budget exhausted?"}
    J --> K
    K -- No --> E
    K -- Yes --> L["Stop and report why"]
```

## 2. CEO / Agent split

```mermaid
flowchart LR
    CEO["CEO\nmission, scope, budget, stop rule"] --> Agent["Coding agent\nplan, execute, verify, decide"]
    Agent --> Harness["Harness\nstate, round ledger, verdicts"]
    Harness --> Repo["Repo, workflow, or deliverable"]
    Repo --> Agent
```

## 3. Mission contract

```mermaid
flowchart TD
    MC["Mission contract"] --> M1["Goal"]
    MC --> M2["Finish standard"]
    MC --> M3["Success signal"]
    MC --> M4["Current gate"]
    MC --> M5["Scope"]
    MC --> M6["Constraints"]
    MC --> M7["Stop rule"]
    MC --> M8["Max rounds / timebox"]
```

## 4. Round anatomy

```mermaid
flowchart TD
    R1["Align on state"] --> R2["Choose one hypothesis"]
    R2 --> R3["Execute one focused change"]
    R3 --> R4["Verify mechanically"]
    R4 --> R5["Keep or discard"]
    R5 --> R6["Record verdict and next round"]
```

## 5. Best-practice reading

- The user owns `goal`, `constraints`, `budget`, and `stop rule`.
- The agent owns `path selection`, `implementation`, and `mechanical verification`.
- The harness owns `persisted state`, `budget tracking`, and `continue / pause / stop`.
- Passing the current gate usually promotes the next gate. It does not stop the loop by itself.
- Budget exhaustion is a valid stop reason. It is not the same thing as mission complete.
- If the loop cannot continue, prefer `pause + blocker + resume condition` over pretending the run is complete.
