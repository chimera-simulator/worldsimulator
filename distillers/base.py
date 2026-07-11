"""
distillers/base.py — BaseLibraryDistiller (Template Method)
=============================================================
Chứa phần logic KHÔNG đổi theo library_type, tái dùng nguyên các hàm đã
có trong t4_5_library_distill.py (generate_entity_id, structure_via_llm)
để không tạo 2 nguồn sự thật.

Import ngược từ t4_5_library_distill.py là CÓ CHỦ ĐÍCH (những hàm đó vẫn
ở nguyên chỗ cũ, KHÔNG di chuyển — xem mục "KHÔNG đổi" đầu SPEC). Để
tránh circular import ở module-load time (t4_5_library_distill.py import
DistillerRegistry từ distillers/registry.py, còn base.py cần các hàm
generate_entity_id/structure_via_llm từ t4_5_library_distill.py), import
được thực hiện LAZY bên trong distill() thay vì ở đầu file — đúng
convention lazy-import đã dùng cho _get_call_gemini() trong file gốc.
"""
from __future__ import annotations

import copy
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import ClassVar, Optional

from schemas.lib_entity import LibConsistencyLock, LibEntity, SourceProvenance

logger = logging.getLogger(__name__)


class BaseLibraryDistiller(ABC):
    """Lớp cha cho mọi Distiller theo library_type.

    Subclass BẮT BUỘC khai báo:
        library_type: ClassVar[str]
        required_fields: ClassVar[list[str]]
    và override:
        _extract_payload(self, blueprint: dict) -> dict
    """

    library_type: ClassVar[str] = ""
    required_fields: ClassVar[list] = []

    # -------------------------------------------------------------------
    # TEMPLATE METHOD — KHÔNG override ở subclass.
    # -------------------------------------------------------------------
    def distill(
        self,
        doc: dict,
        budget=None,
        obs=None,
    ) -> dict:
        """Distill 1 doc (đã được route_library_type() xác định đúng
        library_type của class này) thành lib_record đã flatten.

        Nhận `doc` đầy đủ (không chỉ blueprint/schema_record riêng lẻ)
        vì entity_id và source_provenance cần visual_id — tái dùng đúng
        chữ ký mà generate_entity_id()/distill_one() cũ đang dùng, tránh
        phải truyền thêm tham số rời rạc.
        """
        # Lazy import để tránh circular (base.py <-> t4_5_library_distill.py)
        from t4_5_library_distill import generate_entity_id, structure_via_llm

        visual_id = doc.get("visual_id", "unknown")
        blueprint = doc.get("blueprint") or {}
        schema_record = doc.get("schema_record")

        # Bước 1: entity_id (tái dùng nguyên)
        entity_id = generate_entity_id(self.library_type, doc)

        # Bước 2: payload — phần duy nhất subclass tự quyết định
        payload = self._extract_payload(blueprint)

        # Bước 3: tách prompt_keywords/negative_prompt khỏi payload
        # (pre_built_prompts luôn ưu tiên — logic dùng chung mọi library_type,
        # đặt ở đây thay vì lặp lại trong từng subclass)
        payload = dict(payload)  # tránh mutate payload gốc nếu subclass share state
        prompt_keywords = payload.pop("prompt_keywords", "") or self._extract_prompt_keywords(blueprint)
        negative_prompt = payload.pop("negative_prompt", "") or self._extract_negative_prompt(blueprint)

        # Bước 4: missing required fields (kiểm cả payload lẫn prompt_keywords
        # vì "prompt_keywords" là required_fields phổ biến nhưng đã bị tách
        # ra khỏi payload ở bước 3)
        merged_for_check = dict(payload)
        merged_for_check["prompt_keywords"] = prompt_keywords
        missing = [f for f in self.required_fields if not merged_for_check.get(f)]

        # Bước 5: LLM fallback nếu còn thiếu và có schema_record
        # (tái dùng NGUYÊN structure_via_llm() — không đổi chữ ký/hành vi)
        llm_used = False
        if missing and schema_record is not None:
            llm_fields = structure_via_llm(schema_record, missing, budget, obs)
            if llm_fields:
                for k, v in llm_fields.items():
                    if k == "prompt_keywords":
                        prompt_keywords = prompt_keywords or v
                    elif k == "negative_prompt":
                        negative_prompt = negative_prompt or v
                    else:
                        payload[k] = v
                merged_for_check = dict(payload)
                merged_for_check["prompt_keywords"] = prompt_keywords
                missing = [f for f in self.required_fields if not merged_for_check.get(f)]
                llm_used = len(llm_fields) > 0

        status = "incomplete" if missing else "complete"
        if status == "complete":
            logger.info(
                f"✅ [Gate 6.5] '{entity_id}' ({self.library_type}) — "
                f"status=complete, llm_used={llm_used}."
            )
        else:
            logger.info(
                f"⚠️ [Gate 6.5] '{entity_id}' ({self.library_type}) — "
                f"status=incomplete, thiếu: {missing}."
            )

        # Bước 6: consistency_lock — copy nguyên từ blueprint (KHÔNG tính lại)
        raw_lock = blueprint.get("consistency_lock") or {}
        if hasattr(raw_lock, "model_dump"):
            lock_dict = raw_lock.model_dump()
        elif isinstance(raw_lock, dict):
            lock_dict = raw_lock
        else:
            lock_dict = {}
        consistency_lock = LibConsistencyLock(
            locked_fields=lock_dict.get("locked_fields", []),
            variable_fields=lock_dict.get("variable_fields", []),
        )

        # Bước 7: origin_provenance (Gap B) — copy NGUYÊN provenance_and_metadata
        origin_provenance = self._attach_origin_provenance(schema_record)

        # Bước 8: source_provenance (metadata của hành động distill — KHÁC
        # origin_provenance, xem mục 0.3 tài liệu Architect)
        schema_refs: list[str] = []
        if schema_record is not None:
            raw_id = schema_record.get("_id")
            if raw_id is not None:
                schema_refs = [str(raw_id)]
            else:
                logger.info(
                    f"   [Gate 6.5] schema_record của '{visual_id}' chưa có _id "
                    f"— schema_record_refs sẽ là []."
                )

        ip_status = "unverified"
        if schema_record is not None:
            ip_status = (
                (schema_record.get("provenance_and_metadata") or {})
                .get("ip_filter_status", "unverified")
            ) or "unverified"

        source_provenance = SourceProvenance(
            visual_blueprint_ref=visual_id,
            schema_record_refs=schema_refs,
            distilled_by="t4_5_library_distill",
            distilled_at=datetime.now(timezone.utc).isoformat(),
            llm_structuring_used=llm_used,
            ip_filter_status=ip_status,
        )

        # Bước 9: build LibEntity + flatten
        lib_entity = LibEntity(
            library_type=self.library_type,
            entity_id=entity_id,
            status=status,
            payload=payload,
            prompt_keywords=prompt_keywords,
            negative_prompt=negative_prompt,
            source_provenance=source_provenance,
            origin_provenance=origin_provenance,
            consistency_lock=consistency_lock,
            missing_required_fields=missing,
            schema_version="lib_1.0",
        )
        return self._flatten(lib_entity)

    # -------------------------------------------------------------------
    # ABSTRACT — mỗi Distiller con BẮT BUỘC override
    # -------------------------------------------------------------------
    @abstractmethod
    def _extract_payload(self, blueprint: dict) -> dict:
        """Trích payload thô (chưa check required_fields) từ blueprint,
        đặc thù theo library_type. Đây là phần code trước đây nằm trong
        từng nhánh if/elif của extract_from_blueprint()."""
        raise NotImplementedError

    # -------------------------------------------------------------------
    # CONCRETE — dùng chung cho MỌI Distiller, KHÔNG override
    # -------------------------------------------------------------------
    def _extract_prompt_keywords(self, blueprint: dict) -> str:
        pre_built = blueprint.get("pre_built_prompts") or {}
        return pre_built.get("full_character") or pre_built.get("character") or ""

    def _extract_negative_prompt(self, blueprint: dict) -> str:
        pre_built = blueprint.get("pre_built_prompts") or {}
        return pre_built.get("negative") or pre_built.get("negative_prompt") or ""

    def _attach_origin_provenance(self, schema_record: Optional[dict]) -> dict:
        """Gap B — copy NGUYÊN schema_record['provenance_and_metadata'].

        Luôn trả dict (rỗng {} nếu không có nguồn) — KHÔNG bao giờ None,
        để Repo 3/4 đọc field với shape ổn định (mục 2.3 tài liệu Architect).
        deepcopy để đảm bảo không ai vô tình mutate ngược lên schema_record
        gốc qua reference dùng chung.
        """
        if schema_record is None:
            return {}
        raw = schema_record.get("provenance_and_metadata")
        if not raw:
            logger.info(
                "   [Gate 6.5] schema_record thiếu 'provenance_and_metadata' "
                "(dữ liệu cũ chưa có field này) — origin_provenance = {}."
            )
            return {}
        return copy.deepcopy(raw)

    def _flatten(self, lib_entity: LibEntity) -> dict:
        """Flatten LibEntity → dict Mongo-ready. Giữ nguyên hành vi
        _flatten_lib_record() cũ, thêm origin_provenance vào base."""
        base = {
            "library_type": lib_entity.library_type,
            "entity_id": lib_entity.entity_id,
            "status": lib_entity.status,
            "prompt_keywords": lib_entity.prompt_keywords,
            "negative_prompt": lib_entity.negative_prompt,
            "source_provenance": lib_entity.source_provenance.model_dump(),
            "origin_provenance": lib_entity.origin_provenance,
            "consistency_lock": lib_entity.consistency_lock.model_dump(),
            "missing_required_fields": lib_entity.missing_required_fields,
            "schema_version": lib_entity.schema_version,
        }
        for k, v in lib_entity.payload.items():
            if k not in base:
                base[k] = v
        return base
