"""Course Name Extraction API - serves the fine-tuned model (see train.py) with FastAPI."""
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from transformers import pipeline

MODEL_DIR = os.environ.get("MODEL_DIR", "model")

# aggregation_strategy="first" merges B-COURSE / I-COURSE word pieces into whole course names
extractor = pipeline("token-classification", model=MODEL_DIR, tokenizer=MODEL_DIR, aggregation_strategy="first")

app = FastAPI(title="Course Name Extraction API", version="1.0")


class CourseRequest(BaseModel):
    text: str


@app.post("/extract-course-name/")
def extract_course_name(request: CourseRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")
    courses = [
        {"name": text[e["start"]:e["end"]], "score": round(float(e["score"]), 3)}
        for e in extractor(text)
        if e["entity_group"] == "COURSE"
    ]
    return {"text": text, "extracted_course_names": [c["name"] for c in courses], "details": courses}


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_DIR}
