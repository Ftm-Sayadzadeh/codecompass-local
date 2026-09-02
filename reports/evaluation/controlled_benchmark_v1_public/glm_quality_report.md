# GLM 5.3 Quality Evaluation

Provider/model: `openai_compatible` / `glm-5.3-flash`
Benchmark cases SHA: `5fbec49e1ad4c70af6a8aabf028f473afbdeb807d189070914b778ed3e9699af`
Frozen evidence SHA: `2359b07c36f19d47faf0171de0ab5e48ebc8b2f4620b6a8a8a6865cf75cc4c83`

## QA Results
| Case | Status | Correctness | Groundedness | Citation | Completeness |
|---|---|---:|---:|---:|---|
| CB-QA-H-EN | PASS | 10 | 10 | 10/10 | complete |
| CB-QA-H-FA | PASS | 10 | 10 | 10/10 | complete |
| CB-QA-B-EN | PASS | 10 | 10 | 10/10 | complete |
| CB-QA-B-FA | PASS | 10 | 10 | 10/10 | complete |
| CB-QA-C-EN | PASS | 10 | 10 | 10/10 | complete |
| CB-QA-C-FA | INCONCLUSIVE | اندازه‌گیری نشده | اندازه‌گیری نشده | 10/10 | incomplete |

## Documentation Results
| Case | Status | Overall | Purpose | Parameters | Return | Behavior | Dependencies | Citation |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| CB-DOC-H-EN | INCONCLUSIVE | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده |
| CB-DOC-H-FA | INCONCLUSIVE | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده |
| CB-DOC-B-EN | INCONCLUSIVE | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده |
| CB-DOC-B-FA | INCONCLUSIVE | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده |
| CB-DOC-C-EN | INCONCLUSIVE | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده |
| CB-DOC-C-FA | INCONCLUSIVE | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده | اندازه‌گیری نشده |

## Aggregate
{
  "qa": {
    "count": 6,
    "pass": 5,
    "inconclusive": 1,
    "average_correctness_reviewable": 10.0,
    "average_groundedness_reviewable": 10.0,
    "average_citation_accuracy": 10.0
  },
  "documentation": {
    "count": 6,
    "pass": 0,
    "inconclusive": 6,
    "average_overall_score": "اندازه‌گیری نشده",
    "average_citation_accuracy": "اندازه‌گیری نشده"
  },
  "latency_seconds": {
    "mean": 8.078433833333333,
    "median": 9.8176205,
    "min": 2.79541,
    "max": 12.461999
  },
  "provider_error_types": {
    "invalid_response_empty_content": 4
  },
  "finish_reasons": {
    "stop": 8,
    "length": 2,
    "unavailable": 2
  }
}

## Limitations
Provider failures and truncation are marked INCONCLUSIVE. Token usage was unavailable. No additional models were run in this report.

## Exact Captured Outputs
### CB-QA-H-EN
```text
In `Patient.__init__` (models/patient.py, lines 6–16), the following attributes are assigned on `self`:

- `self.first_name`
- `self.last_name`
- `self.national_id`
- `self.phone_num`
- `self.password`
- `self.gender`
- `self.city`
- `self.full_name` — set to the formatted string `f"{self.first_name} {self.last_name}"`
- `self.insurance_num`
- `self.appointments` — initialized as `Appointments()`

That is a total of 10 attributes assigned in the constructor.
```

