import datetime
import hashlib
import json
import logging
import re
from typing import Dict

from config import settings
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from services.redis_service import redis_client
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from utils.json_repair import safe_json_loads

logger = logging.getLogger("ai_reporting")


def _xml_wrap(key: str, value: str) -> str:
    """Wrap user-supplied content in XML tags to prevent prompt injection."""
    return f"<{key}>{value}</{key}>"


# Category → impact mapping for structuring batch observations.
_CATEGORY_IMPACT = {
    "risk vector": "High",
    "strategic intervention": "High",
    "operational readiness": "Medium",
    "leadership velocity": "Medium",
    "engagement index": "Medium",
    "technical proficiency": "Low",
}
_INTERVENTION_MARKERS = ("recommend", "intervention", "should", "suggest", "prioritize", "consider")


def structure_batch_observations(raw: list) -> list[dict]:
    """Convert batch insight strings (``"[Category] observation..."``) into the
    ``{category, impact, dimension, observation, actionable_step}`` objects the
    executive report renders. Fixes Bug 21 (30 empty 'Impact / Intervention'
    rows because the frontend mapped object fields onto flat strings).

    Already-structured dict items are passed through untouched. Empty/blank
    items are dropped so the report never shows hollow cards.
    """
    structured: list[dict] = []
    for item in raw or []:
        if isinstance(item, dict):
            # Trust pre-structured items but skip ones with no readable body.
            if item.get("observation") or item.get("insight") or item.get("dimension"):
                structured.append(item)
            continue
        text = str(item or "").strip()
        if not text:
            continue
        m = re.match(r"^\s*\[([^\]]+)\]\s*(.*)$", text)
        if m:
            category = m.group(1).strip()
            observation = m.group(2).strip()
        else:
            category = "Strategic Insight"
            observation = text
        if not observation:
            continue
        impact = _CATEGORY_IMPACT.get(category.lower(), "Medium")
        # Derive an actionable step from any recommendation clause in the text.
        actionable = ""
        low = observation.lower()
        for marker in _INTERVENTION_MARKERS:
            idx = low.find(marker)
            if idx != -1:
                # Take from the sentence containing the marker onward.
                sent_start = observation.rfind(".", 0, idx) + 1
                actionable = observation[sent_start:].strip()
                break
        if not actionable:
            actionable = (
                f"Review the {category.lower()} signal with the batch mentor and "
                "define a concrete follow-up action."
            )
        structured.append(
            {
                "category": category,
                "impact": impact,
                "dimension": category,
                "observation": observation,
                "actionable_step": actionable,
            }
        )
    return structured


