"""Actual owner persistence/projection conformance, not HTTP authorisation.

Runs inside the pinned Pulse image against separate PostgreSQL and Qdrant
servers. No embedded vector store or substitute provider is allowed. This
necessary evidence cannot promote L4-CP-02: real caller/CP qualification and
independent certification remain separate. Only fixed booleans leave stdout.
"""
import asyncio
import hashlib
import json
from pathlib import Path

from baobab_pulse.api.dependencies import (
    get_database, get_evidence_repository, get_qdrant_evidence_store,
    get_evidence_retrieval_service, get_settings,
)
from baobab_pulse.application.ports.vector_projection_port import ProjectionCollection, ProjectionRecord
from baobab_pulse.domain.evidence import Evidence, EvidenceSet
from baobab_pulse.domain.shared.enums import Classification, EvidenceDirection, TenantScope
from baobab_pulse.domain.shared.value_objects import Reference, TenantContext
from baobab_pulse.tenancy.context import bind_tenant_context


async def prove():
    settings = get_settings()
    if settings.qdrant_location or not settings.qdrant_url:
        raise ValueError("actual Qdrant server required")
    fixtures = json.loads(Path("/run/l4/fixtures.json").read_text())
    tenant, neighbour = fixtures["tenant"], fixtures["other_tenant"]
    database = get_database()
    await database.connect()
    try:
        repository, vectors = get_evidence_repository(), get_qdrant_evidence_store()
        retrieval = get_evidence_retrieval_service()
        text = "INT-02 synthetic canonical evidence for provider conformance."
        document = EvidenceSet(id="evs_int02_native", purpose="disposable source qualification",
            tenant_scope=TenantScope.TENANT, tenant_context=TenantContext(tenant_id=tenant),
            classification=Classification.CONFIDENTIAL, version=1,
            entries=(Evidence(id="evd_int02_native", referenced_object=Reference(
                object_type="observation", object_id="obs_int02_native"), direction=EvidenceDirection.SUPPORTS),))
        await repository.add_with_text(document, {"evd_int02_native": text})
        await vectors.upsert_projection(ProjectionCollection.EVIDENCE, ProjectionRecord(
            canonical_object_id="evd_int02_native", evidence_set_id=document.id,
            canonical_version=1, tenant_id=tenant, classification=Classification.CONFIDENTIAL,
            content=text, content_hash=hashlib.sha256(text.encode()).hexdigest(),
            embedding_model_id="mock:mock-model", embedding_model_version="1"))
        checks = {}
        with bind_tenant_context(TenantContext(tenant_id=tenant)):
            results = await retrieval.search(text, requester_clearance=Classification.CONFIDENTIAL)
            checks["pulse_native_persisted_search"] = len(results) == 1 and results[0].canonical_object_id == "evd_int02_native" and not results[0].is_stale
            hydrated, contents = await retrieval.hydrate_for_pipeline(results)
            checks["pulse_native_canonical_hydration"] = hydrated.id == document.id and hydrated.version == 1 and contents == {"evd_int02_native": text}
            checks["pulse_native_classification_denied"] = not await retrieval.search(text, requester_clearance=Classification.PUBLIC)
        with bind_tenant_context(TenantContext(tenant_id=neighbour)):
            checks["pulse_native_neighbour_denied"] = not await retrieval.search(text, requester_clearance=Classification.CONFIDENTIAL)
        await repository.add_with_text(document.model_copy(update={"version": 2}), {"evd_int02_native": text})
        with bind_tenant_context(TenantContext(tenant_id=tenant)):
            stale = await retrieval.search(text, requester_clearance=Classification.CONFIDENTIAL)
            checks["pulse_native_stale_projection_observed"] = len(stale) == 1 and stale[0].is_stale
        # Restore a current projection for the subsequent real HTTP proof;
        # the stale observation above remains a distinct native negative.
        await vectors.upsert_projection(ProjectionCollection.EVIDENCE, ProjectionRecord(
            canonical_object_id="evd_int02_native", evidence_set_id=document.id,
            canonical_version=2, tenant_id=tenant, classification=Classification.CONFIDENTIAL,
            content=text, content_hash=hashlib.sha256(text.encode()).hexdigest(),
            embedding_model_id="mock:mock-model", embedding_model_version="1"))
        restricted = document.model_copy(update={"id":"evs_int02_restricted", "version":1,
            "classification":Classification.RESTRICTED,
            "entries":(Evidence(id="evd_int02_restricted", referenced_object=Reference(
                object_type="observation", object_id="obs_int02_restricted"), direction=EvidenceDirection.SUPPORTS),)})
        await repository.add_with_text(restricted, {"evd_int02_restricted":text})
        await vectors.upsert_projection(ProjectionCollection.EVIDENCE, ProjectionRecord(
            canonical_object_id="evd_int02_restricted", evidence_set_id=restricted.id,
            canonical_version=1, tenant_id=tenant, classification=Classification.RESTRICTED,
            content=text, content_hash=hashlib.sha256(text.encode()).hexdigest(),
            embedding_model_id="mock:mock-model", embedding_model_version="1"))
        checks["pulse_native_actual_dependencies"] = await database.is_ready() and await vectors.is_ready()
        print(json.dumps({"checks": checks}, sort_keys=True))
        if not all(value is True for value in checks.values()):
            raise ValueError("native provider conformance failed")
    finally:
        await database.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(prove())
    except Exception:
        # Even native asyncpg/Haystack exceptions can include DSNs or records.
        # The orchestrator reports only a fixed failure class, never a traceback.
        raise SystemExit(2) from None
