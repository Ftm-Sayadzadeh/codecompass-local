# Hospital-System Bilingual Grounded QA Evaluation

## 1. Purpose

This report evaluates CodeCompass grounded question answering on Hospital-System, an external sample Python repository. The scope is a small frozen bilingual matrix intended to examine production-path behavior, source grounding, and deterministic citation integrity. It is not a large benchmark and does not support statistical-significance claims.

## 2. Experimental Setup

| Setting | Frozen value |
|---|---|
| Project | `2 / Hospital-System` |
| Repository identity | 33 files, 409 symbols, 409 chunks, 409 vectors |
| LLM provider | `openai_compatible` |
| Model | `glm-5.3-flash` |
| Embedding | Ollama / `nomic-embed-text-local:latest` / 768 dimensions |
| Retrieval | Hybrid |
| Temperature | `0` |
| Maximum output tokens | `1024` |
| Executions / retries | `8 / 0` |
| Matrix SHA-256 | `3fbeac128da1251ebc3cd262abcb3208044f058a53e3b94977c5e4fddebbe44d` |
| Rubric SHA-256 | `17cc25b4435b9a44189c2ff87b7e04b800fb1a74a8fbd5de523ef7e53151638e` |

Before the matrix, a production-path smoke for `Patient.__init__` passed with 10/10 attributes and a valid normal CodeCompass citation path. No re-indexing occurred for the matrix.

## 3. Evaluation Protocol

- Questions and source-derived ground truth were frozen before generation.
- The matrix was not changed after model outputs were observed.
- No prompt or retrieval tuning occurred during execution.
- Each question used one Hybrid Ask request through the production CodeCompass path.
- Citation records were checked against trusted SQLite metadata.
- `HS-QA-01` is a known regression anchor and is not presented as novel.
- `HS-QA-02` through `HS-QA-08` are novel frozen questions.

## 4. Scoring Rubric

**PASS:** all expected facts present; no invented or forbidden facts; correct target symbol; valid citation/source metadata; answer language matches the question; no truncation or provider error.

**PARTIAL:** stated facts are correct and grounded, but one or more expected facts are missing and no material fact is invented.

**FAIL:** a material fact is invented or forbidden, behavior is contradicted, the wrong symbol is answered, citation mapping is invalid, generation fails or truncates, or the answer is materially wrong.

## 5. Aggregate Results

| Slice | Result |
|---|---:|
| Overall | 7 PASS / 0 PARTIAL / 1 FAIL |
| English | 3/4 PASS |
| Persian | 4/4 PASS |
| Known regression anchor | 1/1 PASS |
| Novel frozen questions | 6/7 PASS |
| Language adherence | 8/8 |
| Target-symbol fidelity | 8/8 |
| Citation validity | 13/13 records |

| Latency statistic | Seconds |
|---|---:|
| Mean | 8.671 |
| Median | 8.562 |
| Minimum | 5.494 |
| Maximum | 12.609 |

## 6. Per-Question Results

| ID | Language | Category | Target symbol | Question | Result | Latency | Expected | Missing | Invented/unsupported | Citation |
|---|---|---|---|---|---:|---:|---:|---|---|---|
| HS-QA-01 | EN | attribute_field_enumeration | `Patient.__init__` | What attributes are assigned in Patient.__init__? | **PASS** | 8.134s | 10 | None | None | Valid |
| HS-QA-02 | FA | attribute_field_enumeration | `Node.__init__` | سازنده Node در models/appointment.py چه ویژگی‌هایی را مقداردهی می‌کند؟ | **PASS** | 5.494s | 3 | None | None | Valid |
| HS-QA-03 | EN | method_behavior | `Schedule.is_available` | How does Schedule.is_available decide whether a time slot is available? | **PASS** | 8.990s | 5 | None | None | Valid |
| HS-QA-04 | FA | method_behavior | `QueueArray.dequeue` | متد QueueArray.dequeue در صف خالی و غیرخالی چه رفتاری دارد؟ | **PASS** | 7.650s | 3 | None | None | Valid |
| HS-QA-05 | EN | class_object_relationship | `Doctor.__init__` | Which helper objects does Doctor.__init__ create and store? | **FAIL** | 9.910s | 2 | None | Described unannotated constructor parameters as "string parameters" | Valid |
| HS-QA-06 | FA | class_object_relationship | `Manage.__init__` | سازنده Manage چه مجموعه‌هایی را نگه می‌دارد و چه شیء مدیریت روزی می‌سازد؟ | **PASS** | 7.525s | 5 | None | None | Valid |
| HS-QA-07 | EN | symbol_specific_explanation | `DayManager.next_day` | What exactly does DayManager.next_day do? | **PASS** | 12.609s | 2 | None | None | Valid |
| HS-QA-08 | FA | symbol_specific_explanation | `File.append` | متد File.append متن ورودی را دقیقاً چگونه به فایل اضافه می‌کند؟ | **PASS** | 9.059s | 3 | None | None | Valid |