class ExecutiveAIService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key:
            self.llm = ChatGoogleGenerativeAI(
                model=settings.PRIMARY_AI_MODEL,
                google_api_key=self.api_key,
                temperature=0.7,
            )
        else:
            self.llm = None
            logger.warning("GEMINI_API_KEY not set — AI insights will be unavailable.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _make_call(
        self, prompt: str, cache_ttl: int = 86400, force: bool = False
    ) -> Dict:
        """
        Unified call with AIResponseEnvelope output.
        Returns: {ai_generated, fallback_reason, data, generated_at}
        """
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
        cache_key = f"ai_report:v2:{prompt_hash}"
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if not force:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    return data
            except Exception as e:
                logger.warning(f"AI Cache lookup failed: {e}")

        if not self.llm:
            logger.warning("AI Fallback Triggered: GEMINI_API_KEY missing")
            return {
                "ai_generated": False,
                "fallback_reason": "GEMINI_API_KEY not configured",
                "data": None,
                "generated_at": now_iso,
            }

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = str(response.content).strip()

            envelope = {
                "ai_generated": True,
                "fallback_reason": None,
                "data": content,
                "generated_at": now_iso,
            }

            try:
                await redis_client.set(cache_key, json.dumps(envelope), ex=cache_ttl)
            except Exception as e:
                logger.warning(f"AI Cache write failed: {e}")

            return envelope
        except Exception as e:
            logger.error(f"AI Call failed: {e}")
            return {
                "ai_generated": False,
                "fallback_reason": f"LLM Call Error: {str(e)}",
                "data": None,
                "generated_at": now_iso,
            }

    async def generate_ai_response(self, prompt: str, cache_ttl: int = 86400) -> Dict:
        """
        Public entry point for generic AI completions.
        Returns: AIResponseEnvelope
        """
        return await self._make_call(prompt, cache_ttl=cache_ttl)

    async def generate_batch_insights(
        self, batch_name: str, stats: Dict, force: bool = False
    ) -> Dict:
        """
        Generates 30 structured strategic observations for an L&D Batch.
        Returns: AIResponseEnvelope
        """
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        fallback_data = [
            f"[Technical Proficiency] Batch proficiency validated at {stats.get('average_score', 0)}% — establishes baseline for subsequent sprint benchmarking.",
            f"[Engagement Index] {stats.get('total_members', 0)} enrolled members have generated {stats.get('total_attempts', 0)} assessment submissions, indicating active engagement.",
            "[Risk Vector] Statistical baseline established; detailed behavioral analysis pending AI synchronization.",
            "[Strategic Intervention] L&D team should schedule a synchronization review to validate cohort progress against organizational KPIs.",
        ]

        if not self.llm:
            return {
                "ai_generated": False,
                "fallback_reason": "GEMINI_API_KEY not configured",
                "data": fallback_data,
                "generated_at": now_iso,
            }

        safe_batch = _xml_wrap("batch_name", str(batch_name)[:200])
        metrics_json = json.dumps(
            {
                "global_avg_accuracy_pct": stats.get("average_score", 0),
                "total_members": stats.get("total_members", 0),
                "total_assessments": stats.get("total_attempts", 0),
                "group_breakdown": stats.get("group_performance", []),
                "top_5_performers": stats.get("top_performers", []),
            },
            indent=2,
        )

        prompt = f"""You are a Senior Strategic Learning & Development Analyst at a Fortune 500 Enterprise.
Your task: analyze the quantitative performance data below and generate exactly 30 high-value, non-generic strategic insights.

BATCH CONTEXT:
{safe_batch}

METRICS DATA:
<metrics>
{metrics_json}
</metrics>

STRICT OUTPUT REQUIREMENTS:
1. Return ONLY a valid JSON array of exactly 30 strings. No markdown, no prose outside the array.
2. Each string must start with one of these category tags:
   [Leadership Velocity], [Risk Vector], [Technical Proficiency], [Operational Readiness], [Strategic Intervention]
3. NEVER restate raw numbers verbatim. Interpret, contextualize, and recommend.
4. Use professional L&D language: "We observe...", "Data suggests...", "Benchmark indicates...", "Intervention recommended..."
5. Each insight must be a full sentence of 15-40 words.
6. Insights must cover: performance gaps, cohort differentiation, engagement patterns, skill velocity, mentor recommendations, business readiness, anomalies, and predictive signals.
7. Return ONLY the JSON array. Ensure it is structurally complete and valid. DO NOT truncate.

OUTPUT FORMAT:
["[Category] Insight text here.", "[Category] Another insight.", ...]
"""
        try:
            envelope = await self._make_call(prompt, cache_ttl=21600, force=force)
            if not envelope["ai_generated"]:
                envelope["data"] = fallback_data
                return envelope

            text = envelope["data"]
            parsed = safe_json_loads(text)
            if isinstance(parsed, list):
                uuid_pattern = r"[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}"
                envelope["data"] = [
                    re.sub(uuid_pattern, "[REDACTED_ID]", str(item))
                    for item in parsed[:30]
                ]
                return envelope

            logger.warning(
                "AI response did not contain a valid JSON array — using fallback insights"
            )
            envelope["ai_generated"] = False
            envelope["fallback_reason"] = "Invalid JSON response from AI"
            envelope["data"] = fallback_data
            return envelope
        except Exception as e:
            logger.error(f"AI Batch Insights Error: {e}")
            return {
                "ai_generated": False,
                "fallback_reason": f"System Error: {str(e)}",
                "data": fallback_data,
                "generated_at": now_iso,
            }

    async def generate_member_summary(
        self, member_name: str, insights: Dict, force: bool = False
    ) -> Dict:
        """Generates a professional AI-powered growth narrative for a specific member."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Extract from 30-metric vector format
        metrics_dict = insights.get("metrics", {})
        insights.get("charts", {})

        acc = metrics_dict.get("m02_overall_accuracy", {}).get("raw", 0)
        code_rate = metrics_dict.get("m14_coding_success_rate", {}).get("raw", 0)

        fallback_text = (
            f"Performance data indicates a quiz accuracy of {acc}% with a coding success rate of {code_rate}%. "
            "Consistent participation across both assessment types is the primary strength observed. "
            "Manual review of recent attempts is recommended to identify specific qualitative growth areas."
        )

        if not self.llm:
            return {
                "ai_generated": False,
                "fallback_reason": "GEMINI_API_KEY not configured",
                "data": fallback_text,
                "generated_at": now_iso,
            }

        safe_name = _xml_wrap("member_name", str(member_name)[:100])
        metrics = {
            "quiz_accuracy_pct": acc,
            "group_average_accuracy_pct": metrics_dict.get("m26_percentile", {}).get(
                "raw", 0
            ),  # Fallback to percentile if avg not direct
            "coding_success_rate_pct": code_rate,
            "consistency_score_pct": insights.get("advanced", {}).get(
                "consistency_score", 0
            ),
            "weighted_proficiency_pct": insights.get("advanced", {}).get(
                "weighted_proficiency", 0
            ),
            "topic_mastery": insights.get("synchronization", {}).get(
                "topic_mastery", []
            ),
            "streak": insights.get("advanced", {}).get("streak", 0),
            "study_path": insights.get("study_path", []),
        }

        prompt = f"""You are a Senior Learning & Development Mentor at a professional enterprise.
