from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from datetime import datetime, timezone
import logging

# تعريف الراوتر
router = APIRouter()

@router.get("/")
async def root():
    """نقطة النهاية الرئيسية"""
    return JSONResponse({
        "status": "ok",
        "message": "Service is running",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@router.get("/health")
async def health_check():
    """فحص صحة الخدمة"""
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

@router.options("/health")
async def health_options():
    """معالجة طلبات OPTIONS للصحة"""
    return JSONResponse({
        "status": "ok",
        "allowed_methods": ["GET", "OPTIONS"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

# التعامل مع الأخطاء
@router.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """معالج الأخطاء العام"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": str(exc.detail),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )