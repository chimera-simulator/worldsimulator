"""
t4_deduplicate.py — Agent 5b: Dedup theo Visual Identity
===========================================================
[CX]
- Dedup key CHÍNH = Visual_ID (không còn content_hash như bản cũ). Dedup
  key PHỤ = similarity trên pre_built_prompts.full_character.
- Không tự động merge nếu 2 document cùng visual_id nhưng nội dung prompt
  sai khác quá lớn — phải đánh cờ "manual_review_needed" để con người review.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Dict, List

from config import DEDUP_SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)


def compute_visual_id(blueprint: dict) -> str:
    """hash(species_base.prompt_fragment + skin.prompt_fragment) ->
    sha256 hex, rút gọn theo convention 'VB_<ENTITY>_<hash8>'."""
    character = blueprint.get("character_blueprint", {}) or {}
    species_base = character.get("species_base", {}) or {}
    physical = character.get("physical_attributes", {}) or {}
    skin = physical.get("skin", {}) or {}

    seed_text = (
        species_base.get("prompt_fragment", "") + "|" + skin.get("prompt_fragment", "")
    )

    if not seed_text.strip("|"):
        # Fallback: nếu không có species/skin (vd entity_type=architecture),
        # dùng toàn bộ character_blueprint + clothing_and_gear serialized.
        seed_text = str(character) + str(blueprint.get("clothing_and_gear", {}))

    digest = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:8]
    entity_type = blueprint.get("entity_type", "unknown").upper()
    return f"VB_{entity_type}_{digest}"


def compute_prompt_similarity(prompt_a: str, prompt_b: str) -> float:
    """TF-IDF cosine similarity trên pre_built_prompts.full_character."""
    if not prompt_a or not prompt_b:
        return 0.0

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vectorizer = TfidfVectorizer().fit([prompt_a, prompt_b])
        vectors = vectorizer.transform([prompt_a, prompt_b])
        return float(cosine_similarity(vectors[0], vectors[1])[0][0])
    except Exception as e:
        logger.warning(f"⚠️ [T4] sklearn không khả dụng, fallback so khớp thô: {e}")
        # Fallback: Jaccard similarity trên set từ.
        set_a, set_b = set(prompt_a.lower().split()), set(prompt_b.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)


def _count_completed_fields(gap_status: dict) -> int:
    return sum(
        1
        for key, value in (gap_status or {}).items()
        if key.endswith("_completed") and value is True
    )


def deduplicate(
    validated_docs: List[dict], existing_visual_ids: Dict[str, dict]
) -> List[dict]:
    """
    1. Với mỗi doc -> visual_id = compute_visual_id(doc["blueprint"]).
    2. Nếu visual_id đã tồn tại: so sánh gap_filling_status, merge nếu
       similarity đủ cao, ngược lại flag manual_review_needed.
    3. Nếu mới -> pass thẳng, thêm vào existing_visual_ids cho batch hiện tại.
    4. Return List[deduped_documents].
    """
    output: List[dict] = []

    for doc in validated_docs:
        if doc.get("reject_reason"):
            # Document đã bị reject ở Gate 5 -> không đưa vào dedup/upload.
            continue

        blueprint = doc.get("blueprint")
        if not blueprint:
            continue

        visual_id = compute_visual_id(blueprint)
        doc["visual_id"] = visual_id
        blueprint["visual_id"] = visual_id

        if visual_id in existing_visual_ids:
            existing_doc = existing_visual_ids[visual_id]
            existing_blueprint = existing_doc.get("blueprint", {})

            new_prompt = (blueprint.get("pre_built_prompts", {}) or {}).get("full_character", "")
            existing_prompt = (existing_blueprint.get("pre_built_prompts", {}) or {}).get(
                "full_character", ""
            )
            similarity = compute_prompt_similarity(new_prompt, existing_prompt)

            if similarity < DEDUP_SIMILARITY_THRESHOLD:
                doc["manual_review_needed"] = True
                logger.warning(
                    f"⚠️ [T4] '{visual_id}' trùng ID nhưng prompt khác biệt lớn "
                    f"(similarity={similarity:.2f}) — flag manual_review_needed, KHÔNG merge."
                )
                output.append(doc)
                continue

            # Merge gap_filling_status: giữ bản có nhiều field completed hơn,
            # union pending_fields.
            existing_gap = existing_blueprint.get("metadata", {}).get("gap_filling_status", {})
            new_gap = blueprint.get("metadata", {}).get("gap_filling_status", {})

            existing_score = _count_completed_fields(existing_gap)
            new_score = _count_completed_fields(new_gap)

            merged_gap = dict(existing_gap if existing_score >= new_score else new_gap)
            merged_gap["pending_fields"] = list(
                set(existing_gap.get("pending_fields", []))
                | set(new_gap.get("pending_fields", []))
            )

            merged_blueprint = existing_blueprint if existing_score >= new_score else blueprint
            merged_blueprint.setdefault("metadata", {})["gap_filling_status"] = merged_gap

            doc["blueprint"] = merged_blueprint
            doc["merged"] = True
            existing_visual_ids[visual_id] = doc
            logger.info(f"🔀 [T4] '{visual_id}' merged (existing_score={existing_score}, new_score={new_score}).")
            output.append(doc)
        else:
            existing_visual_ids[visual_id] = doc
            output.append(doc)

    logger.info(f"✅ [T4] Dedup hoàn thành — {len(output)}/{len(validated_docs)} document giữ lại.")
    return output


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
