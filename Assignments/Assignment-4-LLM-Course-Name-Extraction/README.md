# Assignment 4 – Fine-tuning an LLM for Course Name Extraction and Deploying it as a Docker Container

**Objective:** fine-tune a pre-trained language model to extract the names of courses offered at a college from
free text, and deploy it as a Docker container behind a FastAPI REST API.

```
"This semester I have Operating Systems, Cloud Computing and DevOps."
                              │
                 POST /extract-course-name/  (FastAPI, port 80)
                              │
         fine-tuned DistilBERT token classifier (B-COURSE / I-COURSE / O)
                              │
{"extracted_course_names": ["Operating Systems", "Cloud Computing", "DevOps"]}
```

## Files

| File | Purpose |
|------|---------|
| `train.py` | Builds the labelled dataset, fine-tunes the model, evaluates it on unseen course names, saves it to `model/` |
| `app.py` | FastAPI app: `POST /extract-course-name/`, `GET /health`, Swagger UI at `/docs` |
| `requirements.txt` | transformers, torch, datasets, accelerate, fastapi, uvicorn (pinned) |
| `Dockerfile` | Installs CPU PyTorch, **fine-tunes during `docker build`**, serves with uvicorn on port 80 |

## How the fine-tuning works

Course-name extraction is a **token classification** (named-entity recognition) task. Each word gets a tag:

| I | am | enrolled | in | Operating | Systems | . |
|---|----|----------|----|-----------|---------|---|
| O | O  | O        | O  | B-COURSE  | I-COURSE | O |

1. **Dataset (Step 2):** 36 course names (the manual's five – *Introduction to Computer Science, Advanced
   Mathematics, Data Structures and Algorithms, Operating Systems, Machine Learning* – plus the college's other
   courses) are placed into 24 sentence templates ("I am enrolled in {c}.", "Which is harder, {c} or {c2}?", ...),
   plus sentences with no course, giving ~680 labelled examples. They go through a pandas DataFrame into a
   Hugging Face `Dataset`, as in the manual.
2. **Tokenisation (Step 3):** words are split into word pieces; only the first piece of each word keeps its label
   (the rest get `-100` and are ignored by the loss).
3. **Model:** `distilbert-base-cased` with a new 3-label classification head. Case matters because course names
   are capitalised. The manual's `dbmdz/bert-large-cased-finetuned-conll03-english` also works
   (`docker build --build-arg BASE_MODEL=dbmdz/bert-large-cased-finetuned-conll03-english ...`) but is 5× larger
   and slower on a laptop CPU.
4. **Training:** Hugging Face `Trainer`, 4 epochs, lr 5e-5, batch 16 – about 1–3 minutes on a laptop CPU.
5. **Evaluation:** five course names that were **never** in the training data (e.g. *Introduction to Artificial
   Intelligence*, *Cyber Security*, *Data Mining*) are extracted from new sentences to check that the model generalises.

### What changed compared with the lab manual's code (and why)
| Manual | Problem | Here |
|--------|---------|------|
| `labels: [["Operating Systems"], ...]` | Token classification needs one **tag per token**, not the course string. `Trainer` cannot compute a loss from strings | B-/I-/O tags aligned to word pieces |
| Pre-trained CoNLL head (PER/ORG/LOC/MISC) | Has no COURSE label | New 3-label head (`ignore_mismatched_sizes=True`) |
| `evaluation_strategy="epoch"` without an eval set | Raises an error (and the argument was renamed in newer transformers) | Separate evaluation on held-out course names |
| `extracted_names = [request.text]  # Replace with logic` | Returned the input unchanged | `pipeline(..., aggregation_strategy="first")` groups tagged tokens into course names |
| Model trained in a notebook, not in the image | Container would ship an untrained model | Training runs inside `docker build` |

