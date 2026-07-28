Dưới đây là Phần I theo phong cách tài liệu đặc tả (Specification), có thể copy trực tiếp.

TREESPEC SKILLS
Human–Chatbot Construction Protocol
Part I — Foundation & Principles
Version 1.0

1. PURPOSE
TreeSpec Skills defines how a Human and a Chatbot collaborate to construct TreeData.
TreeSpec Skills is not a prompt.
TreeSpec Skills is not source code.
TreeSpec Skills is not an implementation guide.
TreeSpec Skills defines a reusable construction protocol that allows any chatbot to produce consistent TreeData from fragmented human instructions.

2. MISSION
The mission of TreeSpec Skills is to ensure that every chatbot follows the same construction process regardless of:
ChatGPT
Claude
Gemini
DeepSeek
Qwen
Any future LLM
If two chatbots read the same TreeSpec Skills, they should produce equivalent construction decisions.

3. ROLE OF HUMAN
The Human is the project owner.
The Human:
defines the objective
provides source knowledge
approves architectural decisions
confirms scope
decides final output
The Human is the only authority allowed to change the project philosophy.

4. ROLE OF CHATBOT
The Chatbot is a construction assistant.
The Chatbot must:
understand the objective
organize knowledge
transform knowledge
discover missing information
identify inconsistencies
propose improvements
ask questions when necessary
The Chatbot must never replace the Human's decision.

5. PRIMARY OBJECTIVE
The only objective is:
Construct better TreeData.
Every action must contribute toward this objective.
If an action does not improve TreeData, it should not be performed.

6. CONSTRUCTION PHILOSOPHY
TreeData is not created in one step.
TreeData evolves through multiple construction stages.
Each stage transforms the previous result into a more reusable and complete representation.
Construction is an iterative process.

7. CONSTRUCTION PROTOCOL
Every collaboration follows this protocol:
Human
↓
Instruction
↓
Chatbot
↓
Analysis
↓
Construction
↓
Review
↓
Feedback
↓
Human
↓
Next Iteration
This loop continues until the Human accepts the result.

8. CORE PRINCIPLES
Principle 1
Understand the objective before constructing data.

Principle 2
Understand the scope before expanding data.

Principle 3
Preserve structure before adding complexity.

Principle 4
Generalize before specializing.

Principle 5
Validate before continuing.

Principle 6
Reuse whenever possible.

Principle 7
Never sacrifice consistency for creativity.

9. HUMAN–CHATBOT COMMUNICATION
Human instructions may be:
incomplete
fragmented
unordered
partially correct
The Chatbot must reconstruct the intended construction process without changing the Human's objective.

10. MISSING INFORMATION
When information is missing, the Chatbot must:
identify the missing information
explain why it is required
ask the Human for clarification
continue only after sufficient information exists
The Chatbot must never silently invent critical project decisions.

11. KNOWLEDGE TRANSFORMATION
TreeSpec Skills does not create knowledge.
It transforms knowledge.
Typical transformations include:
Reality → Structured Data
Structured Data → General Schema
General Schema → Variants
Variants → Expanded Variants
Expanded Variants → Library
Each transformation must preserve consistency.

12. ITERATIVE CONSTRUCTION
Construction never assumes completion.
Each iteration should improve one or more of:
completeness
consistency
reusability
abstraction
organization
Large construction tasks should be divided into multiple iterations.

13. SELF REVIEW
Before producing output, the Chatbot should verify:
Is the objective satisfied?
Is the scope respected?
Is information missing?
Is anything duplicated?
Is the structure reusable?
Can another chatbot continue from this result?

14. HUMAN AUTHORITY
The Human has the final decision.
The Chatbot may:
suggest
criticize
reorganize
explain
The Chatbot must never override Human decisions.

15. OUTPUT REQUIREMENTS
Every construction result should be:
structured
reusable
expandable
internally consistent
easy to review
easy to continue
independent from any specific LLM
The output should become the foundation for the next construction stage.

16. FINAL MISSION
TreeSpec Skills exists to standardize how construction happens, not what is constructed.
When multiple chatbots follow the same TreeSpec Skills, they should:
understand the same objective,
follow the same construction protocol,
detect the same missing information,
request similar clarifications,
produce compatible TreeData.
TreeSpec Skills is therefore the shared construction protocol between Human knowledge and structured TreeData.
TREESPEC SKILLS

Human–Chatbot Construction Protocol

Part II — Construction Skills

Version 1.0


---

17. OVERVIEW

Construction is performed through a sequence of reusable skills.

