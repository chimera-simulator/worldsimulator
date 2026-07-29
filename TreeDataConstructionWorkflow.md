

TreeData Construction Workflow

Version: 1.0

Type: Knowledge Construction Workflow


---

OBJECTIVE

Chuẩn hóa quy trình thu thập, xây dựng, xác minh, hợp nhất và duy trì TreeData.

Đầu ra cuối cùng luôn là một TreeData có cấu trúc, nhất quán và có thể tái sử dụng.


---

INPUT

Nguồn tri thức có thể bao gồm:

Internet

Sách

Tài liệu

Paper

Video

Hình ảnh

JSON

Database

API

Human Knowledge

Existing TreeData



---

OUTPUT

Một hoặc nhiều TreeData hoàn chỉnh.

Ví dụ:

Planet

Creature

Technology

Architecture

Culture

Weapon

Story

Language


---

CONSTRUCTION WORKFLOW

Acquire

↓

Screen

↓

Extract

↓

Normalize

↓

Decompose

↓

Structure

↓

Relationship

↓

Validate

↓

Merge

↓

Review

↓

Version

↓

Publish


---

PHASE 1

Acquire

Thu thập tri thức.

Input

↓

Raw Knowledge

Output

↓

Candidate Knowledge


---

PHASE 2

Screen

Loại bỏ

Spam

Duplicate

Noise

Low Quality

Irrelevant


Output

↓

Verified Sources


---

PHASE 3

Extract

Trích xuất

Concept

Attribute

Rule

Pattern

Relationship

Example


Output

↓

Knowledge Units


---

PHASE 4

Normalize

Chuẩn hóa

Ví dụ

colour

↓

color

AI

↓

Artificial Intelligence

Humanoid

↓

Species Type

Output

↓

Normalized Knowledge


---

PHASE 5

Decompose

Phân rã thành node.

Ví dụ

Creature

↓

Body

↓

Organ

↓

Eye

↓

Crystal Lens

Output

↓

Knowledge Nodes


---

PHASE 6

Structure

Tổ chức thành cây.

Ví dụ

Planet

↓

Biome

↓

Creature

↓

Behavior

Output

↓

TreeData Draft


---

PHASE 7

Relationship

Tạo liên kết

Ví dụ

Creature

↓

Habitat

↓

Planet

Weapon

↓

Technology

Culture

↓

Species

Output

↓

Knowledge Graph


---

PHASE 8

Validate

Kiểm tra

Missing Node

Broken Relationship

Duplicate

Invalid Attribute

Empty Branch

Circular Reference

Canon Conflict


Output

↓

Validated Tree


---

PHASE 9

Merge

Hợp nhất

TreeData A


TreeData B

↓

Merged TreeData

Giữ

Canon

Version

Relationship



---

PHASE 10

Review

Leader Review

↓

QA Review

↓

Human Review (optional)

↓

Approved


---

PHASE 11

Version

Sinh

Version

Revision

History

Change Log

Compatibility


---

PHASE 12

Publish

Xuất

TreeData

↓

Library

↓

Repository

↓

Database

↓

Release


---

QUALITY GATES

Mỗi Phase phải vượt QA trước khi sang Phase tiếp theo.

Ví dụ:

Acquire
✓

↓

Screen
✓

↓

Extract
✓

↓

...


---

LOOPBACK

Nếu QA thất bại

Validate

↓

Failed

↓

Return Previous Phase

↓

Fix

↓

Validate Again


---

GENERAL RULES

Không sửa tri thức gốc nếu chưa xác minh.

Không hợp nhất khi còn xung đột.

Mỗi node chỉ có một ý nghĩa chính.

Mỗi quan hệ phải có ngữ nghĩa rõ ràng.

Ưu tiên tái sử dụng node hiện có.

Mọi thay đổi phải có lịch sử phiên bản.

TreeData luôn phải có khả năng mở rộng mà không phá vỡ cấu trúc cũ.



---
