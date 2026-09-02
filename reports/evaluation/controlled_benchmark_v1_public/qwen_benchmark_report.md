# Controlled Bilingual Model Benchmark v1 - Qwen Baseline

## 1. Experiment
This report records the local-Qwen baseline. Retrieval evidence and prompts were frozen before generation. GLM/AvalAI was not called. The replay used the exact frozen LLM inputs after the initial local-provider execution failure.

**Benchmark ID:** `codecompass_controlled_bilingual_model_comparison_v1`  
**Benchmark cases SHA-256:** `5fbec49e1ad4c70af6a8aabf028f473afbdeb807d189070914b778ed3e9699af`  
**Frozen retrieval evidence SHA-256:** `2359b07c36f19d47faf0171de0ab5e48ebc8b2f4620b6a8a8a6865cf75cc4c83`  
**Provider/model:** `ollama` / `qwen2.5-coder-3b-codecompass:latest`  
**Generation:** temperature `0`, max_tokens `1200`, provider retries `0`, manual reruns `0`

## 2. Dataset and Indexes
| Repository | Files | Symbols | Chunks | Vectors | IDs | Generation | Complete |
|---|---:|---:|---:|---:|---|---|---|
| hospital_system | 33 | 409 | 409 | 409 | True | True | True |
| cs_bookstore | 56 | 144 | 144 | 144 | True | True | True |
| codecompass | 96 | 1220 | 1220 | 1220 | True | True | True |

All repositories were indexed once in isolated storage. No re-index occurred during replay.

## 3. Frozen Retrieval Evidence
Search executions: **54**. QA evidence captures: **6**. Documentation evidence captures: **6**.

## 4. Qwen Generation Replay
The original 12 provider failures remain embedded in `qa_results` and `documentation_results`. The replay appended successful outputs in `replay_results` using the same frozen prompts, contexts, and settings. No retries were used.

| Case | Type | Language | Status | Latency (s) | Output length | Finish reason | Token usage |
|---|---|---|---|---:|---:|---|---|
| CB-QA-H-EN | QA | en | REVIEWABLE | 22.691 | 274 | stop | اندازه‌گیری نشده |
| CB-QA-H-FA | QA | fa | REVIEWABLE | 11.876 | 156 | stop | اندازه‌گیری نشده |
| CB-QA-B-EN | QA | en | REVIEWABLE | 9.167 | 322 | stop | اندازه‌گیری نشده |
| CB-QA-B-FA | QA | fa | REVIEWABLE | 27.032 | 500 | stop | اندازه‌گیری نشده |
| CB-QA-C-EN | QA | en | REVIEWABLE | 23.423 | 753 | stop | اندازه‌گیری نشده |
| CB-QA-C-FA | QA | fa | REVIEWABLE | 65.131 | 1090 | stop | اندازه‌گیری نشده |
| CB-DOC-H-EN | Documentation | en | REVIEWABLE | 45.209 | 754 | stop | اندازه‌گیری نشده |
| CB-DOC-H-FA | Documentation | fa | REVIEWABLE | 67.449 | 758 | stop | اندازه‌گیری نشده |
| CB-DOC-B-EN | Documentation | en | REVIEWABLE | 46.410 | 956 | stop | اندازه‌گیری نشده |
| CB-DOC-B-FA | Documentation | fa | REVIEWABLE | 48.971 | 555 | stop | اندازه‌گیری نشده |
| CB-DOC-C-EN | Documentation | en | REVIEWABLE | 93.381 | 1694 | stop | اندازه‌گیری نشده |
| CB-DOC-C-FA | Documentation | fa | REVIEWABLE | 94.510 | 1023 | اندازه‌گیری نشده | اندازه‌گیری نشده |

### Replay Summary
- Successful replay outputs: **12/12**
- Mean latency: **46.271s**
- Median latency: **45.810s**
- Range: **9.167s - 94.510s**
- Token usage: اندازه‌گیری نشده؛ provider response object does not expose it.
- Semantic scores: اندازه‌گیری نشده؛ this replay did not perform human scoring.

## 5. Exact Captured Outputs
### CB-QA-H-EN
```text
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
```

### CB-QA-H-FA
```text
در صف خالی، متد `dequeue` باعث خطای "Queue is empty." است. در صف غیرخالی، ابتدا فرانت صف به یک واحد بروزرسانی شده و سپس عنصر در فرانت جدید برگردانده می‌شود.
```

### CB-QA-B-EN
```text
Book.save populates the slug before saving by checking if the slug attribute is empty. If it is, it uses the `slugify` function from the `slugify` module to generate a slug based on the title attribute and assigns it to the slug attribute. This ensures that every book has a unique slug before being saved to the database.
```

