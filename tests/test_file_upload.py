
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docx import Document
from pypdf import PdfWriter

from file_routes import router


# 独立测试附件路由，避免修改真实数据库
app = FastAPI()
app.include_router(router)

client = TestClient(app)


def upload(filename, content):

    return client.post(
        "/attachments/extract",
        files={
            "file": (
                filename,
                content,
            )
        },
    )


def test_txt():

    response = upload(
        "notes.txt",
        "C++ 学习计划".encode("utf-8"),
    )

    assert response.status_code == 200

    data = response.json()

    assert "C++" in data["text"]
    assert data["saved"] is False


def test_markdown():

    response = upload(
        "todo.md",
        b"# hello world",
    )

    assert response.status_code == 200

    assert (
        response.json()["file_type"]
        == "md"
    )


def test_invalid_extension():

    response = upload(
        "image.png",
        b"123",
    )

    assert response.status_code == 422


def test_large_file():

    response = upload(
        "huge.txt",
        b"a" * (5 * 1024 * 1024 + 1),
    )

    assert response.status_code == 413


def test_empty():

    response = upload(
        "empty.md",
        b"",
    )

    assert response.status_code == 422


def test_invalid_pdf():

    response = upload(
        "fake.pdf",
        b"not really a pdf",
    )

    assert response.status_code == 422


def test_scanned_pdf():

    writer = PdfWriter()

    writer.add_blank_page(
        width=300,
        height=300,
    )

    buffer = BytesIO()

    writer.write(buffer)

    response = upload(
        "scan.pdf",
        buffer.getvalue(),
    )

    assert response.status_code == 422


def test_docx():

    document = Document()

    document.add_paragraph(
        "动态规划与并查集"
    )

    buffer = BytesIO()

    document.save(buffer)

    response = upload(
        "lesson.docx",
        buffer.getvalue(),
    )

    assert response.status_code == 200

    assert (
        "动态规划"
        in response.json()["text"]
    )
