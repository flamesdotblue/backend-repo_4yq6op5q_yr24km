import os
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests

from database import db, create_document, get_documents

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source: Optional[str] = Field("auto", description="Source language code or 'auto'")
    target: str = Field(..., description="Target language code, e.g., 'en', 'es'")


@app.get("/")
def read_root():
    return {"message": "Translator Backend Running"}


@app.post("/translate")
def translate(req: TranslateRequest):
    """
    Translate text using LibreTranslate public API.
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    try:
        # Using libretranslate.de which doesn't require API key for light usage
        resp = requests.post(
            "https://libretranslate.de/translate",
            data={
                "q": req.text,
                "source": req.source or "auto",
                "target": req.target,
                "format": "text",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Translation service error: {resp.text[:200]}")
        data = resp.json()
        translated = data.get("translatedText")
        if not translated:
            raise HTTPException(status_code=502, detail="Invalid response from translation service")
        return {"translated": translated}
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Translation service timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/themes")
def list_themes(limit: Optional[int] = 50):
    """List saved themes from the database"""
    try:
        docs = get_documents("theme", limit=limit)
        # Convert ObjectId to string for JSON serialization
        for d in docs:
            if "_id" in d:
                d["id"] = str(d["_id"])  # add friendly id
                del d["_id"]
        return {"items": docs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ThemeCreate(BaseModel):
    name: str
    primary: str = "#4f46e5"
    background_from: str = "#ffffff"
    background_to: str = "#f5f3ff"
    text: str = "#111827"
    mode: str = "light"
    font: Optional[str] = "Inter"


@app.post("/themes")
def create_theme(theme: ThemeCreate):
    """Create a new theme"""
    try:
        inserted_id = create_document("theme", theme.model_dump())
        return {"id": inserted_id, **theme.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
