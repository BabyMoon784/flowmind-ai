
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient

import vision_service
from file_routes import router


app = FastAPI()
app.include_router(router)


@pytest.fixture
def client():
    return TestClient(app)


def make_png():
    buffer = BytesIO()

    image = Image.new(
        "RGB",
        (120, 80),
        "white",
    )

    image.save(buffer, format="PNG")

    return buffer.getvalue()


def upload(client, filename, content):
    return client.post(
        "/attachments/analyze-image",
        files={
            "file": (
                filename,
                content,
            )
        },
    )


def test_valid_png(monkeypatch, client):
    captured = {}

    class FakeCompletions:

        def create(self, **kwargs):
            captured.update(kwargs)

            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(
                            content=(
                                "这是一张算法题截图，"
                                "内容涉及动态规划。"
                            )
                        ),
                    )
                ]
            )

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=FakeCompletions()
        )
    )

    monkeypatch.setattr(
        vision_service.ai_service,
        "client",
        fake_client,
    )

    response = upload(
        client,
        "algorithm.png",
        make_png(),
    )

    assert response.status_code == 200

    data = response.json()

    assert data["filename"] == "algorithm.png"
    assert data["saved"] is False
    assert "动态规划" in data["text"]

    assert captured["model"] == "deepseek-flash"

    content = captured["messages"][1]["content"]

    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"

    image_url = content[1]["image_url"]["url"]

    assert image_url.startswith(
        "data:image/png;base64,"
    )


def test_invalid_image(client):
    response = upload(
        client,
        "bad.png",
        b"not really an image",
    )

    assert response.status_code == 422


def test_wrong_extension(client):
    response = upload(
        client,
        "test.exe",
        make_png(),
    )

    assert response.status_code == 422


def test_format_mismatch(client):
    response = upload(
        client,
        "photo.jpg",
        make_png(),
    )

    assert response.status_code == 422


def test_image_too_large(client):
    response = upload(
        client,
        "huge.png",
        b"x" * (5 * 1024 * 1024 + 1),
    )

    assert response.status_code == 413


def test_missing_api_key(
    monkeypatch,
    client,
):
    monkeypatch.setattr(
        vision_service.ai_service,
        "client",
        None,
    )

    response = upload(
        client,
        "test.png",
        make_png(),
    )

    assert response.status_code == 503
