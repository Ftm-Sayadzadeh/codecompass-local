# M24 Acceptance Baseline Evaluation

## 1. Executive Summary

This archive preserves the retained M24 acceptance results before any later model validation. No indexing, retrieval, model, documentation, or provider request was rerun to create it. Fields absent from retained output are marked **اندازه گیری نشده** rather than reconstructed.

Final acceptance verdict: **ACCEPTANCE_ISSUES_FOUND**.

All three fresh indexes were structurally and vector complete. Search citations resolved correctly, but two semantic searches missed the expected target in the top five. The local Qwen baseline was mixed: one factual case was fully correct, several answers were incomplete or unsupported, two insufficient-evidence checks hallucinated nonexistent behavior, and two answers were truncated. Four retained OpenAI-compatible QA attempts produced no reviewable answer. The frontend was broadly functional, with one project-switch timing race.

## 2. Dataset Identity and Configuration

| Field | Value |
|---|---|
| Dataset | m24_acceptance_baseline |
| Recorded | 2026-09-02 |
| CodeCompass commit | 9634bdab32af0b262a7e1cae97aea0f251804f6f |
| Embedding | ollama / nomic-embed-text-local:latest / 768 dimensions |
| Local QA | ollama / qwen2.5-coder-3b-codecompass:latest |
| Search | lexical, semantic, hybrid |

## 3. Indexing Results

| Repository | Commit | Files | Symbols | Chunks | Vectors | Complete | Elapsed |
|---|---|---|---|---|---|---|---|
| Hospital-System | da0b1f8cf04f36d6281a5fd44b797ad195147633 | 33 | 409 | 409 | 409 | True | 100.465 s |
| CS-Bookstore | 56ee148f3b4b8bc1f4eaaf921e22f280fa14ad7a | 56 | 144 | 144 | 144 | True | 55.342 s |
| CodeCompass | 9634bdab32af0b262a7e1cae97aea0f251804f6f | 96 | 1220 | 1220 | 1220 | True | 43057.811 s |

CodeCompass elapsed wall time includes session interruptions and is not a comparable pure indexing latency. Every repository had exact SQLite/physical-Chroma ID equality and matching SQLite/active vector generations.

## 4. Search Results

Manual relevance scoring used only retained expected-target rank: rank 1 = 10, rank 2 = 8, and target absent from top 5 = 0. This is a descriptive baseline rule, not a statistical benchmark metric.

| Case | Repository | Lang | Method | Target rank | Top symbol | Relevance | Citation | Failure |
|---|---|---|---|---|---|---|---|---|
| SEARCH-H-EN-LEX | Hospital-System | English | lexical | 1 | Patient.__init__ | 10 | valid | اندازه گیری نشده |
| SEARCH-H-EN-SEM | Hospital-System | English | semantic | اندازه گیری نشده | HashTable.__init__ | 0 | valid | missed target |
| SEARCH-H-EN-HYB | Hospital-System | English | hybrid | 2 | HashTable.__init__ | 8 | valid | wrong ranking |
| SEARCH-H-FA-LEX | Hospital-System | Persian | lexical | 1 | QueueArray.dequeue | 10 | valid | اندازه گیری نشده |
| SEARCH-H-FA-SEM | Hospital-System | Persian | semantic | 2 | Queue.dequeue | 8 | valid | wrong ranking |
| SEARCH-H-FA-HYB | Hospital-System | Persian | hybrid | 1 | QueueArray.dequeue | 10 | valid | اندازه گیری نشده |
| SEARCH-B-EN-LEX | CS-Bookstore | English | lexical | 1 | Book.save | 10 | valid | اندازه گیری نشده |
| SEARCH-B-EN-SEM | CS-Bookstore | English | semantic | 1 | Book.save | 10 | valid | اندازه گیری نشده |
| SEARCH-B-EN-HYB | CS-Bookstore | English | hybrid | 1 | Book.save | 10 | valid | اندازه گیری نشده |
| SEARCH-B-FA-LEX | CS-Bookstore | Persian | lexical | 1 | CommentForm.clean_name | 10 | valid | اندازه گیری نشده |
| SEARCH-B-FA-SEM | CS-Bookstore | Persian | semantic | 1 | CommentForm.clean_name | 10 | valid | اندازه گیری نشده |
| SEARCH-B-FA-HYB | CS-Bookstore | Persian | hybrid | 1 | CommentForm.clean_name | 10 | valid | اندازه گیری نشده |
| SEARCH-C-EN-LEX | CodeCompass | English | lexical | 1 | APIRuntime.vector_generation_matches | 10 | valid | اندازه گیری نشده |
| SEARCH-C-EN-SEM | CodeCompass | English | semantic | 1 | APIRuntime.vector_generation_matches | 10 | valid | اندازه گیری نشده |
| SEARCH-C-EN-HYB | CodeCompass | English | hybrid | 1 | APIRuntime.vector_generation_matches | 10 | valid | اندازه گیری نشده |
| SEARCH-C-FA-LEX | CodeCompass | Persian | lexical | 1 | RepositoryIndexCoordinator.index_repository | 10 | valid | اندازه گیری نشده |
| SEARCH-C-FA-SEM | CodeCompass | Persian | semantic | اندازه گیری نشده | test_final_source_recheck_discards_candidate_and_preserves_previous_index.change_before_final_scan | 0 | valid | missed target |
| SEARCH-C-FA-HYB | CodeCompass | Persian | hybrid | 1 | RepositoryIndexCoordinator.index_repository | 10 | valid | اندازه گیری نشده |

