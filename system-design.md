# System Design — Natural Language Insights Engine

## 1. Objective

The Natural Language Insights Engine allows a user to upload an arbitrary CSV dataset and ask analytical questions using natural language.

The system must:

* Accept previously unseen CSV schemas.
* Automatically understand the structure and basic semantics of the data.
* Answer supported analytical questions reliably.
* Refuse questions that cannot be answered from the available data.
* Handle ingestion and query execution asynchronously.
* Expose the functionality through an HTTP API.
* Provide a usable UI.
* Keep numerical computation deterministic and grounded in the dataset.

The central design principle is:

> **The LLM interprets the user's intent; deterministic application code performs the computation.**

---

# 2. High-Level Architecture

```text
                         ┌──────────────────────┐
                         │      Streamlit UI    │
                         └──────────┬───────────┘
                                    │
                                    │ HTTP
                                    ▼
                         ┌──────────────────────┐
                         │      FastAPI API     │
                         └──────────┬───────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  │                                   │
                  ▼                                   ▼
        ┌───────────────────┐              ┌───────────────────┐
        │ Dataset Ingestion │              │ Question Processing│
        └─────────┬─────────┘              └─────────┬─────────┘
                  │                                  │
                  ▼                                  ▼
        ┌───────────────────┐              ┌───────────────────┐
        │ Schema Profiler   │              │ Capability Check  │
        └─────────┬─────────┘              └─────────┬─────────┘
                  │                                  │
                  ▼                                  ▼
        ┌───────────────────┐              ┌───────────────────┐
        │ Profile Metadata  │              │ Gemini Planner    │
        └───────────────────┘              └─────────┬─────────┘
                                                     │
                                                     ▼
                                          ┌────────────────────┐
                                          │ Structured          │
                                          │ QueryPlan           │
                                          └─────────┬──────────┘
                                                    │
                                                    ▼
                                          ┌────────────────────┐
                                          │ Deterministic SQL  │
                                          │ Generator           │
                                          └─────────┬──────────┘
                                                    │
                                                    ▼
                                          ┌────────────────────┐
                                          │ SQLGlot Guardrails │
                                          └─────────┬──────────┘
                                                    │
                                                    ▼
                                          ┌────────────────────┐
                                          │ DuckDB Execution   │
                                          └─────────┬──────────┘
                                                    │
                                                    ▼
                                          ┌────────────────────┐
                                          │ Deterministic      │
                                          │ Answer Formatter   │
                                          └────────────────────┘
```

---

# 3. Main Components

## 3.1 FastAPI API

FastAPI is the HTTP interface between clients and the analytics engine.

Responsibilities include:

* CSV upload
* question submission
* job status retrieval
* request validation
* structured API errors
* HTTP status codes

Important endpoints include:

```text
POST /datasets
GET  /jobs/{job_id}
POST /questions
GET  /health
```

---

# 4. Dataset Ingestion

The ingestion pipeline starts when a user uploads a CSV.

```text
CSV Upload
    ↓
Validate filename/type
    ↓
Store CSV
    ↓
Create ingestion job
    ↓
Profile schema
    ↓
Save profile metadata
    ↓
Load CSV into DuckDB
    ↓
Mark job completed
```

The upload endpoint returns `202 Accepted` rather than waiting for the entire ingestion operation to finish.

Example:

```json
{
  "job_id": "job-id",
  "dataset_id": "dataset-id",
  "filename": "sales.csv",
  "status": "queued"
}
```

This allows ingestion to continue in the background.

---

# 5. Dynamic Schema Profiling

A key requirement is that the system must work with an unfamiliar CSV rather than relying on a hardcoded Online Retail schema.

The profiler dynamically discovers:

* column names
* logical data types
* row count
* distinct values
* null counts
* semantic roles

Example:

```text
customer_id → identifier
order_date  → date_or_time
country     → categorical
revenue     → numeric_measure
```

The profiler does not assume that columns are named:

```text
InvoiceNo
Description
Country
UnitPrice
Quantity
```

or any other sample-dataset-specific names.

This allows the same pipeline to work with a completely different CSV.