Write a personalized, encouraging, and data-driven growth summary for the following learner.

LEARNER: {safe_name}
PERFORMANCE DATA:
<metrics>
{json.dumps(metrics, indent=2)}
</metrics>

REQUIREMENTS:
1. Exactly 4-5 sentences.
2. Tone: Professional, encouraging, and specific — never generic praise.
3. Identify one concrete strength based on the metrics.
4. Peer-Benchmarking: Briefly mention their performance relative to the group average.
5. Identify one specific improvement area with an actionable suggestion.
6. Crucially, explicitly recommend the specific tracks provided in 'study_path' as their optimal next actions.
7. Do NOT use the learner's name more than once.
8. Do NOT output anything except the summary paragraph. No headers, no bullet points.
"""
        try:
            envelope = await self._make_call(prompt, cache_ttl=21600, force=force)
            if not envelope["ai_generated"]:
                envelope["data"] = fallback_text
                return envelope

            raw_data = envelope["data"].strip()
            uuid_pattern = r"[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}"
            envelope["data"] = re.sub(uuid_pattern, "[REDACTED_ID]", raw_data)
            return envelope
        except Exception as e:
            logger.error(f"Member AI Insight Error: {e}")
            return {
                "ai_generated": False,
                "fallback_reason": f"System Error: {str(e)}",
                "data": fallback_text,
                "generated_at": now_iso,
            }

    async def generate_analytics_insights(
        self, metrics: Dict, force: bool = False
    ) -> Dict:
        """Generates structured AI commentary and strategic insights for the AnalyticsCharts dashboard."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        fallback_data = {
            "summary": "Platform metrics have been aggregated. Review individual group breakdowns for targeted interventions.",
            "insights": [
                {
                    "category": "Synchronization",
                    "impact": "Medium",
                    "insight": "Platform metrics have been aggregated. Review individual group breakdowns.",
                },
                {
                    "category": "Efficiency",
                    "impact": "Low",
                    "insight": "Ensure all batch sectors have active mentorship assigned to accelerate proficiency.",
                },
            ],
        }

        if not self.llm:
            return {
                "ai_generated": False,
                "fallback_reason": "GEMINI_API_KEY not configured",
                "data": fallback_data,
                "generated_at": now_iso,
            }

        prompt = f"""You are a Strategic L&D Analyst. Analyze these platform metrics and generate a high-level executive summary and exactly 6 granular strategic insights.
<metrics>{json.dumps(metrics)}</metrics>
STRICT REQUIREMENTS:
1. Return ONLY a valid JSON object. No markdown.
2. The object must have:
   - "summary": A 3-sentence executive paragraph summarizing overall performance and impact.
   - "insights": An array of 6 objects, each with "category", "impact" (High/Medium/Low), and "insight" (max 25 words).
3. Focus on engagement trends, accuracy gaps, and resource allocation.
4. Return ONLY a valid JSON object. Ensure it is structurally complete and valid. DO NOT truncate.
No intro, no outro."""
        try:
            envelope = await self._make_call(prompt, cache_ttl=21600, force=force)
            if not envelope["ai_generated"]:
                envelope["data"] = fallback_data
                return envelope

            text = envelope["data"]
            parsed = safe_json_loads(text)
            if (
                isinstance(parsed, dict)
                and "summary" in parsed
                and "insights" in parsed
            ):
                envelope["data"] = parsed
                return envelope

            logger.warning(
                "AI response did not contain valid JSON object — using fallback"
            )
            envelope["ai_generated"] = False
            envelope["fallback_reason"] = "Invalid JSON structure in AI response"
            envelope["data"] = fallback_data
            return envelope
        except Exception as e:
            logger.error(f"Analytics AI error: {e}")
            return {
                "ai_generated": False,
                "fallback_reason": f"System Error: {str(e)}",
                "data": fallback_data,
                "generated_at": now_iso,
            }

    async def generate_member_growth_atlas(
        self, member_name: str, data: Dict, force: bool = False
    ) -> Dict:
        """Generates exactly 30 granular growth insights for an individual learner."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        vectors = data.get("vectors", {})
        # Extract from 30-metric vector format (metrics key)
        metrics_vectors = (
            vectors.get("metrics", {}) if "metrics" in vectors else vectors
        )
        consistency = metrics_vectors.get("m18_consistency", {}).get("raw", 0)

        fallback_data = [
            f"[Consistency Vector] Learner maintaining stable engagement with a consistency score of {consistency}% in the current assessment cycle.",
            "[Strategic Depth] Foundational concepts validated; further deep-dive sessions recommended for complex problem vectors.",
            "[Pattern Mastery] Assessment history indicates consistent participation across both synchronous and asynchronous modules.",
        ]

        if not self.llm:
            return {
                "ai_generated": False,
                "fallback_reason": "GEMINI_API_KEY not configured",
                "data": fallback_data,
                "generated_at": now_iso,
            }

        metrics_json = json.dumps(vectors, indent=2)

        prompt = f"""You are a High-Performance Growth Coach and Strategic L&D Lead for a Fortune 500 company.
