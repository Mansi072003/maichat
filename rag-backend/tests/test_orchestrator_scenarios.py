# tests/test_orchestrator_scenarios.py
"""
Unit tests for the MAI Agentic AI orchestrator architecture.

Covers:
  - Emergency triage short-circuit
  - Urgent triage short-circuit
  - Non-urgent triage fall-through
  - Patient context handoff to specialist agents
  - Multi-intent parallel routing (medication + lab)
  - Consent denial blocks patient-specific access
  - Citation normalization
  - Greeting short-circuit (unchanged)

All external services are mocked so tests run without Pinecone / OpenAI / Mongo.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.base_agent import AgentResponse
from agents.consent import check_patient_data_consent, ConsentResult
from pipeline.conversation_orchestrator import ConversationOrchestrator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_services():
    """Create mock service objects with the methods the orchestrator calls."""
    mongodb = AsyncMock()
    mongodb.initialize = AsyncMock()
    mongodb.health_check = AsyncMock(return_value=True)
    mongodb.close = AsyncMock()
    mongodb.create_session = AsyncMock(return_value={"session_id": "s1"})

    embedding = AsyncMock()
    embedding.initialize = AsyncMock()
    embedding.health_check = AsyncMock(return_value=True)

    retrieval = AsyncMock()
    retrieval.initialize = AsyncMock()
    retrieval.health_check = AsyncMock(return_value=True)
    retrieval.retrieve_context = AsyncMock(return_value={
        "contexts": [
            {"text": "Patient takes metformin 500mg BID.", "score": 0.92},
            {"text": "Last HbA1c was 7.1%.", "score": 0.88},
        ],
        "sources": [{"id": "rec-1"}],
        "total_matches": 2,
        "filtered_matches": 2,
    })

    generation = MagicMock()
    generation.initialize = AsyncMock()
    generation.health_check = AsyncMock(return_value=True)
    generation.model_name = "gpt-4o"
    generation.client = MagicMock()

    context = AsyncMock()
    context.initialize = AsyncMock()
    context.health_check = AsyncMock(return_value=True)
    context.add_message = AsyncMock()
    context.get_full_context = AsyncMock(return_value=(
        [{"role": "user", "content": "previous question"}],
        "",
    ))

    return mongodb, embedding, retrieval, generation, context


def _build_orchestrator():
    mongodb, embedding, retrieval, generation, context = _make_services()
    orch = ConversationOrchestrator(mongodb, embedding, retrieval, generation, context)
    orch.initialized = True
    return orch


def _mock_classifier_response(intents, needs_patient_context=False):
    """Return an async mock that resolves to a classification dict."""
    async def classify(query, conversation_context=None):
        return {
            "intents": intents,
            "needs_patient_context": needs_patient_context,
            "reasoning": "test",
        }
    return classify


# ---------------------------------------------------------------------------
# Consent tests
# ---------------------------------------------------------------------------

class TestConsent:
    """Test the consent gate independently."""

    @pytest.mark.asyncio
    async def test_consent_granted_with_patient_id(self):
        result = await check_patient_data_consent(patient_id="patient-101")
        assert result.authorized is True
        assert "patient:read" in result.scopes

    @pytest.mark.asyncio
    async def test_consent_denied_without_patient_id(self):
        result = await check_patient_data_consent(patient_id="")
        assert result.authorized is False

    @pytest.mark.asyncio
    async def test_consent_denied_missing_scope(self):
        result = await check_patient_data_consent(
            patient_id="patient-101",
            required_scopes=["nonexistent:scope"],
        )
        assert result.authorized is False
        assert "nonexistent:scope" not in result.scopes


# ---------------------------------------------------------------------------
# Triage precedence tests
# ---------------------------------------------------------------------------

class TestTriagePrecedence:
    """Verify that emergency/urgent triage short-circuits the pipeline."""

    @pytest.mark.asyncio
    async def test_emergency_short_circuits(self):
        orch = _build_orchestrator()
        orch.intent_classifier.classify = _mock_classifier_response(["triage", "medication"])

        emergency_response = AgentResponse(
            answer="Call 911 immediately for chest pain.",
            warnings=["Possible cardiac event"],
            clinician_triggers=["EMERGENCY: Call 911"],
            agent_name="maitriage",
            confidence=0.95,
            metadata={"urgency": "emergency"},
        )
        orch.safety_agent.handle = AsyncMock(return_value=emergency_response)
        orch.safety_agent.review_merged_answer = AsyncMock(return_value={
            "safe": True,
            "issues": [],
            "revised_answer": emergency_response.answer,
        })

        result = await orch.process_query(
            query="I'm having severe chest pain and can't breathe",
            patient_id="patient-101",
            session_id="s1",
        )

        assert result["metadata"]["triage_short_circuit"] is True
        assert result["metadata"]["urgency"] == "emergency"
        assert "triage" in result["agents_invoked"]
        assert "medication" not in result["agents_invoked"]
        assert "911" in result["answer"]

    @pytest.mark.asyncio
    async def test_urgent_short_circuits(self):
        orch = _build_orchestrator()
        orch.intent_classifier.classify = _mock_classifier_response(["triage", "lab"])

        urgent_response = AgentResponse(
            answer="Contact your healthcare provider today about your high fever.",
            warnings=["High fever >103°F"],
            clinician_triggers=["Contact provider today"],
            agent_name="maitriage",
            confidence=0.95,
            metadata={"urgency": "urgent"},
        )
        orch.safety_agent.handle = AsyncMock(return_value=urgent_response)
        orch.safety_agent.review_merged_answer = AsyncMock(return_value={
            "safe": True,
            "issues": [],
            "revised_answer": urgent_response.answer,
        })

        result = await orch.process_query(
            query="I have a fever of 104 and chills since yesterday",
            patient_id="patient-101",
            session_id="s1",
        )

        assert result["metadata"]["triage_short_circuit"] is True
        assert result["metadata"]["urgency"] == "urgent"
        assert "lab" not in result["agents_invoked"]

    @pytest.mark.asyncio
    async def test_not_urgent_falls_through(self):
        orch = _build_orchestrator()
        orch.intent_classifier.classify = _mock_classifier_response(
            ["triage", "medication"], needs_patient_context=False,
        )

        not_urgent = AgentResponse(
            answer="No urgent concern detected.",
            agent_name="maitriage",
            metadata={"urgency": "not_urgent"},
        )
        orch.safety_agent.handle = AsyncMock(return_value=not_urgent)

        med_response = AgentResponse(
            answer="Metformin is taken with food.",
            agent_name="maimed",
            confidence=0.85,
        )
        orch.agents["medication"].handle = AsyncMock(return_value=med_response)
        orch.safety_agent.review_merged_answer = AsyncMock(return_value={
            "safe": True, "issues": [], "revised_answer": med_response.answer,
        })

        result = await orch.process_query(
            query="Should I take metformin before or after food?",
            patient_id="patient-101",
            session_id="s1",
        )

        assert result["metadata"].get("triage_short_circuit") is not True
        assert "medication" in result["agents_invoked"]


# ---------------------------------------------------------------------------
# Patient context handoff tests
# ---------------------------------------------------------------------------

class TestPatientContextHandoff:
    """Verify patient context summary is injected into specialist agents."""

    @pytest.mark.asyncio
    async def test_context_summary_passed_to_specialist(self):
        orch = _build_orchestrator()
        orch.intent_classifier.classify = _mock_classifier_response(
            ["medication"], needs_patient_context=True,
        )

        ctx_response = AgentResponse(
            answer="Patient has T2DM, takes metformin 500mg BID, no known allergies.",
            agent_name="maicontext",
        )
        orch.patient_context_agent.handle = AsyncMock(return_value=ctx_response)

        med_response = AgentResponse(
            answer="Based on your records, metformin should be taken with meals.",
            agent_name="maimed",
            confidence=0.85,
        )
        orch.agents["medication"].handle = AsyncMock(return_value=med_response)
        orch.safety_agent.review_merged_answer = AsyncMock(return_value={
            "safe": True, "issues": [], "revised_answer": med_response.answer,
        })

        result = await orch.process_query(
            query="When should I take my diabetes medication?",
            patient_id="patient-101",
            session_id="s1",
        )

        call_kwargs = orch.agents["medication"].handle.call_args
        assert call_kwargs.kwargs.get("patient_context_summary") is not None
        assert "metformin" in call_kwargs.kwargs["patient_context_summary"]
        assert result["metadata"]["patient_context_injected"] is True


# ---------------------------------------------------------------------------
# Multi-intent tests
# ---------------------------------------------------------------------------

class TestMultiIntent:
    """Verify parallel multi-intent routing preserves warnings."""

    @pytest.mark.asyncio
    async def test_medication_plus_lab_merged(self):
        orch = _build_orchestrator()
        orch.intent_classifier.classify = _mock_classifier_response(
            ["medication", "lab"], needs_patient_context=False,
        )

        med_resp = AgentResponse(
            answer="Metformin helps control blood sugar.",
            warnings=["Take with food to reduce GI upset."],
            clinician_triggers=["Contact clinician if persistent nausea."],
            agent_name="maimed",
        )
        lab_resp = AgentResponse(
            answer="HbA1c of 7.1% indicates fair glucose control.",
            warnings=["Retest in 3 months."],
            clinician_triggers=["Discuss target HbA1c with your doctor."],
            agent_name="mailab",
        )
        orch.agents["medication"].handle = AsyncMock(return_value=med_resp)
        orch.agents["lab"].handle = AsyncMock(return_value=lab_resp)

        merged_text = "Metformin helps control blood sugar. HbA1c of 7.1% indicates fair control."
        orch.safety_agent.review_merged_answer = AsyncMock(return_value={
            "safe": True, "issues": [], "revised_answer": merged_text,
        })

        result = await orch.process_query(
            query="Tell me about my metformin and my latest HbA1c",
            patient_id="patient-101",
            session_id="s1",
        )

        assert "medication" in result["agents_invoked"]
        assert "lab" in result["agents_invoked"]
        assert len(result["all_warnings"]) >= 2
        assert len(result["all_clinician_triggers"]) >= 2


# ---------------------------------------------------------------------------
# Consent denial in orchestrator
# ---------------------------------------------------------------------------

class TestConsentInOrchestrator:
    """Verify the consent gate blocks the pipeline when denied."""

    @pytest.mark.asyncio
    async def test_consent_denied_returns_error(self):
        orch = _build_orchestrator()
        orch.intent_classifier.classify = _mock_classifier_response(
            ["medication"], needs_patient_context=True,
        )

        with patch(
            "pipeline.conversation_orchestrator.check_patient_data_consent",
            new_callable=AsyncMock,
            return_value=ConsentResult(
                authorized=False,
                scopes=[],
                patient_id="patient-101",
                reason="Patient has opted out of data sharing.",
            ),
        ):
            result = await orch.process_query(
                query="What medications am I taking?",
                patient_id="patient-101",
                session_id="s1",
            )

        assert result["metadata"]["consent_denied"] is True
        assert "unable to access" in result["answer"].lower()
        assert result["agents_invoked"] == []


# ---------------------------------------------------------------------------
# Citation normalization
# ---------------------------------------------------------------------------

class TestCitationNormalization:
    """Verify the citation/evidence step produces structured output."""

    def test_citations_from_agent_refs_and_retrieval(self):
        orch = _build_orchestrator()
        agent_responses = [
            AgentResponse(
                answer="Answer text",
                agent_name="maimed",
                evidence_references=[
                    {"text": "Metformin 500mg twice daily", "score": 0.92},
                ],
            ),
        ]
        retrieved = [
            {"text": "HbA1c 7.1% on 2025-01-15", "score": 0.88, "id": "rec-2",
             "metadata": {"resource_type": "Observation"}},
        ]

        citations = orch._normalize_citations(agent_responses, retrieved)
        assert len(citations) == 2
        assert citations[0]["relevance_score"] >= citations[1]["relevance_score"]
        assert any(c.get("agent") == "maimed" for c in citations)
        assert any(c.get("agent") == "retrieval" for c in citations)


# ---------------------------------------------------------------------------
# Greeting short-circuit (regression)
# ---------------------------------------------------------------------------

class TestGreetingRegression:
    """Greeting short-circuit should still bypass all agent work."""

    @pytest.mark.asyncio
    async def test_greeting_skips_agents(self):
        orch = _build_orchestrator()
        result = await orch.process_query(
            query="Hello!",
            patient_id="patient-101",
            session_id="s1",
        )
        assert result["metadata"].get("simple_greeting") is True
        assert "agent_details" in result
        assert result["intent_classification"]["intents"] == ["greeting"]


# ---------------------------------------------------------------------------
# Safety review is always applied
# ---------------------------------------------------------------------------

class TestSafetyReviewMandatory:
    """Final safety review must run on every non-greeting response."""

    @pytest.mark.asyncio
    async def test_safety_review_called_for_education(self):
        orch = _build_orchestrator()
        orch.intent_classifier.classify = _mock_classifier_response(["education"])

        edu_resp = AgentResponse(answer="Diabetes is a chronic condition.", agent_name="maied")
        orch.agents["education"].handle = AsyncMock(return_value=edu_resp)
        orch.safety_agent.review_merged_answer = AsyncMock(return_value={
            "safe": True, "issues": [], "revised_answer": edu_resp.answer,
        })

        await orch.process_query(
            query="What is diabetes?",
            patient_id="patient-101",
            session_id="s1",
        )

        orch.safety_agent.review_merged_answer.assert_called_once()


# ---------------------------------------------------------------------------
# Run with: python -m pytest tests/test_orchestrator_scenarios.py -v
# ---------------------------------------------------------------------------
