"""Router: /api/documents. Upload, list, view, download, remove.

Uploads are indexed on arrival, so a manual added here is searchable from the
ask bar seconds later with no rebuild and no restart. Rejections are returned
as 400 with the reason in plain language - "this does not look like
manufacturing documentation" is more useful to a supervisor than a 422 body.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.schemas import DocumentListResponse, DocumentMetaModel
from app.services import documents

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
def list_documents() -> DocumentListResponse:
    docs = documents.list_documents()
    return DocumentListResponse(
        documents=[DocumentMetaModel(**d.as_dict()) for d in docs],
        accepted_formats=sorted(documents.ALLOWED),
        max_bytes=documents.MAX_BYTES,
    )


@router.post("/documents", response_model=DocumentMetaModel, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    department: str = Form(""),
) -> DocumentMetaModel:
    raw = await file.read()
    try:
        meta = documents.save_upload(file.filename or "document", raw, department)
    except documents.DocumentRejected as exc:
        # 400, not 422: the request was well formed, the content was refused.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentMetaModel(**meta.as_dict())


@router.get("/documents/{doc_id}/download")
def download_document(doc_id: str):
    """The original bytes, exactly as uploaded."""
    meta = documents.get_meta(doc_id)
    path = documents.original_path(doc_id)
    if meta is None or path is None:
        raise HTTPException(status_code=404, detail=f"No document {doc_id}")
    return FileResponse(
        path,
        filename=meta.original_name or path.name,
        media_type="application/octet-stream",
    )


@router.delete("/documents/{doc_id}", status_code=204)
def delete_document(doc_id: str) -> None:
    """Uploads only. The SOP corpus is version-controlled, not user-editable."""
    meta = documents.get_meta(doc_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"No document {doc_id}")
    if meta.source != "upload":
        raise HTTPException(
            status_code=400,
            detail="Built-in SOPs are part of the repository and cannot be deleted here.",
        )
    documents.delete_upload(doc_id)
