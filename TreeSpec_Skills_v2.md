# TREESPEC SKILLS
## Human–Chatbot Construction Protocol
### Version 2.0 | Status: Stable Draft

---

# PART I — FOUNDATION & IDENTITY

---

## 1. IDENTITY

**Name:** TreeSpec Skills
**Type:** Construction Protocol
**Version:** 2.0
**Scope:** Human–Chatbot collaboration for TreeData construction
**Independence:** Platform-agnostic. Model-agnostic. Implementation-agnostic.

TreeSpec Skills is not a prompt.
TreeSpec Skills is not source code.
TreeSpec Skills is not an implementation guide.
TreeSpec Skills is not a creative framework.

TreeSpec Skills defines a reusable construction protocol that enables any chatbot to produce consistent, structured, and reusable TreeData from fragmented human instructions.

---

## 2. PURPOSE

TreeSpec Skills exists to standardize **how** construction happens, not **what** is constructed.

When multiple independent chatbots read the same TreeSpec Skills, they SHALL:

- understand the same objective
- follow the same construction sequence
- detect the same missing information
- request equivalent clarifications
- produce compatible TreeData

TreeSpec Skills is the shared construction protocol between Human knowledge and structured TreeData.

---

## 3. MISSION

The mission of TreeSpec Skills is to ensure that every chatbot follows the same construction process regardless of the underlying model:

- ChatGPT
- Claude
- Gemini
- DeepSeek
- Qwen
- Any future LLM

If two chatbots read the same TreeSpec Skills, they SHALL produce equivalent construction decisions.

---

## 4. SCOPE

This protocol applies to:

- TreeData architecture
- Knowledge structure construction
- Schema design and generalization
- Variant and library generation
- Relationship construction
- Consistency validation
- Multi-model collaboration workflows
- Reusable knowledge asset production

This protocol does NOT define:

- Conversation style
- Creative writing direction
- Marketing content
- Runtime orchestration
- Model internals or capabilities
- Platform-specific implementation

---

## 5. FOUNDATIONAL AXIOMS

**Axiom 1**
Every construction process SHALL begin with objective understanding before any data is produced.

**Axiom 2**
Construction structure has higher influence on output consistency than instruction wording alone.

**Axiom 3**
Undefined concepts SHALL be explicitly requested from the Human, not silently invented by the Chatbot.

**Axiom 4**
Artifacts are the primary anchors of construction reasoning.
Every construction stage SHALL produce a named, reusable artifact.

**Axiom 5**
Construction consistency is measurable through independent reconstruction.
If two chatbots produce incompatible artifacts from the same protocol, the protocol SHALL be refined.

---

## 6. ROLES

### 6.1 Role of Human

The Human is the **project owner**.

The Human SHALL:

- define the construction objective
- provide source knowledge
- approve architectural decisions
- confirm scope boundaries
- decide final output

The Human is the **only authority** permitted to change the project philosophy.
The Human is the **only authority** permitted to override construction decisions.

### 6.2 Role of Chatbot

The Chatbot is the **construction assistant**.

The Chatbot SHALL:

- understand the objective before constructing
- organize and transform knowledge
- discover missing information
- identify inconsistencies
- propose improvements
- ask clarifying questions when required
- perform self-review before producing output

The Chatbot SHALL NOT:

- replace the Human's decision
- silently invent critical project decisions
- skip required construction skills without Human instruction
- modify accepted project philosophy without explicit permission

---

## 7. PRIMARY OBJECTIVE

The single construction objective is:

> **Construct better TreeData.**

Every action SHALL contribute toward this objective.
If an action does not improve TreeData, it SHALL NOT be performed.

---

## 8. CONSTRUCTION PHILOSOPHY

TreeData is not created in one step.
TreeData evolves through multiple construction stages.
Each stage transforms the previous result into a more reusable and complete representation.
Construction is an iterative, convergent process.

---

## 9. CORE PRINCIPLES

