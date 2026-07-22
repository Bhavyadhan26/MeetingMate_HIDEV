import json
import unittest

from backend.app.agents.groq_llm import extract_json_object
from backend.app.services.deepgram import speaker_tagged_transcript


class AIIntegrationHelpersTests(unittest.TestCase):
    def test_groq_json_extractor_accepts_wrapped_json(self) -> None:
        payload = extract_json_object('Here is the result:\n{"decisions":[{"text":"use Qdrant"}]}')

        self.assertEqual(payload["decisions"][0]["text"], "use Qdrant")

    def test_deepgram_utterances_become_speaker_tagged_transcript(self) -> None:
        response = {
            "results": {
                "utterances": [
                    {"speaker": 0, "transcript": "We decided to use Qdrant."},
                    {"speaker": 1, "transcript": "I will document the schema by Friday."},
                ]
            }
        }

        transcript = speaker_tagged_transcript(response)

        self.assertIn("Speaker 0: We decided to use Qdrant.", transcript)
        self.assertIn("Speaker 1: I will document the schema by Friday.", transcript)

    def test_deepgram_words_fallback_groups_by_speaker(self) -> None:
        response = {
            "results": {
                "channels": [
                    {
                        "alternatives": [
                            {
                                "words": [
                                    {"speaker": 0, "punctuated_word": "We"},
                                    {"speaker": 0, "punctuated_word": "decided."},
                                    {"speaker": 1, "punctuated_word": "Done."},
                                ]
                            }
                        ]
                    }
                ]
            }
        }

        self.assertEqual(speaker_tagged_transcript(response), "Speaker 0: We decided.\nSpeaker 1: Done.")


if __name__ == "__main__":
    unittest.main()