### CB-QA-H-FA
```text
## رفتار متد `QueueArray.dequeue`

بر اساس کد ارائه‌شده (فایل `data_structures/queue.py`، خطوط ۲۲-۳۳):

### صف خالی
اگر `self.is_empty()` مقدار True برگرداند، متد رشته‌ی `"Queue is empty."` را برمی‌گرداند (به‌جای raise کردن خطا).

### صف غیرخالی
اگر صف خالی نباشد، مراحل زیر انجام می‌شود:
1. مقدار `self.front` **یک واحد افزایش** می‌یابد (`self.front += 1`)
2. سپس عنصر `self.queue[self.front - 1]` برگردانده می‌شود؛ یعنی عنصری که قبلاً در موقعیت `front` بوده است.

### نکته
در بدنه‌ی متد یک بلوک کد **کامنت‌شده** وجود دارد که پیاده‌سازی جایگزینی را نشان می‌دهد:
```python
element = self.queue[self.front]
self.front -= 1
return element
```
این نسخه اجرا نمی‌شود و رفتار فعال متد همان افزایش `front` و برگرداندن `self.queue[self.front - 1]` است.
```

### CB-QA-B-EN
```text
According to the provided code for `Book.save` (store/models.py, lines 67–70), the slug is populated as follows:

1. **Check if slug is empty**: The method first checks `if not self.slug:` — meaning the slug is only set if it hasn't already been provided.
2. **Generate the slug**: If the slug is empty, it assigns `self.slug = slugify(self.title)`, using the `slugify` function applied to the book's `title`.
3. **Proceed with saving**: Finally, it calls `super().save(*args, **kwargs)` to perform the actual save.

In short, `Book.save` auto-populates the slug from the title via `slugify`, but only when the slug is not already set; otherwise it leaves the existing slug untouched and saves as usual.
```

### CB-QA-B-FA
```text
بر اساس کد `CommentForm.clean_name` در `blog/forms.py` (خطوط ۴۵–۵۱):

**نام‌هایی که رد می‌شود:**
- نام‌هایی که طولشان **کمتر از ۲ کاراکتر** باشد (`len(name) < 2`)
- نام‌هایی که طولشان **بیشتر از ۲۵۰ کاراکتر** باشد (`len(name) > 250`)

در این دو حالت، متد `forms.ValidationError` با پیام `'نام معتبر نیست!'` صادر (raise) می‌کند.

**در حالت معتبر:**
اگر طول نام بین ۲ تا ۲۵۰ کاراکتر باشد، متد همان `name` را (بدون تغییر) برمی‌گرداند (`return name`).

نکته تکمیلی: کل این بررسی فقط زمانی انجام می‌شود که `name` مقدار truthy داشته باشد (`if name:`)؛ یعنی اگر نام خالی باشد، شرط اعتبارسنجی طول اجرا نمی‌شود و متد بدون return صریح، عملاً `None` برمی‌گرداند.
```

### CB-QA-C-EN
```text
`RAGContextBuilder.build` enforces the budget with a greedy, per-chunk accumulation loop (src/codecompass/rag/context.py, lines 12–28):

1. **Input validation**: It first rejects non-positive budgets — if `max_chars < 1`, it raises `ContextBuildError("max_chars must be positive")`.

2. **Running character counter**: It maintains `used_chars = 0` and iterates over the chunks in the order produced by `self._unique_sorted(retrieval_result.results)`.

3. **Per-chunk admission check**: For each chunk it computes `code_chars = len(chunk.code)`. A chunk is included only if it fits within the remaining budget:
   - If `used_chars + code_chars > max_chars`, the chunk is **skipped entirely** (not truncated), and `omitted_count` is incremented.
   - Otherwise, the chunk's block (`self._block(chunk)`) is appended to `blocks` and `used_chars += code_chars`.

4. **Result accounting**: It returns `RAGContext(blocks=tuple(blocks), total_chars=used_chars, omitted_count=omitted_count)`, so the caller can see both the characters actually used and how many chunks were dropped.

Two notable behaviors visible in the code:
- Oversized chunks are skipped with `continue` rather than `break`, so a later, smaller chunk can still be admitted if it fits in the remaining budget.
- The guarantee is that `total_chars` never exceeds `max_chars`, since a chunk is added only when `used_chars + code_chars <= max_chars`.
```