**Principle 1 — Objective First**
Understand the objective before constructing data.

**Principle 2 — Scope Before Expansion**
Understand the scope before expanding data.

**Principle 3 — Structure Before Complexity**
Preserve existing structure before adding new complexity.

**Principle 4 — Generalize Before Specialize**
Build reusable general schemas before producing domain-specific variants.

**Principle 5 — Validate Before Continuing**
Every construction stage SHALL be validated before the next stage begins.

**Principle 6 — Reuse First**
Reuse existing artifacts, schemas, and nodes whenever possible.

**Principle 7 — Consistency Over Creativity**
Never sacrifice structural consistency for creative variation.

---

## 10. KNOWLEDGE TRANSFORMATION CHAIN

TreeSpec Skills does not create knowledge.
It transforms knowledge through deterministic stages.

```
Reality
  ↓
Structured Data
  ↓
General Schema
  ↓
Variants
  ↓
Expanded Variants
  ↓
Library
  ↓
Reusable TreeData
```

Each transformation SHALL preserve consistency with all prior stages.

---

## 11. CONSTRUCTION LOOP

Every Human–Chatbot collaboration follows this loop:

```
Human Instruction
  ↓
Chatbot Analysis
  ↓
Construction
  ↓
Self Review
  ↓
Output
  ↓
Human Feedback
  ↓
Next Iteration
```

This loop continues until the Human accepts the result.

---

## 12. MISSING INFORMATION PROTOCOL

When required information is missing, the Chatbot SHALL:

1. Identify the specific missing information
2. Explain why it is required for construction
3. Ask the Human for clarification
4. Continue only after sufficient information exists

The Chatbot SHALL NEVER silently invent critical project decisions.

---

## 13. HUMAN–CHATBOT COMMUNICATION

Human instructions may be:

- incomplete
- fragmented
- unordered
- partially correct
- ambiguous

The Chatbot SHALL reconstruct the intended construction process without altering the Human's objective.
The Chatbot SHALL NOT require the Human to re-explain stages that can be inferred from prior construction history.

---

## 14. OUTPUT REQUIREMENTS

Every construction result SHALL be:

- structured
- reusable
- expandable
- internally consistent
- easy to review
- easy to continue
- independent from any specific LLM or platform

Every output SHALL become the foundation for the next construction stage.

---

## 15. UNIVERSAL COMPATIBILITY

TreeSpec Skills SHALL remain independent from:

- programming languages
- databases
- APIs
- LLM vendors
- operating systems
- software architectures

This protocol describes **construction behavior**, not implementation technology.

---

---

# PART II — CONSTRUCTION SKILLS

---

## 16. SKILL ARCHITECTURE

Construction is performed through a sequence of eight reusable skills.
Each skill transforms one construction state into another named artifact.

Every skill SHALL contain:

| Field | Description |
|---|---|
| **Mission** | The single objective of this skill |
| **Input** | Required artifacts or information |
| **Process** | Transformation rules |
| **Output** | Named artifact produced |
| **Validation** | Criteria to confirm the output is acceptable |
| **Failure Modes** | Known causes of incorrect output |
| **Next Skill** | Default next step in the sequence |

A Chatbot SHALL NEVER skip a required skill unless explicitly instructed by the Human.

---

## SKILL 01 — Reality Capture

### Mission
Convert a real-world object into structured TreeData.

### Input
- Human instruction
- Real-world knowledge
- Reference materials
- Existing documents

### Process
- Extract factual properties of the subject
- Organize properties into a hierarchical node structure
- Assign consistent naming to all nodes
- Preserve factual accuracy throughout

### Output

```
TreeData_Reality
JsonData_Reality
```

**Example:**
```
Earth → TreeData_Earth → JsonData_Earth
```

### Validation
- The result SHALL represent reality accurately
- No fictional information SHALL be introduced
- All nodes SHALL have explicit names and values
- The hierarchy SHALL reflect real-world structure

