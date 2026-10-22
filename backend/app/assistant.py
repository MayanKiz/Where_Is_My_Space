"""Conversational space assistant for WIMS.

The assistant receives only derived occupancy metadata. Raw frames, source URLs,
credentials, and personal identifiers never enter the prompt. Amazon Bedrock is
used when configured; the deterministic fallback keeps local demos usable without
AWS credentials or network access.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("wims.assistant")

DEFAULT_MODEL_ID = "amazon.nova-lite-v1:0"
MAX_MESSAGE_LENGTH = 1200
MAX_HISTORY_MESSAGES = 8


@dataclass(frozen=True)
class AssistantSettings:
    region: str = "us-east-1"
    model_id: str = DEFAULT_MODEL_ID
    enabled: bool = False


def _normalise_zones(zones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only public, derived occupancy fields before sending context to a model."""
    safe: list[dict[str, Any]] = []
    for zone in zones[:50]:
        capacity = zone.get("capacity")
        occupied = zone.get("occupied")
        if not isinstance(capacity, int | float):
            continue
        occupied_value = occupied if isinstance(occupied, int | float) else None
        safe.append(
            {
                "name": str(zone.get("name") or "Unnamed space")[:120],
                "location": str(zone.get("location") or "Campus")[:120],
                "capacity": int(capacity),
                "occupied": int(occupied_value) if occupied_value is not None else None,
                "status": str(zone.get("status") or "No data")[:40],
                "observed_at": zone.get("observed_at"),
            }
        )
    return safe


def build_context(zones: list[dict[str, Any]]) -> dict[str, Any]:
    safe_zones = _normalise_zones(zones)
    return {
        "spaces": safe_zones,
        "space_count": len(safe_zones),
        "privacy_note": "Occupancy estimates only; no identities or raw video are available to the assistant.",
    }


def fallback_answer(message: str, zones: list[dict[str, Any]]) -> str:
    """Answer common demo questions without pretending that sample data is live."""
    safe_zones = _normalise_zones(zones)
    available = [
        zone for zone in safe_zones
        if zone["occupied"] is not None and zone["occupied"] < zone["capacity"]
    ]
    lower = message.lower()
    if not safe_zones:
        return "I do not have live space data yet. Connect the WIMS API and process a video clip to create an occupancy snapshot."
    if any(word in lower for word in ("quiet", "available", "free", "study")):
        if available:
            ranked = sorted(available, key=lambda item: (item["occupied"] / max(item["capacity"], 1), item["name"]))
            picks = ", ".join(f'{item["name"]} ({item["capacity"] - item["occupied"]} free)' for item in ranked[:3])
            return f"The least occupied spaces with current estimates are {picks}. Availability is based on the latest processed sample, not a reservation."
        return "Every connected space is currently full or has no usable occupancy estimate."
    if any(word in lower for word in ("busy", "crowded", "full")):
        ranked = sorted(
            (zone for zone in safe_zones if zone["occupied"] is not None),
            key=lambda item: item["occupied"] / max(item["capacity"], 1),
            reverse=True,
        )
        if ranked:
            item = ranked[0]
            return f'{item["name"]} is currently the busiest at {item["occupied"]}/{item["capacity"]} occupied ({item["status"]}).'
    summary = "; ".join(
        f'{item["name"]}: {item["occupied"]}/{item["capacity"]} ({item["status"]})'
        if item["occupied"] is not None else f'{item["name"]}: no live estimate'
        for item in safe_zones[:4]
    )
    return f"Here is the latest space summary: {summary}. Ask me which space is quietest, busiest, or has room."


def _bedrock_answer(message: str, history: list[dict[str, str]], context: dict[str, Any], settings: AssistantSettings) -> str:
    try:
        import boto3

        client = boto3.client("bedrock-runtime", region_name=settings.region)
        system = [{"text": (
            "You are WIMS Space Assistant. Help people choose physical study and public spaces "
            "using only the supplied occupancy metadata. Be concise, practical, and honest about "
            "estimates and stale data. Never infer identities, demographics, or events from video. "
            "If no live estimate exists, say so. Do not claim to reserve a space."
        )}]
        messages = [
            {"role": item["role"], "content": [{"text": item["content"][:MAX_MESSAGE_LENGTH]}]}
            for item in history[-MAX_HISTORY_MESSAGES:]
            if item.get("role") in {"user", "assistant"} and item.get("content")
        ]
        messages.append({"role": "user", "content": [{"text": f"Space metadata:\n{json.dumps(context, separators=(',', ':'))}\n\nQuestion: {message}"}]})
        response = client.converse(
            modelId=settings.model_id,
            system=system,
            messages=messages,
            inferenceConfig={"maxTokens": 350, "temperature": 0.2},
        )
        content = response.get("output", {}).get("message", {}).get("content", [])
        answer = " ".join(str(block.get("text", "")) for block in content if block.get("text")).strip()
        if not answer:
            raise RuntimeError("Bedrock returned an empty answer")
        return answer[:2000]
    except Exception:
        logger.exception("Bedrock assistant request failed; using local fallback.")
        return fallback_answer(message, context["spaces"])


def answer(message: str, zones: list[dict[str, Any]], history: list[dict[str, str]], settings: AssistantSettings) -> tuple[str, str]:
    cleaned = " ".join(message.split()).strip()
    if not cleaned:
        raise ValueError("message must not be empty")
    if len(cleaned) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"message must be {MAX_MESSAGE_LENGTH} characters or fewer")
    context = build_context(zones)
    if settings.enabled:
        return _bedrock_answer(cleaned, history, context, settings), "amazon-bedrock"
    return fallback_answer(cleaned, context["spaces"]), "local-fallback"