The complete per-result payload (all ranks, paths, symbol types, line ranges, chunk IDs, and citation records) was not retained for all executions and is therefore **اندازه گیری نشده** in the authoritative JSON. Retained target ranks, top symbols, and successful source-navigation validation are preserved.

## 5. Grounded QA Results

| Case | Repository | Lang | Provider | Correct | Grounded | Citation | Hallucination | Completeness | Finish | Seconds |
|---|---|---|---|---|---|---|---|---|---|---|
| QA-H-EN | Hospital-System | English | ollama | 8 | 10 | 10 | none | partially complete | stop | 23.014 |
| QA-H-FA | Hospital-System | Persian | ollama | 6 | 8 | 10 | minor | complete | stop | 11.753 |
| QA-B-EN | CS-Bookstore | English | ollama | 7 | 7 | 10 | minor | complete | stop | 9.325 |
| QA-B-FA | CS-Bookstore | Persian | ollama | 5 | 6 | 10 | minor | partially complete | stop | 27.044 |
| QA-C-EN | CodeCompass | English | ollama | 10 | 10 | 10 | none | complete | stop | 18.495 |
| QA-C-FA | CodeCompass | Persian | ollama | 2 | 4 | 10 | major | incomplete | length | 58.827 |
| QA-H-INS | Hospital-System | English | ollama | 10 | 10 | اندازه گیری نشده | none | complete | stop | 12.81 |
| QA-B-INS | CS-Bookstore | Persian | ollama | 0 | 0 | اندازه گیری نشده | critical | incomplete | stop | 33.863 |
| QA-C-INS | CodeCompass | English | ollama | 0 | 0 | اندازه گیری نشده | critical | incomplete | length | 48.915 |
| QA-CLOUD-H-EN | Hospital-System | English | openai_compatible | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | 5.309 |
| QA-CLOUD-H-FA | Hospital-System | Persian | openai_compatible | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | 14.863 |
| QA-CLOUD-B-EN | CS-Bookstore | English | openai_compatible | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | 10.915 |
| QA-CLOUD-B-FA | CS-Bookstore | Persian | openai_compatible | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | اندازه گیری نشده | 15.518 |

### QA-H-EN - Hospital-System

**Question:** What attributes are assigned in Patient.__init__?

**Provider/model:** `ollama` / `qwen2.5-coder-3b-codecompass:latest`  
**Retrieval:** `hybrid`  
**Finish reason:** stop  
**Response time:** 23.014 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

In the `Patient.__init__` method, the following attributes are assigned:

- `first_name`
- `last_name`
- `national_id`
- `phone_num`
- `password`
- `gender`
- `city`
- `insurance_num`

The attribute `full_name` is calculated as a combination of `first_name` and `last_name`.

**Issue:** self.appointments was omitted.  
**Expected:** Enumerate all ten assigned attributes, including self.appointments.  
**Actual:** Nine expected attributes were covered; self.appointments was missing.  
**Severity/category:** medium / missing information

### QA-H-FA - Hospital-System

**Question:** متد QueueArray.dequeue در صف خالی و غیرخالی چه رفتاری دارد؟

**Provider/model:** `ollama` / `qwen2.5-coder-3b-codecompass:latest`  
**Retrieval:** `hybrid`  
**Finish reason:** stop  
**Response time:** 11.753 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

در صف خالی، متد `dequeue` باعث خطای "Queue is empty." است. در صف غیرخالی، ابتدا فرانت صف به یک واحد بروزرسانی شده و سپس عنصر در فرانت جدید برگردانده می‌شود.

**Issue:** The empty-queue return value was described as an error.  
**Expected:** Return the string Queue is empty. for an empty queue; otherwise increment front and return queue[front - 1].  
**Actual:** Called the returned string an error, while correctly summarizing the non-empty branch.  
**Severity/category:** medium / wrong interpretation

### QA-B-EN - CS-Bookstore

**Question:** How does Book.save populate the slug before saving?

**Provider/model:** `ollama` / `qwen2.5-coder-3b-codecompass:latest`  
**Retrieval:** `hybrid`  
**Finish reason:** stop  
**Response time:** 9.325 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

Book.save populates the slug before saving by checking if the slug attribute is empty. If it is, it uses the `slugify` function from the `slugify` module to generate a slug based on the title attribute and assigns it to the slug attribute. This ensures that every book has a unique slug before being saved to the database.

**Issue:** The answer asserted an unsupported uniqueness guarantee and imprecise slugify provenance.  
**Expected:** If slug is falsy, assign slugify(self.title), then call super().save(*args, **kwargs).  
**Actual:** Core assignment was correct, but uniqueness was claimed without source evidence and the super save call was omitted.  
**Severity/category:** medium / unsupported claim

### QA-B-FA - CS-Bookstore

**Question:** متد CommentForm.clean_name چه نام‌هایی را رد می‌کند و در حالت معتبر چه برمی‌گرداند؟

**Provider/model:** `ollama` / `qwen2.5-coder-3b-codecompass:latest`  
**Retrieval:** `hybrid`  
**Finish reason:** stop  
**Response time:** 27.044 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

متد `CommentForm.clean_name` رد می‌کند:

1. "نام معتبر نیست!" را در حالت معتبر برمی‌گرداند.

2. این متد یک فیلد نام (`name`) را بررسی می‌کند و از آن استفاده می‌کند.

3. اگر `name` خالی نباشد، فیلد را بررسی می‌کند:

   - اگر طول `name` بین 2 تا 250 کاراکتر باشد، فیلد را به عنوان نام معتبر درخواست می‌دهد.
   
   - اگر طول `name` کمتر از 2 یا بیشتر از 250 کاراکتر باشد، یک خطا (`ValidationError`) را به عنوان "نام معتبر نیست!" بررسی می‌دهد.

4. در حالت معتبر، `name` را به عنوان نام معتبر برمی‌گرداند.

**Issue:** The answer contradicted itself by saying the validation message is returned in the valid case.  
**Expected:** Reject names shorter than 2 or longer than 250 with ValidationError; return name when valid.  
**Actual:** Eventually states the correct bounds and return, but begins with a materially wrong statement.  
**Severity/category:** high / wrong interpretation

### QA-C-EN - CodeCompass

**Question:** How does APIRuntime.vector_generation_matches validate a project?

**Provider/model:** `ollama` / `qwen2.5-coder-3b-codecompass:latest`  
**Retrieval:** `hybrid`  
**Finish reason:** stop  
**Response time:** 18.495 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

APIRuntime.vector_generation_matches validates a project by checking two conditions:

1. If the `project.index_schema_version` or `project.vector_generation` is `None`, it returns `False`.

2. It attempts to retrieve the active generation of the vector index using `self.collection(project.id).active_generation()`. If this fails due to a `VectorIndexError`, it raises an APIError with status code 409, error code "vector_index_state_invalid", and message "Vector index state is invalid; re-index storage is required".

3. If the active generation matches the project's vector generation, it returns `True`. Otherwise, it returns `False`.

This method ensures that the project's vector generation metadata is consistent with the current state of the vector index.

### QA-C-FA - CodeCompass

**Question:** متد RepositoryIndexCoordinator.index_repository چگونه بین full و incremental انتخاب می‌کند؟

**Provider/model:** `ollama` / `qwen2.5-coder-3b-codecompass:latest`  
**Retrieval:** `hybrid`  
**Finish reason:** length  
**Response time:** 58.827 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

متد `RepositoryIndexCoordinator.index_repository` بین full و incremental انتخاب می‌کند با استفاده از چند ترین شرط:

1. **نوع پروژه**:
   - اگر `project_name` نشان داده شده، فراخوانی متد `_run_full` برای اجرای بسیار کامل (full rebuild) است.
   - در غیر این صورت، فراخوانی متد `_run_incremental` برای اجرای بخشی از بسیار کامل (incremental update) است.

2. **پروژه موجود**:
   - اگر پروژه موجود باشد (`existing is not None`), فراخوانی متد `_incremental_base` برای تعیین پایاندهای قابل افزودن است.
   - اگر پایاندهای قابل افزودن وجود داشته باشند (`base is not None`), فراخوانی متد `_run_incremental` برای اجرای بخشی از بسیار کامل است.

3. **پروژه ناموجود**:
   - اگر پروژه موجود نباشد (`existing is None`), فراخوانی متد `_run_full` برای اجرای بسیار کامل (full rebuild) است.

4. **نوع پروژه و پروژه موجود**:
   - اگر `project_name` نشان داده شده و پروژه موجود باشد (`existing is not None`), فراخوانی متد `_run_incremental` برای اجرای بخشی از بسیار کامل است.

5. **نوع پروژه و پروژه ناموجود**:
   - اگر `project_name` نشان داده شده و پروژه موجود نباشد (`existing is None`), فراخوانی متد `_run_full` برای اجرای بسیار کامل است.

6. **نوع پروژه و پایاندهای قابل افزودن**:
   - اگر `project_name` نش

**Issue:** The answer was truncated and included incorrect project_name decision logic.  
**Expected:** Use the existing project and validated incremental base when eligible; otherwise fall back to full indexing.  
**Actual:** Introduced contradictory and unsupported project_name conditions, then stopped at the token limit.  
**Severity/category:** high / truncated answer

### QA-H-INS - Hospital-System

**Question:** Where is Patient.email_verified assigned?

**Provider/model:** `ollama` / `qwen2.5-coder-3b-codecompass:latest`  
**Retrieval:** `hybrid`  
**Finish reason:** stop  
**Response time:** 12.81 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

Patient.email_verified is not assigned in the provided code context. The code does not contain any assignment to Patient.email_verified anywhere.

### QA-B-INS - CS-Bookstore

**Question:** تابع checkout پرداخت کتاب را چگونه انجام می‌دهد؟

**Provider/model:** `ollama` / `qwen2.5-coder-3b-codecompass:latest`  
**Retrieval:** `hybrid`  
**Finish reason:** stop  
**Response time:** 33.863 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

تابع checkout پرداخت کتاب را در فایل `store/views.py` انجام می‌دهد. 

در سطر 10-25 من زیر، تابع checkout به صورت زیر نوشته شده است:

```python
def checkout(request):
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            # اینجا کد پرداخت کتاب را انجام می‌دهد
            # ...
```

این تابع در صورتی که طرح checkout با استفاده از فرم `ReviewForm` ارسال شود، ابتدا فرم را بررسی می‌کند. اگر فرم معتبر باشد، پرداخت کتاب را انجام می‌دهد.