## 7. Detailed Question and Answer Records

### HS-QA-01

- **Question:** What attributes are assigned in Patient.__init__?
- **Language:** EN
- **Category:** `attribute_field_enumeration`
- **Target source:** `models/patient.py:6-16` / `Patient.__init__`
- **Expected facts:** self.first_name; self.last_name; self.national_id; self.phone_num; self.password; self.gender; self.city; self.full_name; self.insurance_num; self.appointments

**Exact captured answer:**

> In `Patient.__init__` (models/patient.py, lines 6–16), the following attributes are assigned on `self`:
>
> - `first_name`
> - `last_name`
> - `national_id`
> - `phone_num`
> - `password`
> - `gender`
> - `city`
> - `full_name` — set to an f-string combining `self.first_name` and `self.last_name`
> - `insurance_num`
> - `appointments` — initialized to a new `Appointments()` instance

- **Result:** **PASS**
- **Missing facts:** None
- **Invented/unsupported facts:** None
- **Citation metadata:** file_id=36, symbol_id=452, chunk_id=42a0c185f2075dcce043fd60f2d6469f3048b722ebc4329967e065691664c5e2, Patient.__init__, models/patient.py:6-16
- **Latency:** 8.134s
- **Evaluation note:** Known regression anchor. All 10 expected attributes were present, including self.appointments.

### HS-QA-02

- **Question:** سازنده Node در models/appointment.py چه ویژگی‌هایی را مقداردهی می‌کند؟
- **Language:** FA
- **Category:** `attribute_field_enumeration`
- **Target source:** `models/appointment.py:2-5` / `Node.__init__`
- **Expected facts:** self.doctor = doctor; self.day = day; self.hour = hour

**Exact captured answer:**

> سازنده `Node.__init__` در فایل `models/appointment.py` سه ویژگی را مقداردهی می‌کند:
>
> - **`self.doctor`** — از پارامتر `doctor`
> - **`self.day`** — از پارامتر `day`
> - **`self.hour`** — از پارامتر `hour`
>
> کد سازنده (خطوط ۲ تا ۵):
>
> ```python
> def __init__(self, doctor, day, hour):
>     self.doctor = doctor
>     self.day = day
>     self.hour = hour
> ```

- **Result:** **PASS**
- **Missing facts:** None
- **Invented/unsupported facts:** None
- **Citation metadata:** file_id=34, symbol_id=425, chunk_id=d03f82a50f1788c678260c9cc67483f95577f65bd820f427cdef7d8ec26a0468, Node, models/appointment.py:1-12; file_id=34, symbol_id=426, chunk_id=a94b4ac6724cd2ecf2a0e122d1a9016e512354664f1ebd566a44075575bd2609, Node.__init__, models/appointment.py:2-5; file_id=34, symbol_id=428, chunk_id=abaf88ff0dcd4901c9b0a79be40b6b175975a55d7090213cdaba25d9b0308f9c, Node.__repr__, models/appointment.py:11-12; file_id=34, symbol_id=427, chunk_id=0223f0377d08c35f2cd173d3c4182cebe9d2079553576e40133ff417dcb61add, Node.__lt__, models/appointment.py:7-9
- **Latency:** 5.494s
- **Evaluation note:** All expected assignments were present. Additional returned citations were valid but broader than necessary.

### HS-QA-03

- **Question:** How does Schedule.is_available decide whether a time slot is available?
- **Language:** EN
- **Category:** `method_behavior`
- **Target source:** `models/doctor.py:57-63` / `Schedule.is_available`
- **Expected facts:** Converts time to int and subtracts 1 for the list index; Checks self.schedule[day] before reading the slot; Returns True only when the selected slot equals "Available"; Returns False when the day entry is truthy but the selected slot is not "Available"; Returns None implicitly when self.schedule[day] is falsy