### CB-QA-B-FA
```text
متد `CommentForm.clean_name` رد می‌کند:

1. "نام معتبر نیست!" را در حالت معتبر برمی‌گرداند.

2. این متد یک فیلد نام (`name`) را بررسی می‌کند و از آن استفاده می‌کند.

3. اگر `name` خالی نباشد، فیلد را بررسی می‌کند:

   - اگر طول `name` بین 2 تا 250 کاراکتر باشد، فیلد را به عنوان نام معتبر درخواست می‌دهد.
   
   - اگر طول `name` کمتر از 2 یا بیشتر از 250 کاراکتر باشد، یک خطا (`ValidationError`) را به عنوان "نام معتبر نیست!" بررسی می‌دهد.

4. در حالت معتبر، `name` را به عنوان نام معتبر برمی‌گرداند.
```

### CB-QA-C-EN
```text
RAGContextBuilder.build enforces its context-size budget by checking if `max_chars` is positive at the beginning of the method. If `max_chars` is less than 1, it raises a ContextBuildError with an appropriate message.

The method then iterates over each chunk in the retrieval result's results, calculating the number of code characters in each chunk. It adds chunks to the context blocks list as long as adding them would not exceed the `max_chars` budget. If adding a chunk would exceed the budget, it increments the omitted_count and skips that chunk.

After processing all chunks, it returns an RAGContext object containing the list of context blocks, the total number of characters used, and the count of chunks omitted due to exceeding the budget.
```

### CB-QA-C-FA
```text
GroundedQAService.answer می‌کند توسط چهار مرحله ای که در زیر آورده شده است:

1. **اعتبارسنجی درخواست**: پایانده _validate_ بررسی معتبر بودن درخواست را انجام می‌دهد.

2. **دریافت نتیجه های جستجوی**: پایانده _retrieve_ به عنوان داده‌ها استفاده می‌کند و نتیجه‌های جستجوی را دریافت می‌کند.

3. **پردازش نتیجه های جستجوی**: پایانده _focus_on_named_symbol_ به عنوان داده‌ها استفاده می‌کند و نتیجه‌های جستجوی را بررسی می‌کند تا فقط اطلاعاتی که نام‌شناخته شده است را در نظر بگیرد.

4. **ساخت متن پشتیبان**: پایانده _context_ به عنوان داده‌ها استفاده می‌کند و متن پشتیبان بر اساس نتیجه‌های جستجوی و درخواست را ساخت.

5. **ساخت تیتراتور**: پایانده _citations_ به عنوان داده‌ها استفاده می‌کند و تیتراتور‌های قابل اعتماد بر اساس متن پشتیبان را ساخت.

6. **تولید پاسخ**: پایانده _generate_ به عنوان داده‌ها استفاده می‌کند و پاسخ را تولید می‌کند.

7. **ساخت پاسخ**: پایانده _QAAnswer_ به عنوان داده‌ها استفاده می‌کند و پاسخ را با اطلاعاتی که شامل نام‌شناخته شده‌ها، تیتراتور‌های قابل اعتماد، و ساختار داده‌های LLM دریافت می‌کند.

پس از این مرحله‌ها، پاسخ به عنوان یک نمونه از _QAAnswer_ برگردانده می‌شود.
```

### CB-DOC-H-EN
```text
{
  "summary": "Logs in a doctor using their phone number and password.",
  "detailed_description": "This method checks if the provided phone number matches the registered phone number for the given password. If they match, it returns True; otherwise, it returns False.",
  "parameters": [
    {"name": "self", "description": null},
    {"name": "phone_num", "description": "The phone number of the doctor to log in."},
    {"name": "password", "description": "The password associated with the doctor's account."}
  ],
  "return_value": "bool",
  "raises": [],
  "side_effects": ["Modifies the state of the `self` object by checking and updating the logged-in status of the doctor."],
  "dependencies": ["self.signed_in", "self.doctors"],
  "notes": []
}
```

### CB-DOC-H-FA
```text
{
  "summary": "دسته‌بندی کننده خروجی از هایپ در پایگاه داده است",
  "detailed_description": "تابع `extract_min` برای حذف و بازگرداندن عنصر کوچکترین از هایپ استفاده می‌شود. ابتدا بررسی می‌شود که آیا هایپ خالی نیست یا نه. اگر هایپ خالی باشد، خطای `IndexError` را به دست می‌آورد. در غیر این صورت، عنصر کوچکترین (به طور فردی) از هایپ بررسی می‌شود و سپس با عنصر آخر تبادل می‌شود. سپس حجم داده استفاده شده در هایپ به 1 کاهش می‌رسد و تابع `heapify_down` اجرا می‌شود تا ترتیب های پایین را بازگرداند. عنصر کوچکترین برگردانده شده است.",
  "parameters": [{"name": "self", "description": null}],
  "return_value": "عنصر کوچکترین از هایپ",
  "raises": ["IndexError"],
  "side_effects": ["حذف عنصر کوچکترین از هایپ و بازگرداندن آن"],
  "dependencies": [],
  "notes": []
}
```