---

# 6. Schema Context

The resulting profile is persisted as metadata.

Example:

```json
{
  "row_count": 10000,
  "column_count": 6,
  "columns": [
    {
      "name": "customer_id",
      "type": "VARCHAR",
      "role": "identifier"
    },
    {
      "name": "order_date",
      "type": "DATE",
      "role": "date_or_time"
    },
    {
      "name": "region",
      "type": "VARCHAR",
      "role": "categorical"
    },
    {
      "name": "revenue",
      "type": "DOUBLE",
      "role": "numeric_measure"
    }
  ]
}
```

This profile becomes the context supplied to the query planner.

---

# 7. Analytical Question Flow

Once the dataset is ready, the question flow is:

```text
Natural-language question
          ↓
Request validation
          ↓
Dataset/profile lookup
          ↓
Capability check
          ↓
Gemini structured planning
          ↓
QueryPlan validation
          ↓
Deterministic SQL generation
          ↓
SQL validation
          ↓
DuckDB execution
          ↓
Deterministic answer formatting
          ↓
Job completed
```

---

# 8. Capability Check

Before calling the LLM, the application performs deterministic checks for certain clearly unsupported questions.

For example, a profit-margin question requires sufficient financial information.

If the dataset has neither:

```text
profit
```

nor enough information such as:

```text
revenue + cost
```

the system refuses the question.

This layer provides two benefits:

1. Avoids unnecessary LLM calls.
2. Provides predictable refusal behavior for obvious cases.

---

# 9. LLM Planner

Gemini is used only as a semantic planner.

The planner receives:

```text
Dataset schema
+
User question
```

and produces a structured `QueryPlan`.

For example:

```json
{
  "answerable": true,
  "question_type": "ranking",
  "measure_column": "revenue",
  "dimension_columns": ["product"],
  "aggregation": "sum",
  "sort_direction": "desc",
  "limit": 10
}
```

The planner is explicitly instructed to:

* use only available columns
* never invent columns
* never invent metrics
* never write SQL
* never calculate numerical results
* refuse when information is insufficient

---

# 10. Why Use a Structured QueryPlan?

An intermediate representation creates a clean boundary between natural-language understanding and database execution.

Instead of:

```text
Question → LLM → SQL
```

the system uses:

```text
Question
   ↓
LLM
   ↓
QueryPlan
   ↓
Deterministic SQL Generator
```

The QueryPlan is easier to:

* validate
* test
* inspect
* debug
* extend
* constrain

It also makes the LLM's role much smaller and safer.

---

# 11. Deterministic SQL Generation

The SQL generator is application code rather than LLM-generated code.

It maps supported question types to deterministic SQL patterns.

Current analytical patterns include:

```text
aggregation
ranking
comparison
frequency
revenue_share
product_pairs
monthly revenue
grouped analysis
```

For example:

```text
"What are the top 10 products by revenue?"
```

becomes a structured plan and then deterministic SQL.

The LLM does not decide how the final SQL is written.

---

# 12. SQL Guardrails

Before execution, generated SQL is validated using SQLGlot.

The validator checks:

### Single statement

Multiple SQL statements are rejected.

### SELECT only

Only read-only analytical queries are allowed.

### Authorized table

The query must reference the dataset's expected table.

### Authorized columns

Columns must exist in the profiled dataset.

### Forbidden operations

Operations such as:

```text
INSERT
UPDATE
DELETE
DROP
CREATE
ALTER
```

are rejected.

This provides defense in depth even though the SQL generator itself is deterministic.

---

# 13. DuckDB Execution

DuckDB is used as the analytical query engine.

Each dataset is associated with a DuckDB database file.

Example:

```text
data/
├── <dataset-id>.csv
├── db/
│   └── <dataset-id>.duckdb
└── profiles/
    └── <dataset-id>.json
```

DuckDB was selected because it:

* works directly with analytical workloads
* has strong SQL support
* requires no separate database server
* is lightweight
* is easy to reproduce locally
* works well for CSV-based analytics

---

# 14. Grounded Answer Generation