Analyze this high-potenial learner's quantitative trajectory and generate exactly 30 granular, professional growth insights.

LEARNER: {member_name}
PERFORMANCE VECTORS:
<vectors>
{metrics_json}
</vectors>

STRICT REQUIREMENTS:
1. Return ONLY a valid JSON array of exactly 30 strings. No markdown, no intro.
2. Each string must start with one of these category tags:
   [Cognitive Velocity], [Pattern Mastery], [Strategic Depth], [Consistency Vector], [Risk Awareness]
3. Each insight must be a complete, professional sentence (15-35 words).
4. Do NOT repeat yourself. Each of the 30 insights must cover a different dimension of the data.
5. Translate Numbers to Impact: e.g., if Knowledge Velocity is positive, explain the career implication.
6. Return ONLY a valid JSON array. Ensure it is structurally complete and valid. DO NOT truncate.
"""
        try:
            envelope = await self._make_call(prompt, cache_ttl=21600, force=force)
            if not envelope["ai_generated"]:
                envelope["data"] = fallback_data
                return envelope

            text = envelope["data"]
            parsed = safe_json_loads(text)
            if isinstance(parsed, list):
                envelope["data"] = [str(item) for item in parsed[:30]]
                return envelope

            logger.warning(
                "AI response did not contain a valid JSON array — using fallback insights"
            )
            envelope["ai_generated"] = False
            envelope["fallback_reason"] = "Invalid JSON response from AI"
            envelope["data"] = fallback_data
            return envelope
        except Exception as e:
            logger.error(f"Member Atlas Error: {e}")
            return {
                "ai_generated": False,
                "fallback_reason": f"System Error: {str(e)}",
                "data": fallback_data,
                "generated_at": now_iso,
            }

    async def generate_batch_executive_summary(
        self, batch_name: str, cohort_data: dict, force: bool = False
    ) -> Dict:
        """Generate an executive meta-analysis for an entire batch."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fallback_data = "Strategy synchronization pending. Cohort metrics have been recorded for manual executive review."

        if not self.llm:
            return {
                "ai_generated": False,
                "fallback_reason": "GEMINI_API_KEY not configured",
                "data": fallback_data,
                "generated_at": now_iso,
            }

        prompt = f"""YOU ARE THE CHIEF LEARNING ARCHITECT.
ANALYZE COHORT DATA FOR BATCH: {batch_name}
DATA: {json.dumps(cohort_data, indent=2)}

        GOAL:
        PROVIDE A 10-POINT EXECUTIVE STRATEGY SUMMARY FOR L&D DIRECTORS.
        FOCUS ON:
        1. COHORT-WIDE VELOCITY (Is the batch moving fast enough?).
        2. KNOWLEDGE GAPS (Specific topics where accuracy is < 65%).
        3. TALENT DENSITY (Percentage of 'Stars' vs 'At-Risk').
        4. STRATEGIC RECOMMENDATIONS (What should the mentors do next week?).
        
        FORMAT:
        RETURN A CLEAN LIST OF 10 STRATEGIC BULLETS.
        MAX 25 WORDS PER BULLET.
        BE PROFESSIONAL, DATA-DRIVEN, AND AGGRESSIVE.
"""
        try:
            envelope = await self._make_call(prompt, cache_ttl=21600, force=force)
            if not envelope["ai_generated"]:
                envelope["data"] = fallback_data
                return envelope

            envelope["data"] = envelope["data"].strip()
            return envelope
        except Exception as e:
            logger.error(f"AI Batch Summary Error: {e}")
            return {
                "ai_generated": False,
                "fallback_reason": f"System Error: {str(e)}",
                "data": fallback_data,
                "generated_at": now_iso,
            }

    async def generate_cohort_health(
        self, group_name: str, metrics: dict, force: bool = False
    ) -> Dict:
        """Generate 10 targeted strategic intervention points for a specific group/cohort."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fallback_data = [
            "[Diagnostic] Group health metrics stabilized; qualitative diagnostics pending AI synchronization.",
            "[Intervention] Mentors should prioritize identification of outlier performance vectors to prevent cohort drift.",
        ]

        if not self.llm:
            return {
                "ai_generated": False,
                "fallback_reason": "GEMINI_API_KEY not configured",
                "data": fallback_data,
                "generated_at": now_iso,
            }

        prompt = f"""You are a Strategic L&D Mentor. Analyze this cohort's performance:
