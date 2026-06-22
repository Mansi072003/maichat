# agents/tools/education_tools.py
"""
Education tools for the Education Agent (maied).

Tools:
  searchEducationArticles — search curated health education content by topic

FHIR Resource Mapping (target state):
  searchEducationArticles → Library (type=asset-collection) or
                             DocumentReference (category=education) containing
                             curated patient-education content.
"""
from typing import Dict, Any
from agents.tools.base_tool import BaseTool
from utils.logger import get_logger

logger = get_logger(__name__)


class SearchEducationArticles(BaseTool):
    name = "searchEducationArticles"
    description = "Search curated health education articles by topic. Optionally specify language and literacy level."
    parameters = {
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "Health topic to search (e.g. diabetes, hypertension, cholesterol)"},
            "language": {"type": "string", "description": "Optional: language code (e.g. en, es, hi). Default: en"},
            "literacyLevel": {"type": "string", "description": "Optional: reading level (simple, standard, advanced). Default: standard"},
        },
        "required": ["topic"]
    }

    def __init__(self, retrieval_service):
        self.retrieval_service = retrieval_service

    async def execute(self, topic: str, language: str = "en", literacyLevel: str = "standard", **kwargs) -> Dict[str, Any]:
        try:
            query = f"{topic} health education patient guide"
            if literacyLevel == "simple":
                query += " simple easy to understand"
            elif literacyLevel == "advanced":
                query += " detailed clinical information"

            result = await self.retrieval_service.retrieve_context(
                query=query,
                patient_id=None,
                top_k=5,
                similarity_threshold=0.4,
            )
            articles = [{"text": c["text"], "score": c.get("score", 0)} for c in result.get("contexts", [])]
            return {
                "topic": topic,
                "language": language,
                "literacyLevel": literacyLevel,
                "articles": articles,
                "count": len(articles),
            }
        except Exception as e:
            logger.error(f"searchEducationArticles error: {e}")
            return {"topic": topic, "articles": [], "error": str(e)}


def create_education_tools(retrieval_service):
    """Factory function to create all education tools."""
    return [SearchEducationArticles(retrieval_service)]