**Exact captured answer:**

> Based on the code in `models/doctor.py` (lines 57–63), `Schedule.is_available` works as follows:
>
> 1. **Converts the time slot to a 0-based index**: It takes the `time` argument, converts it to an integer, and subtracts 1 (`time = int(time) - 1`). This means callers pass a 1-based slot number, which is mapped to a list index.
>
> 2. **Checks that the day exists in the schedule**: It first tests `if self.schedule[day]:` — i.e., the entry for that day must be truthy (non-empty).
>
> 3. **Compares the slot's value to the string "Available"**:
>    - If `self.schedule[day][time] == "Available"`, it returns `True`.
>    - Otherwise, it returns `False`.
>
> One additional behavior visible in the code: if `self.schedule[day]` is falsy (e.g., empty), the outer `if` is not entered and the method has no explicit return in that path, so it implicitly returns `None` — which is falsy and would be treated as "not available" in a boolean context, though it is not an explicit `False`.

- **Result:** **PASS**
- **Missing facts:** None
- **Invented/unsupported facts:** None
- **Citation metadata:** file_id=35, symbol_id=438, chunk_id=8164f851e74f01a4f69a42e48ffc67282ab90a9aa4349da9bf235c10ac794e21, Schedule.is_available, models/doctor.py:57-63
- **Latency:** 8.990s
- **Evaluation note:** All branch-sensitive expected facts were present, including the implicit None path.

### HS-QA-04

- **Question:** متد QueueArray.dequeue در صف خالی و غیرخالی چه رفتاری دارد؟
- **Language:** FA
- **Category:** `method_behavior`
- **Target source:** `data_structures/queue.py:22-33` / `QueueArray.dequeue`
- **Expected facts:** If the queue is empty, returns "Queue is empty."; Otherwise increments self.front by 1; Returns self.queue[self.front - 1] after incrementing front

**Exact captured answer:**

> بر اساس کد موجود در `data_structures/queue.py` (خطوط ۲۲-۳۳)، متد `QueueArray.dequeue` دو رفتار دارد:
>
> **صف خالی:**
> - ابتدا با `self.is_empty()` بررسی می‌کند که صف خالی باشد.
> - اگر صف خالی باشد، رشته‌ی `"Queue is empty."` را برمی‌گرداند (یعنی به‌جای پرتاب استثنا، یک پیام متنی برمی‌گرداند).
>
> **صف غیرخالی:**
> - مقدار `self.front` را یک واحد افزایش می‌دهد: `self.front += 1`
> - سپس عنصر موجود در اندیس `self.front - 1` (یعنی همان موقعیت قبلیِ `front`) را برمی‌گرداند: `return self.queue[self.front - 1]`
>
> به این ترتیب، عنصر ابتدای صف خوانده شده و نشانگر `front` به سمت جلو حرکت می‌کند.
>
> **نکته:** در بدنه‌ی متد یک بلوک کد کامنت‌شده نیز وجود دارد که پیاده‌سازی جایگزینی را نشان می‌دهد (خواندن عنصر از `self.queue[self.front]` و سپس کاهش `self.front`)، اما این کد اجرا نمی‌شود و نسخه‌ی فعال همان افزایش `front` است.

- **Result:** **PASS**
- **Missing facts:** None
- **Invented/unsupported facts:** None
- **Citation metadata:** file_id=24, symbol_id=316, chunk_id=1df22345e37e9c6c7038efb4a6acb81e56298fbe587c4a4be47acb872f21650b, QueueArray.dequeue, data_structures/queue.py:22-33
- **Latency:** 7.650s
- **Evaluation note:** Both active execution paths were explained correctly; the commented alternative was explicitly identified as inactive.

### HS-QA-05

- **Question:** Which helper objects does Doctor.__init__ create and store?
- **Language:** EN
- **Category:** `class_object_relationship`
- **Target source:** `models/doctor.py:9-23` / `Doctor.__init__`
- **Expected facts:** self.schedule is initialized with Schedule(); self.appointments is initialized with Appointments()

**Exact captured answer:**