GROUP: {group_name}
METRICS: {json.dumps(metrics, indent=2)}

Generate exactly 10 high-value intervention points. 
Focus on: Identifying outliers, predicting drift, and suggesting specific mentoring tactics.
Format: Valid JSON array of 10 strings. Ensure it is structurally complete and valid. DO NOT truncate. No intro/outro."""

        try:
            envelope = await self._make_call(prompt, cache_ttl=21600, force=force)
            if not envelope["ai_generated"]:
                envelope["data"] = fallback_data
                return envelope

            text = envelope["data"]
            parsed = safe_json_loads(text)
            if isinstance(parsed, list):
                envelope["data"] = [str(item) for item in parsed[:10]]
                return envelope

            logger.warning(
                "AI response did not contain valid JSON array — using fallback health points"
            )
            envelope["ai_generated"] = False
            envelope["fallback_reason"] = "Invalid JSON response from AI"
            envelope["data"] = fallback_data
            return envelope
        except Exception as e:
            logger.error(f"Cohort Health Error: {e}")
            return {
                "ai_generated": False,
                "fallback_reason": f"System Error: {str(e)}",
                "data": fallback_data,
                "generated_at": now_iso,
            }

    async def generate_user_insights(
        self, member_name: str, metrics: dict, force: bool = False
    ) -> Dict:
        """Generate a 5-point coaching narrative for a learner."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        fallback_data = (
            "**Performance Summary**: Consistent activity detected; quantitative synthesis pending AI synchronization.\n"
            "**Critical Gaps**: Target weakest topics for immediate remediation.\n"
            "**Engagement Health**: Maintain streak and active days for optimal learning velocity.\n"
            "**Technical Proficiency**: Focus on coding lab practice to bridge theory-application gap.\n"
            "**Recommended Actions**: Review weak topics, maintain 7-day activity, and complete pending assignments."
        )

        if not self.llm:
            return {
                "ai_generated": False,
                "fallback_reason": "GEMINI_API_KEY not configured",
                "data": fallback_data,
                "generated_at": now_iso,
            }

        prompt = f"""Analyze this L&D learner data and write a professional 5-point coaching intelligence report for {_xml_wrap("member", member_name)}.

Data Context:
{_xml_wrap("metrics", json.dumps(metrics, indent=2))}

Write exactly 5 bullet points covering:
1. 🎯 Performance Summary (key strengths, accuracy level, trajectory)
2. ⚠️ Critical Gaps & Risk Areas (weakest topics, risk level, what needs attention)
3. 🔥 Engagement Health (streak, activity pattern, consistency)
4. 💻 Technical Proficiency (coding lab performance, languages, assignment completion)
5. 🚀 Recommended Next Actions (3 specific, actionable steps for improvement)

Format each bullet as: **Icon Label**: Your insight here.
Be data-specific, professional, and use the exact numbers from the data provided.
"""
        try:
            envelope = await self._make_call(
                prompt, cache_ttl=43200, force=force
            )  # 12h cache
            if not envelope["ai_generated"]:
                envelope["data"] = fallback_data
                return envelope

            envelope["data"] = envelope["data"].strip()
            return envelope
        except Exception as e:
            logger.error(f"User Insights Error: {e}")
            return {
                "ai_generated": False,
                "fallback_reason": f"System Error: {str(e)}",
                "data": fallback_data,
                "generated_at": now_iso,
            }

    async def generate_pedagogical_summary(
        self, group_name: str, metrics: dict, force: bool = False
    ) -> Dict:
        """Generate a high-level pedagogical summary of a group for a mentor."""
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        avg_acc = metrics.get("avg_accuracy", 0)
        risk_counts = metrics.get("risk_counts", {})
        fallback_data = f"Group {group_name} is currently performing at {avg_acc:.1f}% accuracy with {risk_counts.get('High', 0)} high-risk cases identified."

        if not self.llm:
            return {
                "ai_generated": False,
                "fallback_reason": "GEMINI_API_KEY not configured",
                "data": fallback_data,
                "generated_at": now_iso,
            }

        prompt = f"""You are an L&D Lead analyzing a student group's performance for {_xml_wrap("group", group_name)}.

Metrics Overview:
{_xml_wrap("metrics", json.dumps(metrics, indent=2))}

Provide a 3-sentence high-fidelity summary covering:
1. Current group status relative to benchmark (80% accuracy).
2. Most pressing collective intervention needed based on the risk profile.
3. Positive trend to celebrate (accuracy or velocity).

Keep it sharp, professional, and mentor-facing.
"""
        try:
            envelope = await self._make_call(prompt, cache_ttl=21600, force=force)
            if not envelope["ai_generated"]:
                envelope["data"] = fallback_data
                return envelope

            envelope["data"] = envelope["data"].strip()
            return envelope
        except Exception as e:
            logger.error(f"Pedagogical Summary Error: {e}")
            return {
                "ai_generated": False,
                "fallback_reason": f"System Error: {str(e)}",
                "data": fallback_data,
                "generated_at": now_iso,
            }


ai_executive = ExecutiveAIService()