After DuckDB executes the query, the system receives structured rows.

The final response is generated deterministically from those rows.

The answer formatter does not ask the LLM to calculate or reinterpret the result.

For example:

```text
DuckDB:
one_time_customer_revenue = 125000
total_revenue = 500000
revenue_share_percentage = 25
```

The application formats:

```text
Customers who bought only once generated
125,000 in revenue, which represents 25%
of total revenue (500,000).
```

This ensures that the numerical answer remains grounded in the database result.

---

# 15. Async Job Architecture

Both ingestion and question execution are represented as jobs.

The current implementation uses a bounded `ThreadPoolExecutor`.

A job moves through:

```text
queued
   ↓
running
   ↓
completed
```

or:

```text
queued
   ↓
running
   ↓
failed
```

The client receives a job ID immediately and polls:

```text
GET /jobs/{job_id}
```

This avoids keeping an HTTP request open while long-running work executes.

---

# 16. Concurrency

The job manager uses a bounded worker pool.

Conceptually:

```text
             ┌───────────────┐
Job A ──────►│               │
Job B ──────►│ Worker Pool   │
Job C ──────►│               │
Job D ──────►│               │
             └───────────────┘
```

A bounded pool prevents unlimited concurrent work from being created inside the application.

Each job maintains independent state, so one failed job does not automatically fail other jobs.

---

# 17. Partial Failure

Different stages can fail independently.

For example:

```text
Upload
  ↓
Profiling FAILED
```

or:

```text
Upload
  ↓
Profiling
  ↓
DuckDB ingestion FAILED
```

or:

```text
Question
  ↓
Planner FAILED
```

or:

```text
Question
  ↓
SQL validation FAILED
```

The job manager catches exceptions and records the job as:

```text
failed
```

with a structured error.

The API does not expose a Python stack trace to the client.

---

# 18. Refusal Strategy

Refusal is treated as a first-class product behavior.

The system should not attempt to answer a question when the required information is missing.

Examples:

### Missing customer field

```text
Which customers bought only once?
```

If no customer identifier exists:

```text
Refuse.
```

### Missing revenue field

```text
What was the revenue last month?
```

If no suitable measure exists:

```text
Refuse.
```

### Insufficient financial information

```text
What was the profit margin?
```

If required revenue/cost/profit information is unavailable:

```text
Refuse.
```

This is preferable to generating a plausible but incorrect answer.

---

# 19. Handling an Unseen CSV

Consider an unseen dataset:

```text
transaction_number
transaction_date
market
item_name
net_sales
buyer
```

The system does not require any code change.

The profiler can identify:

```text
transaction_number → identifier
transaction_date   → date_or_time
market             → categorical
item_name          → text/categorical
net_sales          → numeric_measure
buyer              → identifier
```

A question such as:

```text
What are the top 10 items by sales?
```

can then be mapped to the available fields.

The key architectural property is that **the schema is supplied as runtime context rather than being encoded into prompts or SQL templates as fixed sample column names.**

---

# 20. What Could Break on an Unseen Schema?

Dynamic schema handling does not mean every possible question can be answered.

Potential failure cases include:

### Ambiguous numeric fields

A dataset may contain:

```text
cost
price
discount
revenue
```

The system must not assume that every numeric field is revenue.

### Missing entity identifiers

A dataset may contain customer names but no stable customer identifier.

Some customer-level analyses may therefore be unsafe.

### Missing order identifier

Product-pair analysis requires a reliable concept of an order or transaction.

### Ambiguous dates

A dataset may contain multiple date fields:

```text
order_date
ship_date
delivery_date
```

The planner must select the appropriate one based on the question.

### Unsupported semantics

A user may ask for:

```text
customer lifetime value
```

when the available dataset does not contain sufficient historical or financial information.

In such cases, refusal is preferable to guessing.

---

# 21. Key Design Decisions

## Decision 1 — Structured LLM planning

### Chosen

```text
Natural language → QueryPlan → SQL
```

### Alternative

```text
Natural language → LLM-generated SQL
```

### Reason

The structured approach provides stronger control over:

* allowed columns
* supported operations
* validation
* testing
* refusal behavior

The direct SQL approach would be simpler but would increase hallucination and security risks.

---

## Decision 2 — Deterministic SQL generation

### Chosen

SQL is generated from the QueryPlan by application code.

### Alternative

Ask Gemini to generate SQL directly.

### Reason

Analytical SQL contains important correctness decisions around:

* grouping
* joins
* distinct counts
* date boundaries
* percentages
* order-level logic

Keeping these deterministic makes the system more reproducible.

---

## Decision 3 — DuckDB

### Chosen

DuckDB as the analytical engine.

### Alternative

PostgreSQL or a cloud warehouse.

### Reason

DuckDB provides analytical SQL without requiring infrastructure.

For this assignment, it gives a strong balance of:

```text
simplicity + performance + reproducibility
```

A production deployment could use a warehouse or managed database depending on scale.

---

## Decision 4 — In-process job manager

### Chosen

Bounded `ThreadPoolExecutor`.

### Alternative

Redis/Celery, RabbitMQ, Kafka, or a cloud queue.

### Reason

The assignment requires asynchronous processing but does not require distributed deployment.

The current approach demonstrates:

* job IDs
* queueing
* status tracking
* concurrent work
* failure handling

For production, job state should be durable and workers should be independently scalable.

---

# 22. Error Handling

The API uses structured errors.

Example:

```json
{
  "detail": {
    "code": "INVALID_FILE_TYPE",
    "message": "Only CSV files are supported."
  }
}
```

Important error categories include:

```text
INVALID_FILENAME
INVALID_FILE_TYPE
FILE_TOO_LARGE
FILE_STORAGE_ERROR
UPLOAD_FAILED
JOB_NOT_FOUND
JOB_FAILED
```

The API uses appropriate HTTP status codes such as:

```text
400 → invalid request
404 → unknown job
413 → file too large
202 → asynchronous operation accepted
```

---

# 23. Security Model

The user does not provide arbitrary SQL.

Instead:

```text
Natural Language
      ↓
Structured QueryPlan
      ↓
Deterministic SQL
      ↓
SQLGlot validation
      ↓
DuckDB
```

The SQL validator ensures that the query:

* is a single statement
* is read-only
* references the expected table
* references known columns

This substantially reduces the attack surface compared with executing user-provided SQL directly.

---

# 24. Testing Strategy

The test suite focuses heavily on deterministic components.

Current tests cover:

```text
Health endpoint
Job completion
Job failure
Unknown jobs
CSV loading
Schema profiling
CSV upload
Invalid file rejection
```

The goal is to keep the majority of the pipeline testable without requiring a live Gemini request.

The architecture makes this possible because:

```text
LLM planning
```

is separated from:

```text
SQL generation
SQL validation
SQL execution
Answer formatting
```

---

# 25. Observability

The current assignment implementation keeps observability lightweight.

Useful production metrics would include:

```text
upload latency
profiling latency
ingestion latency
LLM latency
SQL execution latency
job queue depth
job failure rate
refusal rate
query success rate
```

Structured logs should include:

```text
request ID
dataset ID
job ID
question type
execution status
latency
error code
```

This would make production debugging much easier.

---

# 26. Caching Opportunity

Repeated questions could be cached.

A possible cache key is:

```text
dataset_id
+
dataset_version
+
normalized_question
```

The dataset version is important because the same question should not return a result generated against an older dataset.

Caching would reduce:

* DuckDB execution
* planner calls where applicable
* response latency

---

# 27. Production Architecture

The current architecture is intentionally local and lightweight.

A production system could evolve into:

```text
                       ┌─────────────────┐
                       │ Load Balancer   │
                       └────────┬────────┘
                                │
                    ┌───────────┴───────────┐
                    │                       │
             ┌──────▼──────┐        ┌──────▼──────┐
             │ API Worker  │        │ API Worker  │
             └──────┬──────┘        └──────┬──────┘
                    │                       │
                    └───────────┬───────────┘
                                │
                         ┌──────▼──────┐
                         │ Job Queue   │
                         └──────┬──────┘
                                │
                    ┌───────────▼───────────┐
                    │ Background Workers   │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
       ┌──────▼──────┐   ┌──────▼──────┐   ┌─────▼─────┐
       │ Object      │   │ Metadata DB │   │ Analytics │
       │ Storage     │   │             │   │ Engine    │
       └─────────────┘   └─────────────┘   └───────────┘
```