### CB-QA-C-FA
```text
## پاسخ بر اساس کد موجود

بر اساس بلوک S1 (`GroundedQAService.answer` در `src/codecompass/qa/service.py`، خطوط ۴۳–۸۴)، این متد پاسخ grounded را با این جریان تولید می‌کند:

### مراحل تولید پاسخ

1. **اعتبارسنجی و بازیابی:** ابتدا `self._validate(request)` اجرا می‌شود، سپس `self._retrieve(request)` نتایج بازیابی را می‌سازد.
2. **تمرکز بر نماد:** `self._focus_on_named_symbol(retrieval_result)` نتایج را روی نماد نام‌برده متمرکز می‌کند.
3. **ساخت context:** `self._context(retrieval_result, request.max_context_chars)` با توجه به سقف `max_context_chars` کانتکست را می‌سازد.
4. **تولید citationها:** `citations = self._citations(context)` — یعنی citationها **از روی context ساخته‌شده** (و طبق docstring متد، «metadata-derived») تولید می‌شوند، **قبل و مستقل از خروجی LLM**. همین نکته آن‌ها را قابل‌اعتماد می‌کند: citationها ادعای مدل نیستند، بلکه از متادیتای بلوک‌های بازیابی‌شده می‌آیند.

### رفتار grounded

- اگر `context.blocks` خالی باشد، متد بدون فراخوانی LLM یک `QAAnswer` برمی‌گرداند که در آن `answer=NO_EVIDENCE_ANSWER` و `citations=()` است — یعنی در نبود شواهد، پاسخ بی‌پایه تولید نمی‌شود.

### فراخوانی LLM و بازگشت نتیجه

- در غیر این صورت، `self.prompt_builder.build(request.question, context)` پرامپت و system prompt را می‌سازد و `self.llm_provider.generate(LLMRequest(...))` با `temperature` و `max_tokens` درخواست اجرا می‌شود.
- در صورت `LLMProviderError`، خطای `QAError("llm", error.message)` با `from error` منتشر می‌شود.
- `QAAnswer` نهایی شامل `answer=response.text`، `citations` (محاسبه‌شده از context)، و متادیتای
```

### CB-DOC-H-FA
```text
{
"summary": "کوچک‌ترین عنصر را از heap حداقلی حذف کرده و برمی‌گرداند.",
"detailed_description": "اگر heap خالی باشد، خطای IndexError با پیام «empty heap» صادر می‌شود. در غیر این صورت ریشه (کوچک‌ترین عنصر) ذخیره می‌شود، آخرین عنصر جایگزین ریشه می‌گردد، مقدار useful_data یکی کاهش می‌یابد و با فراخوانی heapify_down(0) ساختار heap بازسازی می‌شود. در پایان عنصر ذخیره‌شده بازگردانده می‌شود.",
"parameters": [{"name": "self", "description": null}],
"return_value": "کوچک‌ترین عنصر heap پیش از حذف را برمی‌گرداند.",
"raises": [{"name": "IndexError", "description": "اگر heap خالی باشد صادر می‌شود."}],
"side_effects": ["عنصر آخر را جایگزین ریشه در self.heap می‌کند", "مقدار self.heap.useful_data را یکی کاهش می‌دهد", "با فراخوانی heapify_down(0) ترتیب heap را بازسازی می‌کند"],
"dependencies": ["heapify_down"],
"notes":
```

### CB-DOC-B-FA
```text
{
"summary": "این تابع یک view ثبت‌نام کاربر است که فرم UserRegisterForm را پردازش می‌کند و در صورت اعتبار فرم، کاربر را با رمز عبور هش‌شده ذخیره می‌کند.",
"detailed_description": "در درخواست‌های POST، داده‌های ارسالی به UserRegisterForm داده می‌شود و در صورت اعتبار فرم، شیء کاربر با commit=False ساخته، رمز عبور آن با set_password تنظیم و سپس ذخیره می‌شود و الگوی users/registration/register_done
```

