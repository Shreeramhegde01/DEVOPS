"""Fine-tunes a pre-trained (BERT-family) language model to extract course names from text.

This is token classification (named-entity recognition): every word gets a tag
    B-COURSE  first word of a course name
    I-COURSE  following words of the same course name
    O         any other word
e.g.   I  am  enrolled  in  Operating  Systems  .
       O  O   O         O   B-COURSE  I-COURSE  O

Environment variables:
    BASE_MODEL  pre-trained model to start from (default distilbert-base-cased;
                the lab manual's dbmdz/bert-large-cased-finetuned-conll03-english also works, but is 5x larger)
    MODEL_DIR   where the fine-tuned model is saved (default ./model)
    EPOCHS      training epochs (default 4)
"""
import os
import random

import pandas as pd
from datasets import Dataset
from transformers import (AutoModelForTokenClassification, AutoTokenizer, DataCollatorForTokenClassification,
                          Trainer, TrainingArguments, pipeline)

BASE_MODEL = os.environ.get("BASE_MODEL", "distilbert-base-cased")
MODEL_DIR = os.environ.get("MODEL_DIR", "model")
EPOCHS = float(os.environ.get("EPOCHS", 4))
SEED = 42

LABELS = ["O", "B-COURSE", "I-COURSE"]
LABEL2ID = {label: i for i, label in enumerate(LABELS)}
ID2LABEL = {i: label for label, i in LABEL2ID.items()}

# Courses offered at the college (the five from the lab manual first).
COURSES = [
    "Introduction to Computer Science", "Advanced Mathematics", "Data Structures and Algorithms",
    "Operating Systems", "Machine Learning", "DevOps", "Computer Networks", "Database Management Systems",
    "Cloud Computing", "Software Engineering", "Compiler Design", "Theory of Computation",
    "Discrete Mathematics", "Digital Logic Design", "Computer Organization and Architecture",
    "Big Data Analytics", "Cryptography and Network Security", "Internet of Things", "Deep Learning",
    "Natural Language Processing", "Object Oriented Programming", "Web Technologies", "Linear Algebra",
    "Engineering Physics", "Engineering Chemistry", "Probability and Statistics",
    "Human Computer Interaction", "Distributed Systems", "Blockchain Technology", "Computer Graphics",
    "Microprocessors and Microcontrollers", "Introduction to Python Programming", "Artificial Intelligence",
    "Design and Analysis of Algorithms", "Unix System Programming", "Software Testing",
]
# Never shown during training - used to check that the model generalises to unseen course names.
HELD_OUT = ["Introduction to Artificial Intelligence", "Cyber Security", "Mobile Application Development",
            "Data Mining", "Advanced Computer Architecture"]

TEMPLATES = [
    "{c}", "{c} .", "{c} course",
    "I am enrolled in {c} .", "The college offers {c} this semester .", "Has anyone taken {c} with Prof. Rao ?",
    "Registration for {c} closes on Friday .", "My favourite course is {c} .",
    "We have a lab for {c} tomorrow morning .", "Is {c} an elective or a core subject ?",
    "She scored an A in {c} last year .", "The syllabus for {c} was updated .", "Please share the notes for {c} .",
    "{c} is taught by the ISE department .", "Our timetable has {c} on Monday .",
    "I want to drop {c} and take something else .", "The exam for {c} is next week .",
    "Students who passed {c} can register for {c2} .", "This semester I have {c} , {c2} and {c3} .",
    "Which is harder , {c} or {c2} ?", "{c} and {c2} are both offered in the fifth semester .",
    "Courses offered : {c} , {c2} , {c3} .", "Can I audit {c} ?", "Who teaches {c} this year ?",
]
NEGATIVES = [
    "The canteen opens at eight .", "Our college fest is in December .",
    "Please submit the fee receipt at the office .", "The library will be closed on Sunday .",
    "I met Professor Sharma near the main gate .", "The bus leaves Bengaluru at seven .",
    "Placements start in August this year .", "The hostel wifi is slow today .",
    "Welcome to BMS College of Engineering .", "The Principal addressed the students on Monday .",
]


def build_example(template, courses, lowercase=False):
    """Turns a template + course names into (words, tags)."""
    fillers = {"{c}": courses[0], "{c2}": courses[1], "{c3}": courses[2]}
    words, tags = [], []
    for token in template.split():
        if token in fillers:
            course_words = (fillers[token].lower() if lowercase else fillers[token]).split()
            words += course_words
            tags += ["B-COURSE"] + ["I-COURSE"] * (len(course_words) - 1)
        else:
            words.append(token)
            tags.append("O")
    return words, tags


def make_dataset():
    rng = random.Random(SEED)
    rows = []
    for template in TEMPLATES:
        for _ in range(25):
            courses = rng.sample(COURSES, 3)
            words, tags = build_example(template, courses, lowercase=rng.random() < 0.15)
            rows.append({"words": words, "tags": tags})
    for sentence in NEGATIVES:
        for _ in range(8):
            rows.append({"words": sentence.split(), "tags": ["O"] * len(sentence.split())})
    rng.shuffle(rows)
    return Dataset.from_pandas(pd.DataFrame(rows))


def main():
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForTokenClassification.from_pretrained(
        BASE_MODEL, num_labels=len(LABELS), id2label=ID2LABEL, label2id=LABEL2ID,
        ignore_mismatched_sizes=True,   # replaces e.g. the 9-label CoNLL head with our 3 labels
    )

    def tokenize_and_align(batch):
        encoded = tokenizer(batch["words"], is_split_into_words=True, truncation=True, max_length=64)
        all_labels = []
        for i, tags in enumerate(batch["tags"]):
            labels, previous = [], None
            for word_id in encoded.word_ids(batch_index=i):
                # label only the first sub-token of each word; -100 = ignored by the loss
                labels.append(-100 if word_id is None or word_id == previous else LABEL2ID[tags[word_id]])
                previous = word_id
            all_labels.append(labels)
        encoded["labels"] = all_labels
        return encoded

    dataset = make_dataset()
    print(f"Training examples: {len(dataset)}")
    tokenized = dataset.map(tokenize_and_align, batched=True, remove_columns=["words", "tags"])

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir="results",
            num_train_epochs=EPOCHS,
            learning_rate=5e-5,
            per_device_train_batch_size=16,
            weight_decay=0.01,
            logging_steps=25,
            save_strategy="no",
            report_to="none",
            disable_tqdm=True,      # print the loss every 25 steps instead of a progress bar
            seed=SEED,
        ),
        train_dataset=tokenized,
        data_collator=DataCollatorForTokenClassification(tokenizer),
    )
    trainer.train()
    trainer.save_model(MODEL_DIR)
    tokenizer.save_pretrained(MODEL_DIR)
    print(f"Fine-tuned model saved to {MODEL_DIR}/")

    # Quick evaluation on course names the model has never seen
    extractor = pipeline("token-classification", model=MODEL_DIR, tokenizer=MODEL_DIR, aggregation_strategy="first")
    correct = 0
    for course in HELD_OUT:
        for sentence in (course, f"I am enrolled in {course} this semester."):
            found = [sentence[e["start"]:e["end"]] for e in extractor(sentence) if e["entity_group"] == "COURSE"]
            ok = found == [course]
            correct += ok
            print(f"  [{'OK ' if ok else 'MISS'}] {sentence!r:70} -> {found}")
    print(f"Held-out exact match: {correct}/{2 * len(HELD_OUT)}")


if __name__ == "__main__":
    main()