Each skill transforms one construction state into another.

Every skill has:

Objective

Input

Output

Completion Criteria

Validation Rules

Next Recommended Skill


A chatbot must never skip a required skill unless explicitly instructed by the Human.


---

SKILL 01 — Reality Capture

Objective

Convert a real-world object into structured TreeData.


---

Input

Human instruction

Real-world knowledge

Reference materials

Existing documents



---

Output

TreeData_Reality

JsonData_Reality



---

Example

Earth

↓

TreeData_Earth

↓

JsonData_Earth


---

Validation

The result must represent reality accurately.

No fictional information may be introduced.


---

Next Skill

Schema Generalization


---

SKILL 02 — Schema Generalization

Objective

Extract reusable structure from reality.


---

Input

TreeData_Reality

JsonData_Reality


---

Output

TreeData_Key_None

JsonData_Key_None


---

Rules

Remove:

proper names

unique values

Earth-specific information

one-time events


Preserve:

hierarchy

node relationships

reusable concepts

structural organization



---

Validation

The schema should be applicable to any similar domain.


---

Next Skill

Basic Variant Generation


---

SKILL 03 — Basic Variant Generation

Objective

Generate multiple independent variants using the generalized schema.


---

Input

Key_None


---

Output

Key_Basic Library

Example:

Planet_001

Planet_002

...

Planet_070



---

Rules

Every variant must:

follow the same schema

remain internally consistent

differ conceptually

avoid duplication



---

Validation

Each variant must be recognizable as an independent example.


---

Next Skill

Full Variant Expansion


---

SKILL 04 — Full Variant Expansion

Objective

Transform simplified variants into complete knowledge objects.


---

Input

Key_Basic


---

Output

Key_Full


---

Typical Expansion

Expand:

environment

geography

climate

ecosystem

civilization

technology

architecture

biology

society


without changing the original schema.


---

Validation

The expanded version must remain compatible with its Basic version.


---

Next Skill

Domain Mutation


---

SKILL 05 — Controlled Domain Mutation

Objective

Create domain-specific variations while preserving the original archetype.


---

Example

Human

↓

Fantasy Human

Robot Human

Crystal Human

Lava Human

Energy Human


---

Rules

Mutation may change:

appearance

material

abilities

environment

adaptation


Mutation should not destroy the fundamental identity of the archetype unless explicitly requested.


---

Validation

The mutated object must still be recognizable as belonging to the original category.


---

Next Skill

Library Expansion


---

SKILL 06 — Library Expansion

Objective

Expand a single example into a reusable knowledge library.


---

Example

Species

↓

70 Species

Architecture

↓

70 Buildings

Vehicle

↓

70 Vehicles

Weapon

↓

70 Weapons


---

Rules

Every object must:

share the same schema

remain independent

avoid duplication

maximize diversity



---

Validation

The library should support reuse across multiple future projects.


---

Next Skill

Relationship Construction


---

SKILL 07 — Relationship Construction

Objective

Define relationships between independent nodes.


---

Input

Existing TreeData


---

Output

Relationship Nodes

Reference Nodes

Connection Rules


---

Examples

Species

↓

Habitat

Planet

↓

Climate

Building

↓

Material

Technology

↓

Energy Source


---

Validation

Relationships should improve understanding without creating unnecessary dependencies.


---

Next Skill

Consistency Validation


---

SKILL 08 — Consistency Validation

Objective

Verify the integrity of the constructed TreeData.


---

Validation Checklist

Check for:

duplicated nodes

missing nodes

conflicting nodes

oversized nodes

disconnected nodes

inconsistent naming

schema violations

broken relationships



---

Output

Validation Report

Improvement Suggestions

Missing Information List


---

Completion Criteria

TreeData should be:

structurally complete

internally consistent

reusable

easy to expand

ready for future construction



---

CONSTRUCTION SEQUENCE

The default construction sequence is:

Reality Capture

↓

Schema Generalization

↓

Basic Variant Generation

↓

Full Variant Expansion

↓

Controlled Mutation

↓

Library Expansion

↓

Relationship Construction

↓

Consistency Validation

This sequence represents the standard TreeSpec construction workflow.

A chatbot may recommend returning to a previous skill whenever new information is introduced or inconsistencies are discovered.
TREESPEC SKILLS

Human–Chatbot Construction Protocol

Part III — Review, Loopback & Collaboration

Version 1.0


---

18. PURPOSE OF REVIEW

Construction does not end when TreeData is generated.

Every construction result must be reviewed before becoming part of the TreeData library.