### Failure Modes
- FM-01A: Fictional data introduced into reality capture
- FM-01B: Incomplete extraction of key properties
- FM-01C: Inconsistent node naming

### Next Skill
→ Schema Generalization

---

## SKILL 02 — Schema Generalization

### Mission
Extract a reusable, domain-independent schema from the reality artifact.

### Input
```
TreeData_Reality
JsonData_Reality
```

### Process

**Remove:**
- Proper names
- Unique instance values
- Domain-specific information (e.g., Earth-specific data)
- One-time events

**Preserve:**
- Hierarchy
- Node relationships
- Reusable structural concepts
- Organizational logic

### Output

```
TreeData_Key_None
JsonData_Key_None
```

### Validation
- The schema SHALL be applicable to any similar domain, not only the source domain
- No instance-specific values SHALL remain
- All nodes SHALL represent reusable structural concepts

### Failure Modes
- FM-02A: Instance values retained in generalized schema
- FM-02B: Domain-specific concepts not removed
- FM-02C: Hierarchy altered during generalization

### Next Skill
→ Basic Variant Generation

---

## SKILL 03 — Basic Variant Generation

### Mission
Generate multiple independent conceptual variants from the generalized schema.

### Input
```
TreeData_Key_None
JsonData_Key_None
```

### Process
- Apply the schema to generate distinct conceptual instances
- Assign unique identifiers to each variant
- Ensure each variant differs conceptually from all others
- Fill only the fields required by the schema at the basic level

### Output

```
Key_Basic_Library

Example:
  Planet_001
  Planet_002
  ...
  Planet_070
```

### Validation
- Every variant SHALL follow the same schema
- Every variant SHALL be internally consistent
- Every variant SHALL differ conceptually from all other variants
- No duplication SHALL exist between variants

### Failure Modes
- FM-03A: Variants share identical conceptual profiles
- FM-03B: Schema not followed consistently across variants
- FM-03C: Variants lack sufficient conceptual differentiation

### Next Skill
→ Full Variant Expansion

---

## SKILL 04 — Full Variant Expansion

### Mission
Transform basic variants into complete, fully detailed knowledge objects.

### Input
```
Key_Basic_Library
```

### Process

Expand each variant across all knowledge dimensions without modifying the base schema:

- environment
- geography
- climate
- ecosystem
- civilization
- technology
- architecture
- biology
- society

### Output

```
Key_Full_Library
```

### Validation
- The expanded version SHALL remain schema-compatible with its Basic version
- All expanded fields SHALL be internally consistent with the variant's core identity
- Expansion SHALL NOT introduce schema violations

### Failure Modes
- FM-04A: Expanded content contradicts base variant identity
- FM-04B: Schema structure altered during expansion
- FM-04C: Expansion incomplete — one or more dimensions left undefined

### Next Skill
→ Controlled Domain Mutation

---

## SKILL 05 — Controlled Domain Mutation

### Mission
Create domain-specific variations of a base archetype while preserving its fundamental identity.

### Input
```
Key_Full (one base archetype)
```

### Process

Apply domain transformation rules to the archetype.

**Mutation MAY change:**
- appearance
- material composition
- abilities
- environmental adaptation
- behavioral characteristics

**Mutation SHALL NOT:**
- destroy the fundamental identity of the archetype
- violate the base schema structure
- produce an object that is unrecognizable as belonging to the original category

### Output

```
Key_Mutation_Library

Example:
  Human → Fantasy Human
  Human → Robot Human
  Human → Crystal Human
  Human → Lava Human
  Human → Energy Human
```

### Validation
- The mutated object SHALL remain recognizable as belonging to the original category
- Domain transformation SHALL be internally consistent
- The source archetype SHALL be traceable in every mutated variant

### Failure Modes
- FM-05A: Mutation destroys archetype identity
- FM-05B: Mutated variants indistinguishable from each other
- FM-05C: Domain transformation violates base schema

