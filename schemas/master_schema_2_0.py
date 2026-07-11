"""
schemas/master_schema_2_0.py — Pydantic model cho Master Schema 2.0
=====================================================================
Không thêm field nào ngoài spec §28.3. Nếu cần mở rộng, phải version
bump lên "2.1" chứ không âm thầm thêm field vào "2.0".
"""
from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


class PlanetIdentity(BaseModel):
    planet_type: str = ""
    core_material: str = ""
    physical_appearance: List[str] = Field(default_factory=list)
    terrain_patterns: List[str] = Field(default_factory=list)
    climate_patterns: List[str] = Field(default_factory=list)
    energy_sources: List[str] = Field(default_factory=list)
    natural_resources: List[str] = Field(default_factory=list)
    planetary_hazards: List[str] = Field(default_factory=list)
    planetary_phenomena: List[str] = Field(default_factory=list)


class EcosystemFoundation(BaseModel):
    dominant_ecosystem: List[str] = Field(default_factory=list)
    dominant_life_material: str = ""
    food_chain_patterns: List[str] = Field(default_factory=list)
    ecological_cycles: List[str] = Field(default_factory=list)
    environmental_adaptations: List[str] = Field(default_factory=list)


class Form1PlanetFoundation(BaseModel):
    planet_identity: PlanetIdentity = Field(default_factory=PlanetIdentity)
    ecosystem_foundation: EcosystemFoundation = Field(default_factory=EcosystemFoundation)


class BiologyAndBehavior(BaseModel):
    species_morphology: List[str] = Field(default_factory=list)
    species_behavior: List[str] = Field(default_factory=list)


class SocietyAndInfrastructure(BaseModel):
    architecture_patterns: List[str] = Field(default_factory=list)
    transportation_patterns: List[str] = Field(default_factory=list)
    technology_patterns: List[str] = Field(default_factory=list)
    government_patterns: List[str] = Field(default_factory=list)
    economic_patterns: List[str] = Field(default_factory=list)
    military_patterns: List[str] = Field(default_factory=list)


class CultureAndHistory(BaseModel):
    religion_and_belief: List[str] = Field(default_factory=list)
    cultural_patterns: List[str] = Field(default_factory=list)
    language_patterns: List[str] = Field(default_factory=list)
    art_patterns: List[str] = Field(default_factory=list)
    daily_life_patterns: List[str] = Field(default_factory=list)
    historical_patterns: List[str] = Field(default_factory=list)
    diplomatic_patterns: List[str] = Field(default_factory=list)


class Form2CivilizationLayer(BaseModel):
    biology_and_behavior: BiologyAndBehavior = Field(default_factory=BiologyAndBehavior)
    society_and_infrastructure: SocietyAndInfrastructure = Field(
        default_factory=SocietyAndInfrastructure
    )
    culture_and_history: CultureAndHistory = Field(default_factory=CultureAndHistory)


class ProvenanceAndMetadata(BaseModel):
    target_form_field: str
    search_strategy_used: str = ""
    extracted_from_domain: str = ""
    ip_filter_status: Literal["cleaned", "unverified", "failed"] = "unverified"
    original_ip_detected: List[str] = Field(default_factory=list)
    quality_gate_passed: bool = False
    timestamp: str = ""  # ISO8601


class MasterSchema20(BaseModel):
    schema_version: Literal["2.0"] = "2.0"
    document_type: Literal["worldbuilding_design_pattern"] = "worldbuilding_design_pattern"
    form_1_planet_foundation: Form1PlanetFoundation = Field(
        default_factory=Form1PlanetFoundation
    )
    form_2_civilization_layer: Form2CivilizationLayer = Field(
        default_factory=Form2CivilizationLayer
    )
    provenance_and_metadata: ProvenanceAndMetadata