## Step 1 – Build the image (fine-tunes the model)
```bash
cd Assignments/Assignment-4-LLM-Course-Name-Extraction
docker build -t course-extraction-api .
# ... Training examples: 680
# {'loss': 0.41, 'epoch': 0.58} ... {'loss': 0.004, 'epoch': 4.0}
# Fine-tuned model saved to model/
#   [OK ] 'Introduction to Artificial Intelligence'                              -> ['Introduction to Artificial Intelligence']
#   [OK ] 'I am enrolled in Cyber Security this semester.'                       -> ['Cyber Security']
#   ...
# Held-out exact match: 9/10
```
(The first build downloads ~200 MB of CPU PyTorch and the ~260 MB base model; the exact loss values and
held-out score vary a little between machines.)

## Step 2 – Run the container
```bash
docker run -d --name course-api -p 80:80 course-extraction-api
# port 80 busy on Windows? use  -p 8080:80  and http://localhost:8080 below
docker logs course-api       # "Uvicorn running on http://0.0.0.0:80"
```

## Step 3 – Test the API
```bash
curl -X POST "http://localhost/extract-course-name/" -H "Content-Type: application/json" \
     -d '{"text": "Introduction to Artificial Intelligence"}'
# {"text":"Introduction to Artificial Intelligence",
#  "extracted_course_names":["Introduction to Artificial Intelligence"],
#  "details":[{"name":"Introduction to Artificial Intelligence","score":0.99}]}

curl -X POST "http://localhost/extract-course-name/" -H "Content-Type: application/json" \
     -d '{"text": "This semester I have Operating Systems, Cloud Computing and DevOps."}'
# {"extracted_course_names":["Operating Systems","Cloud Computing","DevOps"], ...}

curl -X POST "http://localhost/extract-course-name/" -H "Content-Type: application/json" \
     -d '{"text": "The canteen opens at eight."}'
# {"extracted_course_names":[], ...}
```
PowerShell:
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost/extract-course-name/ -ContentType "application/json" `
  -Body '{"text": "Has anyone taken Machine Learning with Prof. Rao?"}'
```
Interactive docs (Swagger UI): **http://localhost/docs**.

## Run without Docker (optional)
```bash
pip install torch==2.4.1+cpu --extra-index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python train.py
uvicorn app:app --reload --port 8000
```

## Cleanup
```bash
docker rm -f course-api && docker rmi course-extraction-api
```

## Q&A

1. **Primary objective?** – Fine-tune a pre-trained language model to extract college course names from text and
   deploy it as a Docker container with a FastAPI endpoint.
2. **Libraries needed?** – `transformers`, `torch`, `datasets`, `fastapi`, `uvicorn` (+ `accelerate`, which
   `Trainer` needs, and `pandas`).
3. **Data used for fine-tuning?** – Sentences that contain course names, with every word tagged B-COURSE /
   I-COURSE / O, plus sentences with no course.
4. **How is the dataset prepared?** – Rows are built in a pandas DataFrame and converted with
   `Dataset.from_pandas()`, then tokenised with the labels aligned to word pieces.
5. **Which function tokenises?** – `tokenize_and_align()` in `train.py`, applied with `dataset.map(..., batched=True)`
   (`is_split_into_words=True`, truncation).
6. **Which pre-trained model?** – `distilbert-base-cased` by default; the manual's
   `dbmdz/bert-large-cased-finetuned-conll03-english` can be chosen with `--build-arg BASE_MODEL=...`.
7. **Role of FastAPI?** – Exposes the model as a REST endpoint (`POST /extract-course-name/`) that takes text and
   returns the extracted course names, with automatic validation and Swagger docs.
8. **How is the container created?** – The Dockerfile installs the dependencies, runs `train.py` at build time so
   the fine-tuned model is inside the image, and starts uvicorn on port 80.
9. **Build command?** – `docker build -t course-extraction-api .`
10. **Run command?** – `docker run -d -p 80:80 course-extraction-api`

## Screenshots to capture
1. `docker build` output showing the training loss and held-out evaluation.
2. `docker ps` with the running container.
3. curl / Swagger requests and responses.
