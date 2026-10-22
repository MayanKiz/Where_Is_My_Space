from app.assistant import AssistantSettings, answer, build_context, fallback_answer


def test_context_strips_private_fields():
    context = build_context([
        {
            "name": "Library",
            "location": "Block A",
            "capacity": 20,
            "occupied": 5,
            "status": "Available",
            "stream_url": "rtsp://secret-camera",
            "source_id": "private-id",
        }
    ])
    assert context["spaces"] == [{
        "name": "Library",
        "location": "Block A",
        "capacity": 20,
        "occupied": 5,
        "status": "Available",
        "observed_at": None,
    }]
    assert "stream_url" not in str(context)


def test_fallback_recommends_least_occupied_space():
    zones = [
        {"name": "Busy Hall", "location": "A", "capacity": 10, "occupied": 8, "status": "Busy"},
        {"name": "Quiet Room", "location": "B", "capacity": 10, "occupied": 2, "status": "Available"},
    ]
    answer_text, provider = answer("Where can I study quietly?", zones, [], AssistantSettings())
    assert provider == "local-fallback"
    assert "Quiet Room" in answer_text


def test_fallback_is_honest_without_live_data():
    assert "live space data" in fallback_answer("Where is free?", [])