**Issue:** A nonexistent checkout function, source location, and implementation were fabricated.  
**Expected:** State that the retrieved evidence does not establish an implemented checkout/payment function.  
**Actual:** Invented store/views.py checkout code and claimed payment behavior.  
**Severity/category:** critical / hallucinated file/function/class

### QA-C-INS - CodeCompass

**Question:** How does RepositoryIndexCoordinator coordinate workers through Redis?

**Provider/model:** `ollama` / `qwen2.5-coder-3b-codecompass:latest`  
**Retrieval:** `hybrid`  
**Finish reason:** length  
**Response time:** 48.915 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

RepositoryIndexCoordinator coordinates workers through Redis by using the `begin_activation` and `end_activation` callbacks. These callbacks are set during initialization and are used to activate or deactivate the indexing process for a specific project.

Here's how it works:

1. **Initialization**: During the constructor (`__init__` method), the `begin_activation` callback is set to a lambda function that does nothing by default. This means that by default, no activation callbacks are triggered when starting an indexing session.

2. **Activation Callbacks**: The `activate` method within `_run_incremental.activate` sets the `activation_started` flag to `True`, calls the `begin_activation` callback with the project ID, and then activates the vector index using the staged data.

3. **Usage in Indexing Methods**: When indexing a repository (`index_repository` method), if an existing project is found, it checks for any changes since the last indexing session. If there are changes, it calls `_run_incremental` to perform an incremental update. This method uses the `begin_activation` callback to ensure that the indexing process is properly activated before starting.

4. **No-Op Mode**: If no existing project or no changes are detected, the `_run_full` method is called to perform a

**Issue:** Redis coordination was fabricated and the response truncated.  
**Expected:** State that the evidence does not show Redis-based coordination.  
**Actual:** Recast local activation callbacks as Redis worker coordination.  
**Severity/category:** critical / unsupported claim

### QA-CLOUD-H-EN - Hospital-System

**Question:** What attributes are assigned in Patient.__init__?

**Provider/model:** `openai_compatible` / `glm-5.3-flash`  
**Retrieval:** `hybrid`  
**Finish reason:** اندازه گیری نشده  
**Response time:** 5.309 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

اندازه گیری نشده - no reviewable answer was produced.

**Issue:** Safe API envelope reported qa_llm_failed; no answer was produced.  
**Expected:** Return a grounded answer.  
**Actual:** Provider-path failure before a reviewable answer.  
**Severity/category:** high / اندازه گیری نشده

### QA-CLOUD-H-FA - Hospital-System

**Question:** متد QueueArray.dequeue در صف خالی و غیرخالی چه رفتاری دارد؟

**Provider/model:** `openai_compatible` / `glm-5.3-flash`  
**Retrieval:** `hybrid`  
**Finish reason:** اندازه گیری نشده  
**Response time:** 14.863 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

اندازه گیری نشده - no reviewable answer was produced.

**Issue:** Safe API envelope reported qa_llm_failed; no answer was produced.  
**Expected:** Return a grounded answer.  
**Actual:** Provider-path failure before a reviewable answer.  
**Severity/category:** high / اندازه گیری نشده

### QA-CLOUD-B-EN - CS-Bookstore

**Question:** How does Book.save populate the slug before saving?

**Provider/model:** `openai_compatible` / `glm-5.3-flash`  
**Retrieval:** `hybrid`  
**Finish reason:** اندازه گیری نشده  
**Response time:** 10.915 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

اندازه گیری نشده - no reviewable answer was produced.

**Issue:** Safe API envelope reported qa_llm_failed; no answer was produced.  
**Expected:** Return a grounded answer.  
**Actual:** Provider-path failure before a reviewable answer.  
**Severity/category:** high / اندازه گیری نشده

### QA-CLOUD-B-FA - CS-Bookstore

**Question:** متد CommentForm.clean_name چه نام‌هایی را رد می‌کند و در حالت معتبر چه برمی‌گرداند؟

**Provider/model:** `openai_compatible` / `glm-5.3-flash`  
**Retrieval:** `hybrid`  
**Finish reason:** اندازه گیری نشده  
**Response time:** 15.518 s  
**Token information:** اندازه گیری نشده

