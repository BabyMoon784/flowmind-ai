
"""
FlowMind AI - 附件接口

支持：
1. TXT / MD / PDF / DOCX 文本提取
2. PNG / JPG / JPEG 图片理解
3. DeepSeek API 错误诊断
"""

import logging

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)

from openai import (
    APIStatusError,
    APIConnectionError,
    APITimeoutError,
    OpenAIError,
)

from file_extraction import (
    MAX_FILE_BYTES,
    FileExtractionError,
    extract_document,
)

from vision_service import (
    MAX_IMAGE_BYTES,
    VisionInputError,
    VisionResponseError,
    analyze_image,
)


router = APIRouter(
    tags=["Attachments"]
)

logger = logging.getLogger("uvicorn.error")


# ==========================================
# 1. 文档提取
# ==========================================

@router.post("/attachments/extract")
def extract_attachment(
    file: UploadFile = File(...),
):
    try:
        data = file.file.read(
            MAX_FILE_BYTES + 1
        )

        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="文件大小不能超过 5 MB",
            )

        return extract_document(
            file.filename or "",
            data,
        )

    except FileExtractionError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    finally:
        file.file.close()


# ==========================================
# 2. 图片理解
# ==========================================

@router.post("/attachments/analyze-image")
def analyze_image_attachment(
    file: UploadFile = File(...),
):
    try:
        data = file.file.read(
            MAX_IMAGE_BYTES + 1
        )

        if len(data) > MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="图片大小不能超过 5 MB",
            )

        logger.info(
            "收到图片理解请求：文件大小 %s 字节",
            len(data),
        )

        result = analyze_image(
            file.filename or "",
            data,
        )

        logger.info(
            "图片理解成功：返回 %s 个字符",
            result.get("character_count", 0),
        )

        return result

    # ======================================
    # 图片本身不合法
    # ======================================

    except VisionInputError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    # ======================================
    # 视觉模型返回空结果等
    # ======================================

    except VisionResponseError as exc:
        logger.error(
            "图片分析结果异常：%s",
            exc,
        )

        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    # ======================================
    # DeepSeek API 返回 4xx / 5xx
    # ======================================

    except APIStatusError as exc:
        logger.error(
            "DeepSeek API 请求失败："
            "上游 HTTP %s；错误详情：%s",
            exc.status_code,
            str(exc)[:1000],
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "DeepSeek API 返回错误："
                f"HTTP {exc.status_code}。"
                "请查看后端终端中的具体错误。"
            ),
        ) from exc

    # ======================================
    # DeepSeek 请求超时
    # ======================================

    except APITimeoutError as exc:
        logger.error(
            "DeepSeek 图片理解请求超时：%s",
            exc,
        )

        raise HTTPException(
            status_code=504,
            detail="DeepSeek 图片理解请求超时",
        ) from exc

    # ======================================
    # 无法连接 DeepSeek
    # ======================================

    except APIConnectionError as exc:
        logger.error(
            "无法连接 DeepSeek：%s",
            exc,
        )

        raise HTTPException(
            status_code=502,
            detail="无法连接 DeepSeek API，请检查网络",
        ) from exc

    # ======================================
    # 其他 DeepSeek SDK 异常
    # ======================================

    except OpenAIError as exc:
        logger.error(
            "DeepSeek SDK 异常：%s",
            str(exc)[:1000],
        )

        raise HTTPException(
            status_code=502,
            detail="DeepSeek SDK 请求失败，详见后端终端",
        ) from exc

    # ======================================
    # API Key 未配置等
    # ======================================

    except RuntimeError as exc:
        logger.error(
            "图片理解服务配置异常：%s",
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    finally:
        file.file.close()
