import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.service import get_current_user
from app.database import get_db
from app.rag.service import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG / Documents"])

ALLOWED_TYPES = {"text/plain", "application/pdf", "text/markdown"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


class SearchRequest(BaseModel):
    query: str
    top_k: int = 3


@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # File type check
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sirf TXT aur MD files allowed hain. Aap ne bheja: {file.content_type}",
        )

    # File size check
    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File bohot badi hai. Max 5 MB allowed hai.",
        )

    # Content decode karo
    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File encoding galat hai. UTF-8 chahiye.",
        )

    if len(content.strip()) < 50:
        raise HTTPException(400, "File mein koi content nahi")

    # RAG index karo
    chunks_count = await rag_service.index_document(
        content=content,
        filename=file.filename,
        user_id=current_user.id,
        db=db,
    )

    return {
        "message":       f"Document '{file.filename}' successfully indexed!",
        "filename":      file.filename,
        "chunks_created": chunks_count,
        "size_bytes":    len(content_bytes),
    }


@router.get("/docs")
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apne indexed documents ki list dekho"""
    docs = await rag_service.get_user_documents(current_user.id, db)
    return {"documents": docs, "total": len(docs)}


@router.post("/search")
async def search_documents(
    data: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    results = await rag_service.search_documents(
        query=data.query,
        user_id=current_user.id,
        db=db,
        top_k=data.top_k,
    )

    return {
        "query":   data.query,
        "results": results,
        "count":   len(results),
    }