**Exact retained answer:**

اندازه گیری نشده - no reviewable answer was produced.

**Issue:** Safe API envelope reported qa_llm_failed; no answer was produced.  
**Expected:** Return a grounded answer.  
**Actual:** Provider-path failure before a reviewable answer.  
**Severity/category:** high / اندازه گیری نشده

## 6. Function Documentation Results

| Case | Repository | Target | Purpose | Parameters | Return | Behavior | Dependencies | Citation | Overall |
|---|---|---|---|---|---|---|---|---|---|
| DOC-H | Hospital-System | Patient.__init__ | 10 | 10 | 10 | 10 | 10 | 10 | 10 |
| DOC-B | CS-Bookstore | CommentForm.clean_name | 7 | 10 | 10 | 8 | 10 | 10 | 8 |
| DOC-C | CodeCompass | APIRuntime.vector_generation_matches | 10 | 10 | 10 | 9 | 8 | 10 | 8 |

### DOC-H - `Patient.__init__`

Source: `models/patient.py:6-16`

**Summary:** Initializes a new Patient object with various attributes.

**Description:** The `__init__` method initializes a new patient instance with the provided first name, last name, national ID, phone number, password, gender, city, and insurance number. It also sets up an empty list for appointments and calculates the full name of the patient.

**Parameters:** self, first_name, last_name, national_id, phone_num, password, gender, city, insurance_num  
**Return:** اندازه گیری نشده  
**Raises:** None  
**Dependencies:** Appointments  
**Unsupported claims:** None

### DOC-B - `CommentForm.clean_name`

Source: `blog/forms.py:45-51`

**Summary:** متد `clean_name` برای کنترل نام در فرم خبرنامه ای می‌شود.

**Description:** این متد بررسی معتبر بودن و طول نام استفاده می‌کند. اگر نام نامعتبر یا طول آن به حدود 250 یا کمتر از 2 حرف باشد، خطا را می‌سازد.

**Parameters:** self  
**Return:** name  
**Raises:** forms.ValidationError  
**Dependencies:** None  
**Unsupported claims:** فرم خبرنامه

### DOC-C - `APIRuntime.vector_generation_matches`

Source: `src/codecompass/api/runtime.py:275-283`

**Summary:** Returns whether the canonical metadata names the active vector generation for a given project.

**Description:** This method checks if the canonical metadata of a project matches the active vector generation. It returns `True` if they match, otherwise `False`. If the project's index schema version or vector generation is not available, it returns `False`. The method also handles exceptions related to vector index errors and raises an API error with specific details.

**Parameters:** self, project  
**Return:** bool  
**Raises:** VectorIndexError, APIError  
**Dependencies:** collection, active_generation  
**Unsupported claims:** VectorIndexError was listed as a propagated raise even though it is caught and mapped to APIError.

## 7. Frontend Acceptance

