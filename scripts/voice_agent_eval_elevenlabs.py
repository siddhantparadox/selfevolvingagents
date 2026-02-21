import asyncio
import os
import random
import re
from typing import Any, Dict, List

from autoevals import ExactMatch
from braintrust import EvalAsync, current_span
from dotenv import load_dotenv
from elevenlabs import AgentConfig, ConversationSimulationSpecification, ElevenLabs


LANGUAGES = ["english", "spanish", "french", "german", "italian"]

FALLBACK_TEXTS = {
    "english": [
        "I cannot access my account.",
        "My latest bill looks incorrect.",
        "I need help resetting my password.",
    ],
    "spanish": [
        "No puedo acceder a mi cuenta.",
        "Necesito ayuda para restablecer mi contrasena.",
        "Mi factura tiene un cobro que no reconozco.",
    ],
    "french": [
        "Je ne peux pas acceder a mon compte.",
        "J'ai besoin d'aide pour reinitialiser mon mot de passe.",
        "Ma facture contient un montant incorrect.",
    ],
    "german": [
        "Ich kann mich nicht in mein Konto einloggen.",
        "Ich brauche Hilfe beim Zurucksetzen meines Passworts.",
        "Auf meiner Rechnung steht eine falsche Gebuhr.",
    ],
    "italian": [
        "Non riesco ad accedere al mio account.",
        "Ho bisogno di aiuto per reimpostare la password.",
        "La mia fattura mostra un addebito errato.",
    ],
}


def _to_plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "__dict__"):
        return vars(value)
    return value


def _extract_text_fragments(value: Any) -> List[str]:
    value = _to_plain(value)
    found: List[str] = []

    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            key_lower = str(key).lower()
            if isinstance(item, str) and any(
                token in key_lower
                for token in ["text", "message", "response", "content", "transcript"]
            ):
                found.append(item)
            found.extend(_extract_text_fragments(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            found.extend(_extract_text_fragments(item))

    return found


def _normalize_language(text: str) -> str:
    lowered = text.lower()
    for lang in LANGUAGES:
        if re.search(rf"\b{lang}\b", lowered):
            return lang
    return "unknown"


def _build_eval_data(limit: int = 20) -> List[Dict[str, Any]]:
    examples: List[Dict[str, Any]] = []
    per_language = limit // len(LANGUAGES)
    remainder = limit % len(LANGUAGES)

    for idx, language in enumerate(LANGUAGES):
        num = per_language + (1 if idx < remainder else 0)
        for _ in range(num):
            text = random.choice(FALLBACK_TEXTS[language])
            examples.append(
                {
                    "input": {
                        "simulated_user": {
                            "text": text,
                            "language": language,
                        }
                    },
                    "expected": language,
                    "metadata": {"raw_text": text, "expected_language": language},
                }
            )

    random.shuffle(examples)
    return examples


def _run_simulation(
    client: ElevenLabs,
    agent_id: str,
    user_text: str,
    user_language: str,
) -> Any:
    spec = ConversationSimulationSpecification(
        simulated_user_config=AgentConfig(
            first_message=user_text,
            language=user_language,
            disable_first_message_interruptions=False,
        )
    )
    return client.conversational_ai.agents.simulate_conversation(
        agent_id=agent_id,
        simulation_specification=spec,
        new_turns_limit=6,
    )


def _task_factory(client: ElevenLabs, agent_id: str):
    def task_func(example: Dict[str, Any]) -> str:
        input_data = example.get("input", example)
        simulated_user = input_data.get("simulated_user", {})
        user_text = simulated_user.get("text", "")
        user_language = simulated_user.get("language", "english")

        if not user_text:
            return "error"

        try:
            result = _run_simulation(client, agent_id, user_text, user_language)
            fragments = _extract_text_fragments(result)
            merged = "\n".join(fragments)
            prediction = _normalize_language(merged)

            current_span().log(
                metadata={
                    "expected_language": example.get("expected"),
                    "raw_text": example.get("metadata", {}).get("raw_text"),
                    "prediction_text_preview": merged[:500],
                }
            )

            return prediction
        except Exception as exc:
            current_span().log(
                metadata={
                    "expected_language": example.get("expected"),
                    "raw_text": example.get("metadata", {}).get("raw_text"),
                    "error": str(exc),
                }
            )
            return "error"

    return task_func


async def main() -> None:
    load_dotenv()
    agent_id = os.environ.get("ELEVENLABS_AGENT_ID")
    api_key = os.environ.get("ELEVENLABS_API_KEY")

    if not agent_id:
        raise ValueError("ELEVENLABS_AGENT_ID is required")

    client = ElevenLabs(api_key=api_key)
    task_func = _task_factory(client, agent_id)

    await EvalAsync(
        "ElevenLabs Voice Agent Language Eval",
        data=lambda: _build_eval_data(limit=20),
        task=task_func,
        scores=[ExactMatch],
        metadata={
            "provider": "elevenlabs",
            "agent_id": agent_id,
            "task": "language_classification",
            "sdk_method": "conversational_ai.agents.simulate_conversation",
        },
        experiment_name="elevenlabs-language-classification-eval",
    )


if __name__ == "__main__":
    asyncio.run(main())