### CB-DOC-B-EN
```text
{
  "summary": "Reviews a book by ID or slug.",
  "detailed_description": "This function reviews a book based on its unique identifier (pk) or slug. It retrieves the book from the database, checks if it exists, and then handles POST requests to submit a review form. If the request is valid, it saves the review with the associated book and user, then redirects to the book's absolute URL.",
  "parameters": [
    {"name": "request", "description": "The HTTP request object containing information about the client's request."},
    {"name": "pk", "description": "The unique identifier of the book to be reviewed."},
    {"name": "slug", "description": "The slug of the book to be reviewed."}
  ],
  "return_value": null,
  "raises": [],
  "side_effects": ["Saves a review to the database if the request is valid.", "Redirects to the book's absolute URL after processing the request."],
  "dependencies": ["get_object_or_404", "ReviewForm"],
  "notes": []
}
```

### CB-DOC-B-FA
```text
{
  "summary": "فunkce درخواستی برای ثبت نام کاربران",
  "detailed_description": "این funkce مربوط به ثبت نام کاربران است و از طریق فرم‌های HTML درخواستی می‌گیرد. اگر نوع پروتکل درخواست 'POST' باشد، فرم بررسی شده و اگر معتبر باشد، کاربر جدید ساخته می‌شود و رمز عبور آن تنظیم می‌شود. در غیر این صورت، فرم پیشفرض نمایش داده می‌شود.",
  "parameters": [{"name": "request", "description": null}],
  "return_value": null,
  "raises": [],
  "side_effects": ["کاربر جدید ساخته شده و رمز عبور آن تنظیم شده"],
  "dependencies": ["UserRegisterForm"],
  "notes": []
}
```

### CB-DOC-C-EN
```text
{
  "summary": "Replaces a project's structural metadata in the SQLite database.",
  "detailed_description": "This method atomically replaces one project's structural metadata, including its name, root path, and other associated data. It handles file replacements, symbol updates, chunk management, and ensures that the operation is rolled back if an error occurs.",
  "parameters": [
    {"name": "self", "description": null},
    {"name": "name", "description": "The new name for the project."},
    {"name": "root_path", "description": "The new root path for the project."},
    {"name": "files", "description": "An iterable of SourceFile objects representing files to be replaced."},
    {"name": "parse_results", "description": "An iterable of ParseResult objects containing symbols and other parse information."},
    {"name": "chunks", "description": "An iterable of Chunk objects representing chunks of data."},
    {"name": "before_commit", "description": "A callable that is executed before the commit, allowing for custom activation logic."},
    {"name": "on_rollback", "description": "A callable that is executed if a rollback is needed after an error occurs."},
    {"name": "index_schema_version", "description": "The new schema version for the project's index."},
    {"name": "vector_generation", "description": "The new vector generation for the project's data."}
  ],
  "return_value": "ProjectRecord",
  "raises": ["StorageError"],
  "side_effects": ["Modifies the SQLite database with new or updated project metadata and files."],
  "dependencies": ["sqlite3", "_connect", "_now", "_replace_source_files", "_replace_symbols", "_replace_chunks", "_project"],
  "notes": []
}
```

### CB-DOC-C-FA
```text
{
  "summary": "این متد جواب‌گذاری از سوالات است که با استفاده از داده‌های مستقیم در پایان نتیجه‌گیری می‌شود.",
  "detailed_description": "این متد به صورت خلاصه جواب را برای سوالات با استفاده از داده‌های مستقیم در پایان نتیجه‌گیری می‌دهد. ابتدا، تابع _validate() بررسی می‌کند که درخواست مناسب است یا خیر. سپس، تابع _retrieve() به داده‌ها برمی‌گرداند که با استفاده از روش پیدا کردن مورد نظر انجام شده است. سپس، تابع _focus_on_named_symbol() برای فکر کردن درباره یک متغیر مشخص می‌کند. سپس، تابع _context() به داده‌ها برمی‌گرداند که با استفاده از حجم معین مناسب شده است. سپس، تابع _citations() برای جستجوی مراجع مربوطه به داده‌ها برمی‌گرداند. در صورتی که هیچ بلاک نداشته باشد، یک جواب خالصی با استفاده از NO_EVIDENCE_ANSWER برای سوال و پاسخ می‌دهد. در غیر اینصورت، تابع prompt_builder.build() به داده‌ها برمی‌گرداند که شامل پرسش و حجم مناسب شده است. سپس، تابع llm_provider.generate() برای گرفتن جواب از مدل خود استفاده می‌کند. در صورتی که خطای llmProviderError را دریافت کند، یک QAError با نوع "                               
```

## 6. Interpretation and Limitations
The frozen retrieval/index evidence remains valid and unchanged. The initial local-provider failures are preserved as historical attempts; the replay produced reviewable Qwen outputs. No GLM/AvalAI request was made, so no model comparison is present in this artifact. Human quality scores, hallucination labels, and independent semantic judgments remain اندازه‌گیری نشده and must not be inferred from generated text alone.

## 7. Artifact Integrity
- benchmark_cases.json is frozen; its SHA-256 is recorded above.
- frozen_retrieval_evidence.json is frozen; its SHA-256 is recorded above.
- qwen_results.json contains both initial failures and replay outputs.
- No source code, index, retrieval evidence, prompt, or configuration was changed.