| Repository | Action | Result | Issue/Note |
|---|---|---|---|
| Hospital-System | indexing flow | اندازه گیری نشده | Fresh indexing was executed through the production backend path, not through this repository's frontend action. |
| Hospital-System | search UI | PASS | اندازه گیری نشده |
| Hospital-System | Persian query | اندازه گیری نشده | Persian UI query was exercised on CS-Bookstore; Hospital Persian search was API-validated. |
| Hospital-System | English query | PASS | اندازه گیری نشده |
| Hospital-System | result selection | PASS | اندازه گیری نشده |
| Hospital-System | Monaco navigation | PASS | 11 expected highlighted source lines were observed for Patient.__init__. |
| Hospital-System | citation navigation | PASS | اندازه گیری نشده |
| Hospital-System | documentation display | اندازه گیری نشده | Documentation UI display was exercised on CS-Bookstore. |
| CS-Bookstore | indexing flow | اندازه گیری نشده | Fresh indexing was executed through the production backend path. |
| CS-Bookstore | search UI | PASS | اندازه گیری نشده |
| CS-Bookstore | Persian query | PASS | اندازه گیری نشده |
| CS-Bookstore | English query | اندازه گیری نشده | English search was API-validated; frontend English query was exercised on Hospital-System and CodeCompass. |
| CS-Bookstore | result selection | اندازه گیری نشده | Result selection was exercised on Hospital-System and CodeCompass. |
| CS-Bookstore | Monaco navigation | اندازه گیری نشده | Monaco navigation was exercised on Hospital-System and CodeCompass. |
| CS-Bookstore | citation navigation | اندازه گیری نشده | Citation navigation was exercised on Hospital-System and CodeCompass. |
| CS-Bookstore | documentation display | PASS | اندازه گیری نشده |
| CodeCompass | indexing flow | PASS | A true no-op re-index completed: 96 unchanged files, 0 parsed, 0 embeddings, and 1220 vectors reused. |
| CodeCompass | search UI | PASS | اندازه گیری نشده |
| CodeCompass | Persian query | اندازه گیری نشده | Persian search was API-validated. |
| CodeCompass | English query | PASS | Stable-project QA request returned the correct target and citation. |
| CodeCompass | result selection | PASS | اندازه گیری نشده |
| CodeCompass | Monaco navigation | PASS | 9 expected highlighted source lines were observed. |
| CodeCompass | citation navigation | PASS | اندازه گیری نشده |
| CodeCompass | documentation display | اندازه گیری نشده | Documentation was API-validated; UI display was exercised on CS-Bookstore. |
| CodeCompass | immediate Ask after project switch | FAIL | The project combobox displayed CodeCompass, but an immediate Ask used the previously loaded CS-Bookstore project. Waiting for project loading to settle produced the correct result. |
| all | console/runtime errors | PASS | No warning or error entries were observed. |
| all | responsive horizontal overflow | PASS | No document-level horizontal overflow at desktop or 390x844 mobile viewport. |

## 8. Baseline Quality Summary

| Metric | Observed value |
|---|---|
| Average search relevance | 8.667 |
| Search target found | 16/18 |
| Search citation-valid executions | 18/18 |
| Average local-QA correctness | 5.333 |
| Average local-QA groundedness | 6.111 |
| Local-QA citation accuracy | 10.0 across 6 cases; 3 exact citation lists اندازه گیری نشده |
| Local-QA hallucinations | minor 3, major 1, critical 2 |
| OpenAI-compatible reviewable answers | 0/4 |
| Documentation average accuracy | 8.667 |
| Documentation citation accuracy | 10.0 |

## 9. Discovered Weaknesses

- Semantic retrieval missed the expected top-5 target for Hospital-System English and CodeCompass Persian queries in this sample.
- Hybrid retrieval ranked the Hospital-System Patient target second rather than first.
- Local Qwen omitted self.appointments in the Patient enumeration regression question.
- Local Qwen misinterpreted a returned empty-queue string as an error.
- Local Qwen introduced unsupported uniqueness/provenance claims for Book.save.
- Local Qwen produced a contradictory Persian CommentForm.clean_name answer.
- Local Qwen produced two critical unsupported-evidence hallucinations: a nonexistent checkout implementation and Redis coordination.
- Two local Qwen answers ended with finish_reason=length.
- All four retained OpenAI-compatible acceptance QA attempts failed with safe 502 qa_llm_failed envelopes, leaving semantic quality unmeasured for those attempts.
- Two of three Function Documentation cases contained unsupported prose or exception/dependency detail.
- An immediate Ask after switching projects can use the previously loaded project before the new project state settles.
- Exact full search-result lists, frozen QA prompt context, provider token usage, and some exact citation lists were not retained and are marked اندازه گیری نشده.

## 10. Data Gaps and Interpretation Boundary

The archive is intentionally conservative. Full search result payloads, frozen QA prompt/context pairs, token usage, and some exact insufficient-evidence citation records were not retained. These fields are marked **اندازه گیری نشده** in JSON and are not reconstructed. The reported averages exclude semantically unreviewable provider failures and exclude citation cases whose exact records were not retained. Results describe this acceptance sample only.