> Based on the provided code, `Doctor.__init__` creates and stores two helper objects:
>
> 1. **`Schedule()`** — a new `Schedule` instance assigned to `self.schedule`
> 2. **`Appointments()`** — a new `Appointments` instance assigned to `self.appointments`
>
> All other attributes set in `__init__` are plain values, not helper objects: the string parameters (`first_name`, `last_name`, `national_id`, `medical_num`, `phone_num`, `address`, `city`, `speciality`, `password`), the integer `self.visits = 0`, and the f-string `self.full_name = f"{self.first_name} {self.last_name}"`.

- **Result:** **FAIL**
- **Missing facts:** None
- **Invented/unsupported facts:** Described unannotated constructor parameters as "string parameters"
- **Citation metadata:** file_id=35, symbol_id=430, chunk_id=9c72cb460e7b3d43f4ccfa12ea1c0cbcea8ff63a35683885deed828231679f3c, Doctor.__init__, models/doctor.py:9-23
- **Latency:** 9.910s
- **Evaluation note:** The requested helper-object facts were complete, but the unsupported parameter-type claim is a material generation/prose grounding failure under the frozen rubric.

### HS-QA-06

- **Question:** سازنده Manage چه مجموعه‌هایی را نگه می‌دارد و چه شیء مدیریت روزی می‌سازد؟
- **Language:** FA
- **Category:** `class_object_relationship`
- **Target source:** `logic/management.py:7-12` / `Manage.__init__`
- **Expected facts:** Stores cities in self.cities; Stores specialities in self.specialities; Stores patients in self.patients; Stores doctors in self.doctors; Creates DayManager() and stores it in self.day_manager

**Exact captured answer:**

> بر اساس کد سازندهٔ `Manage.__init__` (فایل `logic/management.py`، خطوط ۷ تا ۱۲):
>
> **مجموعه‌هایی که نگه می‌دارد** (که همگی به‌عنوان پارامتر ورودی دریافت می‌شوند):
> - `self.cities` — شهرها
> - `self.specialities` — تخصص‌ها
> - `self.patients` — بیماران
> - `self.doctors` — پزشکان
>
> **شیء مدیریت روزی که می‌سازد:**
> - `self.day_manager = DayManager()` — یک نمونه از کلاس `DayManager` می‌سازد (این پارامتر ورودی نیست و مستقیماً درون سازنده نمونه‌سازی می‌شود).

- **Result:** **PASS**
- **Missing facts:** None
- **Invented/unsupported facts:** None
- **Citation metadata:** file_id=30, symbol_id=381, chunk_id=69c8ba061c1bec5d408854c7261ff2649807ec56b40b998e8a133d9bbf27d2d7, Manage, logic/management.py:6-203; file_id=30, symbol_id=382, chunk_id=e5423fb10dff0fafa428a81cff245fca3072c81c2f53b611630c5e234355f617, Manage.__init__, logic/management.py:7-12; file_id=30, symbol_id=383, chunk_id=4309dea23016534ac81b5feb84e06e0dfdbaa2ac88509b7092a247156e2b3b62, Manage.admin_display_doctors, logic/management.py:16-18
- **Latency:** 7.525s
- **Evaluation note:** All stored dependencies and the constructed DayManager were identified. Additional returned citations were valid but broader than necessary.

### HS-QA-07

- **Question:** What exactly does DayManager.next_day do?
- **Language:** EN
- **Category:** `symbol_specific_explanation`
- **Target source:** `logic/day_manager.py:27-29` / `DayManager.next_day`
- **Expected facts:** Increments self.curr_day by 1; Calls self.save_day() after incrementing

**Exact captured answer:**

> Based on the provided code, `DayManager.next_day` (defined in `logic/day_manager.py`, lines 27–29) does exactly two things:
>
> 1. **Increments the current day**: `self.curr_day += 1` — it adds 1 to the instance attribute `curr_day`.
> 2. **Saves the day**: it then calls `self.save_day()`.
>
> ```python
> def next_day(self):
>     self.curr_day += 1
>     self.save_day()
> ```
>
> Note: The retrieved context does not include the implementation of `save_day()`, so what that save operation actually does (e.g., where or how the day is persisted) cannot be determined from the provided evidence.

- **Result:** **PASS**
- **Missing facts:** None
- **Invented/unsupported facts:** None
- **Citation metadata:** file_id=29, symbol_id=379, chunk_id=c4412c63a3df489c8bac4713e4b7eb9e04dad1b47be79e617a4a923b71bdd817, DayManager.next_day, logic/day_manager.py:27-29
- **Latency:** 12.609s
- **Evaluation note:** The two operations and their order were correct; the answer appropriately bounded claims about save_day().