Potential production technologies could include:

* object storage for CSV files
* PostgreSQL for metadata and jobs
* Redis or a durable queue
* independently scalable workers
* managed analytical infrastructure
* centralized logging and tracing

---

# 28. Scalability Considerations

The current implementation is suitable for a local assignment/demo environment.

At larger scale, several changes would be required.

### Large files

Instead of local disk:

```text
Object Storage
```

could be used.

### Large datasets

DuckDB may be replaced or supplemented by:

```text
warehouse / distributed query engine
```

depending on workload.

### Multiple API instances

The in-memory job manager would need to become:

```text
durable queue + persistent job state
```

### Concurrent users

Resource controls would be needed for:

* worker concurrency
* query execution
* memory
* file size
* request rate

---

# 29. Future Improvements

## Short-term

* Expand analytical question types.
* Add more deterministic SQL templates.
* Increase unit-test coverage.
* Add explicit planner tests.
* Add query timeouts.
* Improve structured logging.

## Medium-term

* Add query result caching.
* Add evaluation datasets.
* Add chart recommendations.
* Add conversational follow-up questions.
* Add richer semantic profiling.

## Production

* Durable job queue.
* Persistent metadata.
* Object storage.
* Authentication and authorization.
* Rate limiting.
* Distributed workers.
* Centralized observability.

---

# 30. Trade-offs

The architecture intentionally prioritizes:

```text
Correctness
    >
Flexibility of LLM-generated SQL
```

and:

```text
Simple local deployment
    >
Production-scale infrastructure
```

and:

```text
Predictable refusal
    >
Attempting to answer every question
```

These trade-offs are appropriate for the assignment because correctness, extensibility, and engineering reliability are more important than deploying a fully distributed production system.

---

# 31. End-to-End Example

Consider:

```text
CSV:
customer_id
order_id
order_date
country
product
revenue
```

User asks:

```text
Which customers bought only once?
```

The system performs:

```text
1. Retrieve dataset profile
              ↓
2. Confirm customer identifier exists
              ↓
3. Confirm order identifier exists
              ↓
4. Send schema + question to Gemini
              ↓
5. Gemini returns:

   question_type = frequency
   customer_column = customer_id
   order_column = order_id

              ↓
6. Deterministic SQL generator creates query
              ↓
7. SQLGlot validates query
              ↓
8. DuckDB executes query
              ↓
9. Application counts returned customers
              ↓
10. Deterministic answer formatter returns:

    "X customer(s) bought only once."
```

At no point does the LLM calculate `X`.

---

# 32. Core Reliability Principle

The most important reliability property of the system is the separation of responsibilities:

```text
┌─────────────────────────────────────┐
│ LLM                                 │
│                                     │
│ Understand intent                   │
│ Select available semantic fields    │
│ Produce structured QueryPlan        │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│ Application                         │
│                                     │
│ Validate plan                       │
│ Generate SQL                        │
│ Validate SQL                        │
│ Execute SQL                         │
│ Format result                       │
└─────────────────────────────────────┘
```

This minimizes the amount of trusted computation delegated to a probabilistic model.

---

# 33. Conclusion

The Natural Language Insights Engine uses a layered architecture to combine the flexibility of natural-language interfaces with deterministic analytical execution.

The system is designed around five principles:

1. **Understand the schema dynamically.**
2. **Use the LLM for intent interpretation rather than computation.**
3. **Generate SQL deterministically.**
4. **Validate every query before execution.**
5. **Prefer a correct refusal over an incorrect answer.**

The resulting architecture is lightweight enough for local execution while providing a clear path toward a production system with durable jobs, scalable workers, persistent metadata, observability, and stronger semantic modeling.
