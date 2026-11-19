
"""
FlowMind AI - 文件文本提取模块

支持：
- TXT
- Markdown
- PDF（文字版）
- DOCX

不保存文件，不调用 AI。
"""

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, BadZipFile

from docx import Document
from pypdf import PdfReader


MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 16000
MAX_PDF_PAGES = 25

MAX_DOCX_EXPANDED_BYTES = 20 * 1024 * 1024

SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".pdf",
    ".docx",
}


class FileExtractionError(ValueError):
    """文件不符合要求或无法解析。"""


def extract_document(
    filename: str,
    data: bytes,
) -> dict:

    # Windows / Unix 文件名统一处理
    safe_name = (
        filename.replace("\\", "/")
        .split("/")[-1]
        .strip()
    )

    extension = Path(safe_name).suffix.lower()

    if (
        not safe_name
        or extension not in SUPPORTED_EXTENSIONS
    ):
        raise FileExtractionError(
            "仅支持 .txt、.md、.pdf 和 .docx 文件"
        )

    if not data:
        raise FileExtractionError("文件为空")

    if len(data) > MAX_FILE_BYTES:
        raise FileExtractionError(
            "文件超过 5 MB"
        )

    try:

        # ======================================
        # TXT / Markdown
        # ======================================

        if extension in {".txt", ".md"}:

            if b"\x00" in data:
                raise FileExtractionError(
                    "文本文件包含二进制内容"
                )

            try:
                text = data.decode("utf-8-sig")

            except UnicodeDecodeError:
                text = data.decode("gb18030")

        # ======================================
        # PDF
        # ======================================

        elif extension == ".pdf":

            if not data.startswith(b"%PDF-"):
                raise FileExtractionError(
                    "不是有效的 PDF 文件"
                )

            reader = PdfReader(
                BytesIO(data),
                strict=False,
            )

            if reader.is_encrypted:
                raise FileExtractionError(
                    "暂不支持加密 PDF"
                )

            if len(reader.pages) > MAX_PDF_PAGES:
                raise FileExtractionError(
                    "PDF 超过 25 页，请拆分上传"
                )

            parts = []

            for page in reader.pages:

                parts.append(
                    page.extract_text() or ""
                )

                if (
                    sum(len(p) for p in parts)
                    > MAX_TEXT_CHARS
                ):
                    break

            text = "\n".join(parts)

        # ======================================
        # Word DOCX
        # ======================================

        else:

            # 防止异常压缩文件造成过大的解压开销
            try:

                with ZipFile(BytesIO(data)) as archive:

                    entries = archive.infolist()

                    total_size = sum(
                        item.file_size
                        for item in entries
                    )

                    if (
                        len(entries) > 500
                        or total_size
                        > MAX_DOCX_EXPANDED_BYTES
                    ):
                        raise FileExtractionError(
                            "Word 文档解压后体积过大"
                        )

                    if (
                        "word/document.xml"
                        not in archive.namelist()
                    ):
                        raise FileExtractionError(
                            "不是有效的 DOCX 文件"
                        )

            except BadZipFile as exc:
                raise FileExtractionError(
                    "不是有效的 DOCX 文件"
                ) from exc

            doc = Document(BytesIO(data))

            parts = [
                paragraph.text
                for paragraph in doc.paragraphs
                if paragraph.text.strip()
            ]

            # 提取表格文字
            for table in doc.tables:

                for row in table.rows:

                    parts.append(
                        " | ".join(
                            cell.text
                            for cell in row.cells
                        )
                    )

            text = "\n".join(parts)

    except FileExtractionError:
        raise

    except Exception as exc:
        raise FileExtractionError(
            "文件损坏、格式不正确或暂不支持此编码"
        ) from exc

    # ==========================================
    # 统一清洗与长度限制
    # ==========================================

    text = text.replace("\x00", "").strip()

    if not text:
        raise FileExtractionError(
            "未提取到可用文字；扫描版 PDF 暂不支持"
        )

    return {
        "filename": safe_name[:160],
        "file_type": extension.lstrip("."),
        "size_bytes": len(data),
        "text": text[:MAX_TEXT_CHARS],
        "character_count": min(
            len(text),
            MAX_TEXT_CHARS,
        ),
        "truncated": len(text) > MAX_TEXT_CHARS,
        "saved": False,
    }