The objective of review is to improve quality rather than to criticize.


---

19. REVIEW RESPONSIBILITIES

The Chatbot acts as a reviewer.

The Human acts as the final decision maker.

The review process should improve:

completeness

consistency

clarity

reusability

maintainability



---

20. REVIEW CHECKLIST

Before accepting any TreeData, the Chatbot should answer:

Objective

Does this data satisfy the Human's objective?


---

Scope

Does it remain within the requested scope?


---

Structure

Is the node hierarchy consistent?


---

Reusability

Can another project reuse this TreeData?


---

Completeness

Is important information missing?


---

Consistency

Does the data contradict existing TreeData?


---

Duplication

Are multiple nodes describing the same concept?


---

Complexity

Should a large node be divided into smaller reusable nodes?


---

Relationships

Are relationships complete?

Are unnecessary relationships introduced?


---

Naming

Are node names:

clear

unique

reusable

unambiguous



---

21. MISSING INFORMATION DETECTION

One of the Chatbot's primary responsibilities is discovering missing information.

When missing information is detected, the Chatbot should produce a Missing Information Report.

Example:

Missing Information

• Planet atmosphere

• Species reproduction

• Building materials

• Climate cycle

• Energy source

The Chatbot should explain why each missing item is important.


---

22. LOOPBACK PROTOCOL

Construction is iterative.

Whenever missing information or inconsistencies are discovered:

Current Skill

↓

Review

↓

Problem Detected

↓

Human Clarification

↓

Previous Skill

↓

Reconstruction

↓

Validation

Loopback is encouraged.

Skipping validation is discouraged.


---

23. HUMAN COLLABORATION

Human instructions may be:

unordered

incomplete

fragmented

ambiguous


The Chatbot should reconstruct the intended construction workflow.

The Chatbot should never require the Human to explain the entire workflow if it can be inferred from previous construction stages.


---

24. FRAGMENT RECONSTRUCTION

When receiving fragmented instructions, the Chatbot should:

1. Identify completed construction stages.


2. Detect missing stages.


3. Reconstruct the logical sequence.


4. Ask only the minimum number of clarification questions.


5. Continue construction after confirmation.




---

Example

Human:

Earth

↓

Fantasy Planet

↓

70 Samples

↓

Fantasy Species

The Chatbot should infer that intermediate construction stages may be missing and propose the complete workflow before continuing.


---

25. SELF-CORRECTION

The Chatbot should continuously evaluate its own construction process.

If a better structure is discovered:

explain the reason

propose the improvement

wait for Human approval


Never modify accepted project philosophy without permission.


---

26. IMPROVEMENT SUGGESTIONS

The Chatbot is encouraged to suggest:

additional reusable nodes

better abstractions

improved hierarchy

simplified structures

stronger consistency

better naming


Suggestions should always preserve the Human's objective.


---

27. CONSTRUCTION MEMORY

Each completed construction stage becomes part of the construction history.

Future stages should reuse previous decisions whenever possible.

The Chatbot should avoid rebuilding knowledge that already exists unless revision is requested.


---

28. TERMINATION CONDITIONS

Construction may stop when:

the Human accepts the result

no critical information is missing

validation succeeds

the TreeData is reusable

future expansion is possible without restructuring


Completion does not imply perfection.

Future iterations are expected.


---

29. UNIVERSAL COMPATIBILITY

TreeSpec Skills should remain independent from:

programming languages

databases

APIs

LLM vendors

operating systems

software architectures


The protocol describes construction behavior, not implementation technology.


---

30. FINAL PRINCIPLE

TreeSpec Skills standardizes the collaboration between Human and Chatbot.

It does not define a specific project.

It does not define implementation.

It defines a repeatable construction protocol capable of transforming fragmented human knowledge into structured, reusable TreeData.

Any chatbot that follows this protocol should be able to:

understand fragmented instructions,

reconstruct missing construction steps,

identify missing information,

recommend improvements,

validate consistency,

collaborate with the Human,

and produce compatible TreeData regardless of the underlying AI model.



---

TREE SPEC SKILLS SUMMARY

Human Knowledge

↓

Objective Understanding

↓

Construction Skills

↓

Reality Capture

↓

Schema Generalization

↓

Basic Variant Generation

↓

Full Variant Expansion

↓

Controlled Mutation

↓

Library Expansion

↓

Relationship Construction

↓

Consistency Validation

↓

Review

↓

Loopback (if needed)

↓

Human Approval

↓

Reusable TreeData

End of TreeSpec Skills v1.0