### HS-QA-08

- **Question:** متد File.append متن ورودی را دقیقاً چگونه به فایل اضافه می‌کند؟
- **Language:** FA
- **Category:** `symbol_specific_explanation`
- **Target source:** `tools/file_handling.py:19-22` / `File.append`
- **Expected facts:** Opens self.path in append mode "a"; Writes the supplied line; Writes a newline "\n" immediately afterward

**Exact captured answer:**

> متد `File.append` (در فایل `tools/file_handling.py`، خطوط ۱۹ تا ۲۲) متن ورودی را به این صورت اضافه می‌کند:
>
> 1. فایل را با حالت `"a"` (append) باز می‌کند، یعنی محتوا به انتهای فایل اضافه می‌شود و محتوای قبلی حذف نمی‌شود:
>    ```python
>    with open(self.path, "a") as file:
>    ```
> 2. متن ورودی (`line`) را با `file.write(line)` می‌نویسد.
> 3. بلافاصله یک کاراکتر خط جدید (`"
> "`) را با `file.write("
> ")` اضافه می‌کند.
>
> بنابراین متن ورودی دقیقاً همان‌طور که هست (بدون هیچ تغییری) در انتهای فایل نوشته می‌شود و پس از آن یک خط جدید قرار می‌گیرد، به‌طوری که هر فراخوانی بعدی در خط جداگانه‌ای نوشته شود.

- **Result:** **PASS**
- **Missing facts:** None
- **Invented/unsupported facts:** None
- **Citation metadata:** file_id=44, symbol_id=518, chunk_id=20fde1b51d208c3d95db9b5108c353ed49af83cd5b6348410fd5b1ca8f01932d, File.append, tools/file_handling.py:19-22
- **Latency:** 9.059s
- **Evaluation note:** The append mode, input write, and trailing newline were all described correctly.

## 8. Failure Analysis

`HS-QA-05` returned both requested helper-object facts correctly: `self.schedule = Schedule()` and `self.appointments = Appointments()`. It also called the unannotated constructor inputs “string parameters.” The source does not establish those parameter types. Under the frozen strict rubric, this material unsupported type claim makes the result FAIL even though the core requested facts were complete. This is a generation/prose-grounding limitation; retrieval succeeded and the citation mapped correctly to `Doctor.__init__`.

## 9. Citation Analysis

All 13 returned citation records matched SQLite project, file, symbol, chunk, path, and line metadata. `HS-QA-02` and `HS-QA-06` returned additional citations beyond the narrow target. Those records were valid, but they reduce citation precision. Citation validity and citation noise are therefore reported separately.

## 10. Language Analysis

Within this small frozen sample, all four Persian answers passed and three of four English answers passed. The sample is too small to infer that either language performs better in general. All eight answers adhered to the requested language.

## 11. Conclusion

**Final verdict: READY_WITH_LIMITATIONS.**

The system produced a strong result on this small frozen matrix, with 7/8 strict passes and a deterministic citation path that remained valid for every returned record. One unsupported prose/type claim demonstrates that correct retrieval and citations do not guarantee fully grounded generation. These results do not establish hallucination-free behavior and are too limited for broad statistical or cross-repository claims.

## 12. Reproducibility Record

- Matrix ID: `hospital_system_bilingual_qa_matrix_v1`
- Matrix SHA-256: `3fbeac128da1251ebc3cd262abcb3208044f058a53e3b94977c5e4fddebbe44d`
- Rubric SHA-256: `17cc25b4435b9a44189c2ff87b7e04b800fb1a74a8fbd5de523ef7e53151638e`
- Project: `2 / Hospital-System`
- Index identity: 33 source files; 409 symbols; 409 chunks; 409 vectors; exact SQLite/Chroma ID sets
- Embedding identity: Ollama / `nomic-embed-text-local:latest` / 768 dimensions
- QA identity: Hybrid / OpenAI-compatible / `glm-5.3-flash` / temperature 0 / max_tokens 1024
- Execution identity: eight sequential production-path Ask calls; zero retries; no re-index
- Evidence source: exact answers and citation records retained from the frozen session run
- Data gaps: normal Ask responses did not retain token usage, monetary cost, or provider `finish_reason`.
