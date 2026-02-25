from app.services.volc_clients import parse_asr_text, parse_llm_text


def test_parse_asr_text_from_result_text() -> None:
    payload = {"result": {"text": "你好，世界"}}
    assert parse_asr_text(payload) == "你好，世界"


def test_parse_asr_text_from_utterances() -> None:
    payload = {
        "result": {
            "utterances": [
                {"text": "第一句"},
                {"text": "第二句"},
            ]
        }
    }
    assert parse_asr_text(payload) == "第一句\n第二句"


def test_parse_llm_text_from_choices_message() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "输出内容",
                }
            }
        ]
    }
    assert parse_llm_text(payload) == "输出内容"