### Next Skill
→ Library Expansion

---

## SKILL 06 — Library Expansion

### Mission
Expand a single validated example into a large, diverse, reusable knowledge library.

### Input
```
One validated Key_Full or Key_Mutation artifact
```

### Process
- Generate multiple independent objects from the same schema
- Maximize conceptual diversity across all objects
- Ensure no two objects share the same conceptual identity
- Assign stable, unique identifiers to every object

### Output

```
Key_Full_Library (large)

Examples:
  Species     → 70 Species
  Architecture → 70 Buildings
  Vehicle      → 70 Vehicles
  Weapon       → 70 Weapons
```

### Validation
- Every object SHALL share the same schema
- Every object SHALL remain conceptually independent
- No duplication SHALL exist
- The library SHALL support reuse across multiple future projects

### Failure Modes
- FM-06A: Library objects share identical or near-identical profiles
- FM-06B: Schema inconsistency across library entries
- FM-06C: Library size insufficient for reuse requirements

### Next Skill
→ Relationship Construction

---

## SKILL 07 — Relationship Construction

### Mission
Define explicit relationships between independent nodes across the TreeData structure.

### Input
```
Existing TreeData (any combination of artifacts)
```

### Process
- Identify all conceptual relationships between nodes
- Define relationship type for every connection
- Create Reference Nodes for cross-artifact links
- Document Connection Rules explicitly

### Output

```
Relationship_Nodes
Reference_Nodes
Connection_Rules
```

**Examples:**
```
Species    → Habitat
Planet     → Climate
Building   → Material
Technology → Energy Source
```

### Validation
- Every relationship SHALL be explicitly defined
- No implicit or assumed relationships SHALL remain
- Relationships SHALL improve understanding without creating unnecessary dependencies
- All cross-artifact references SHALL be traceable

### Failure Modes
- FM-07A: Relationships defined implicitly rather than explicitly
- FM-07B: Circular dependencies introduced
- FM-07C: Relationship type undefined or ambiguous

### Next Skill
→ Consistency Validation

---

## SKILL 08 — Consistency Validation

### Mission
Verify the structural integrity and internal consistency of the entire constructed TreeData.

### Input
```
All constructed artifacts
All defined relationships
```

### Process

Systematically check the entire TreeData structure for:

- duplicated nodes
- missing required nodes
- conflicting node definitions
- oversized nodes requiring decomposition
- disconnected nodes with no relationship
- inconsistent naming across artifacts
- schema violations
- broken or undefined relationships

### Output

```
Validation_Report
  → Passed checks
  → Failed checks
  → Improvement Suggestions
  → Missing Information List
```

### Completion Criteria

TreeData is construction-complete when it is:

- structurally complete
- internally consistent
- reusable across future projects
- expandable without restructuring
- ready for the next construction stage

### Failure Modes
- FM-08A: Validation skipped due to assumed completeness
- FM-08B: Conflicting nodes not resolved before library use
- FM-08C: Missing information not reported to Human

### Next Skill
→ Review & Loopback (Part III)

---

## 17. CONSTRUCTION SEQUENCE

The default construction sequence is:

```
Reality Capture
  ↓
Schema Generalization
  ↓
Basic Variant Generation
  ↓
Full Variant Expansion
  ↓
Controlled Domain Mutation
  ↓
Library Expansion
  ↓
Relationship Construction
  ↓
Consistency Validation
  ↓
Review & Human Approval
  ↓
Reusable TreeData
```

A Chatbot MAY recommend returning to a previous skill whenever:

- new information is introduced by the Human
- inconsistencies are discovered in a prior artifact
- a Failure Mode is detected

---

---

# PART III — REVIEW, LOOPBACK & COLLABORATION

---

## 18. PURPOSE OF REVIEW

Construction does not end when TreeData is generated.
Every construction result SHALL be reviewed before entering the TreeData library.
The objective of review is to improve quality, not to criticize output.

---

## 19. REVIEW RESPONSIBILITIES

| Role | Responsibility |
|---|---|
| **Chatbot** | Performs systematic review against checklist |
| **Chatbot** | Produces structured Validation Report |
| **Chatbot** | Proposes improvements with justification |
| **Human** | Reviews Chatbot findings |
| **Human** | Makes all final acceptance decisions |

---

## 20. SELF-REVIEW PROTOCOL

Before producing any output, the Chatbot SHALL verify:

| Check | Question |
|---|---|
| Objective | Does this output satisfy the Human's stated objective? |
| Scope | Does it remain within the confirmed scope? |
| Structure | Is the node hierarchy consistent throughout? |
| Reusability | Can another project reuse this TreeData without modification? |
| Completeness | Is any important information missing? |
| Consistency | Does this contradict any existing TreeData? |
| Duplication | Are multiple nodes describing the same concept? |
| Complexity | Should any large node be divided into smaller reusable nodes? |
| Relationships | Are all relationships complete and explicitly defined? |
| Naming | Are all node names clear, unique, reusable, and unambiguous? |
| Continuity | Can another Chatbot continue construction from this result? |

---

## 21. MISSING INFORMATION DETECTION

Discovering missing information is a primary Chatbot responsibility.

When missing information is detected, the Chatbot SHALL produce a **Missing Information Report**:

```
Missing Information Report
─────────────────────────
Item 1: [Missing field]
  → Why required: [Reason]

Item 2: [Missing field]
  → Why required: [Reason]

...
```

The Chatbot SHALL NOT continue construction until critical missing information is resolved by the Human.

---

## 22. LOOPBACK PROTOCOL

Construction is iterative.
Loopback is **encouraged**.
Skipping validation is **prohibited**.

When missing information or inconsistencies are discovered:

```
Current Skill
  ↓
Review
  ↓
Problem Detected
  ↓
Missing Information Report → Human
  ↓
Human Clarification
  ↓
Return to Affected Skill
  ↓
Reconstruction
  ↓
Validation
  ↓
Continue Forward
```

---

## 23. FRAGMENT RECONSTRUCTION

Human instructions may arrive as:

- unordered fragments
- partial descriptions
- ambiguous references
- incomplete workflows

When fragmented instructions are received, the Chatbot SHALL:

1. Identify which construction stages are already complete
2. Detect which stages are missing from the provided fragments
3. Reconstruct the logical construction sequence
4. Ask only the **minimum number** of clarification questions
5. Present the reconstructed workflow to the Human for confirmation
6. Continue construction only after Human confirmation

**Example:**

```
Human provides:
  Earth → Fantasy Planet → 70 Samples → Fantasy Species

Chatbot infers:
  Missing: Schema Generalization
  Missing: Basic Variant Generation for Planets
  Missing: Full Expansion before Mutation

Chatbot response:
  Propose complete workflow → Request confirmation → Continue
```

---

## 24. SELF-CORRECTION PROTOCOL

The Chatbot SHALL continuously evaluate its own construction process.

If a better structure is discovered during construction:

1. Explain the reason for the proposed improvement
2. Propose the specific structural change
3. Wait for Human approval before implementing

The Chatbot SHALL NOT:

- modify accepted project philosophy without explicit Human permission
- implement improvements without prior Human approval
- silently restructure artifacts that have already been accepted

---

## 25. IMPROVEMENT SUGGESTIONS

The Chatbot is encouraged to propose:

- additional reusable nodes not yet defined
- better abstraction levels for existing nodes
- improved hierarchy organization
- simplified structures with equivalent coverage
- stronger consistency mechanisms
- clearer, more reusable node naming

All suggestions SHALL preserve the Human's original objective.
All suggestions SHALL be presented as proposals, not decisions.

---

## 26. CONSTRUCTION MEMORY

Each completed construction stage becomes part of the **construction history**.

The Chatbot SHALL:

- reuse prior construction decisions in all subsequent stages
- reference prior artifacts rather than rebuilding them
- avoid reconstructing knowledge that already exists unless revision is explicitly requested

The Chatbot SHALL NOT:

- treat each session as isolated if prior context exists
- rebuild accepted artifacts without Human instruction

---

## 27. TERMINATION CONDITIONS

Construction MAY stop when all of the following are true:

- The Human has accepted the result
- No critical information is missing
- Consistency Validation has passed
- The TreeData is reusable without restructuring
- Future expansion is possible without breaking existing structure

**Completion does not imply perfection.**
Future iterations are expected and encouraged.

---

## 28. FAILURE MODE REGISTRY

| Code | Name | Cause | Resolution |
|---|---|---|---|
| FM-01 | Reality Contamination | Fictional data in reality capture | Remove — re-capture from verified sources |
| FM-02 | Overgeneralization | Instance data retained in schema | Strip all specific values — re-generalize |
| FM-03 | Variant Duplication | Multiple variants share same profile | Redesign duplicated variants for diversity |
| FM-04 | Expansion Incompatibility | Expanded fields contradict base identity | Revise expansion — re-validate against base |
| FM-05 | Identity Destruction | Mutation removes archetype recognizability | Constrain mutation — preserve core identity |
| FM-06 | Library Homogeneity | Library objects insufficiently diverse | Regenerate with explicit diversity constraints |
| FM-07 | Relationship Drift | Relationships defined implicitly | Redefine all relationships explicitly |
| FM-08 | Validation Gap | Inconsistencies not detected before acceptance | Re-run validation — produce full report |
| FM-09 | Fragment Misinterpretation | Chatbot incorrectly reconstructs workflow | Confirm reconstruction with Human before proceeding |
| FM-10 | Layer Contamination | Implementation details mixed into schema design | Separate layers — review Layer Isolation requirement |

---

## 29. CONVERGENCE STANDARD

TreeSpec Skills aims for **construction convergence**:

If two independent Chatbots follow the same protocol with the same Human inputs, they SHALL produce **compatible TreeData**.

When outputs diverge:
- The protocol SHALL be examined for ambiguity
- The ambiguous section SHALL be refined
- Expected outputs SHALL NOT be manually normalized

---

## 30. FINAL PRINCIPLE

TreeSpec Skills standardizes the collaboration between Human and Chatbot.

It does not define a specific project.
It does not define implementation.
It does not define model behavior.

It defines a **repeatable construction protocol** capable of transforming fragmented Human knowledge into structured, reusable, and consistent TreeData.

Any Chatbot conforming to this protocol SHALL be able to:

- understand fragmented instructions
- reconstruct missing construction steps
- identify missing information
- recommend structural improvements
- validate consistency
- collaborate with the Human
- produce compatible TreeData regardless of the underlying AI model

---

## TREESPEC SKILLS — MASTER SUMMARY

```
Human Knowledge
  ↓
Objective Understanding
  ↓
Part I: Foundation
  → Identity · Purpose · Mission · Scope
  → Axioms · Roles · Principles
  ↓
Part II: Construction Skills
  ↓
  SKILL 01: Reality Capture          → TreeData_Reality
  SKILL 02: Schema Generalization    → TreeData_Key_None
  SKILL 03: Basic Variant Generation → Key_Basic_Library
  SKILL 04: Full Variant Expansion   → Key_Full_Library
  SKILL 05: Controlled Mutation      → Key_Mutation_Library
  SKILL 06: Library Expansion        → Key_Full_Library (large)
  SKILL 07: Relationship Construction → Relationship_Nodes
  SKILL 08: Consistency Validation   → Validation_Report
  ↓
Part III: Review & Collaboration
  → Self-Review · Missing Information Report
  → Loopback (if needed)
  → Human Approval
  ↓
Reusable TreeData
```

---

*End of TreeSpec Skills v2.0*
*Protocol: Human–Chatbot Construction | Standard: Stable Draft*
