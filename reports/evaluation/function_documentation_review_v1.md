# Function Documentation Review Matrix v1

## Experiment Identity

- Matrix: `function_documentation_review_matrix_v1`
- Matrix SHA-256: `c85fd5a3f5ffb5262d42936bda2f49fd53c26e6141befd341def7db1b375292a`
- Rubric: `function_documentation_review_rubric_v1`
- Rubric SHA-256: `1e6542b748de383cb87d0d1df2d3478e32e79ffeb2df663b63fb07717bec6741`
- Production path: `POST /projects/{project_id}/documentation`
- Provider/model: `openai_compatible` / `glm-5.3-flash`
- Temperature / max tokens: `0` / `1200`
- Retrieval: none; provider retries: 0; manual reruns: 0

English requests permit one provider call. Persian requests preserve the production language-validation regeneration policy, with a maximum of two calls only after a structurally valid first output fails Persian validation.

## Aggregate Results

| Measure | Result |
|---|---:|
| Semantic PASS | 0/6 |
| Semantic PARTIAL | 1/6 |
| Semantic FAIL | 2/6 |
| Semantic INCONCLUSIVE | 3/6 |
| Service-accepted contract results | 1/6 |
| Total provider calls | 6 |
| Persian cases regenerated | 0/3 |
| Mean latency | 16.240 s |
| Median latency | 15.513 s |
| Latency range | 10.142-24.817 s |

### Language Breakdown

| Language | PASS | PARTIAL | FAIL | INCONCLUSIVE |
|---|---:|---:|---:|---:|
| English | 0 | 1 | 1 | 1 |
| Persian | 0 | 0 | 1 | 2 |

## Per-Case Results

| Case | Language | Symbol | HTTP | Calls | Contract | Semantic | Attribution | Latency |
|---|---|---|---:|---:|---|---|---|---:|
| FD-01 | en | `escape_silent` | 200 | 1 | PASS | PARTIAL | GENERATION | 10.142 s |
| FD-02 | fa | `test_escape` | 502 | 1 | FAIL | FAIL | VALIDATION | 16.695 s |
| FD-03 | en | `Patient.__init__` | 502 | 1 | FAIL | FAIL | VALIDATION | 17.577 s |
| FD-04 | fa | `QueueArray.dequeue` | 502 | 1 | NOT_ASSESSABLE | INCONCLUSIVE | PROVIDER | 24.817 s |
| FD-05 | en | `Book.save` | 502 | 1 | NOT_ASSESSABLE | INCONCLUSIVE | PROVIDER | 13.879 s |
| FD-06 | fa | `CommentForm.clean_name` | 502 | 1 | NOT_ASSESSABLE | INCONCLUSIVE | PROVIDER | 14.332 s |

## Detailed Records

### FD-01 - `escape_silent`

- Repository/project: MarkupSafe M17 Smoke (`project_id=1`)
- Source: `src/markupsafe/__init__.py:48-61`
- Provider calls: 1
- First output passed service validation: True
- Application regeneration: False
- Contract: PASS; service accepted=True; citation valid=True
- Expected fact coverage: 3/3
- Missing expected facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: ["Markup"]
- Parameter / raises / side-effect / dependency validity: True / True / True / False
- Language adherence: True
- Semantic result: **PARTIAL** (GENERATION)
- Latency: 10.142 s
- Review note: All three required behavior facts are present and supported, but the generated dependencies field omits the frozen expected dependency Markup.

#### Attempt Records

- Attempt 1: provider_completed=True; schema/parameters=True; language=True; service=True; failure=None; latency=10.107s

#### Exact Captured Model Output

Attempt 1 SHA-256: `c71a6ae07fccecc6afbdc96388c50d14ef03e689eaab59749ae2ce259da0b825`

```text
{
  "summary": "Like escape but treats None as the empty string.",
  "detailed_description": "If s is None, the function returns an empty Markup instead of escaping it, which would otherwise produce the string 'None'. For any other value, it delegates to escape(s). This is useful with optional values, where escaping None directly yields Markup('None') rather than Markup('').",
  "parameters": [
    {
      "name": "s",
      "description": "The value to escape, of any type or None; when None it is treated as the empty string. Positional-only."
    }
  ],
  "return_value": "A Markup: an empty Markup() if s is None, otherwise the result of escape(s).",
  "raises": [],
  "side_effects": [],
  "dependencies": [
    "escape"
  ],
  "notes": [
    "Docstring examples: escape(None) returns Markup('None') while escape_silent(None) returns Markup('')."
  ]
}
```

#### Exact Final User-Visible API Response

```json
{"extracted":{"citation":{"project_id":1,"project_name":"MarkupSafe M17 Smoke","file_id":4,"symbol_id":12,"chunk_id":"174e43c398b28f69b412f2d8e4abf2ebd96e753e7979083dc965401a12b16c7c","qualified_name":"escape_silent","relative_source_path":"src/markupsafe/__init__.py","start_line":48,"end_line":61,"content_hash":"298008fe4439aff21113921fafefd1e3bf96850fcaad39354db8f66c6fdbc8e8"},"symbol_type":"function","signature":"def escape_silent(s) -> Markup","parameters":["s"],"return_annotation":"Markup","is_async":false,"source_file_hash":"9f20aafab60222866d0e475ea34a5bb7cda76ae174b55c89f067a12f60919191"},"generated":{"summary":"Like escape but treats None as the empty string.","detailed_description":"If s is None, the function returns an empty Markup instead of escaping it, which would otherwise produce the string 'None'. For any other value, it delegates to escape(s). This is useful with optional values, where escaping None directly yields Markup('None') rather than Markup('').","parameters":[{"name":"s","description":"The value to escape, of any type or None; when None it is treated as the empty string. Positional-only."}],"return_value":"A Markup: an empty Markup() if s is None, otherwise the result of escape(s).","raises":[],"side_effects":[],"dependencies":["escape"],"notes":["Docstring examples: escape(None) returns Markup('None') while escape_silent(None) returns Markup('')."]},"citations":[{"project_id":1,"project_name":"MarkupSafe M17 Smoke","file_id":4,"symbol_id":12,"chunk_id":"174e43c398b28f69b412f2d8e4abf2ebd96e753e7979083dc965401a12b16c7c","qualified_name":"escape_silent","relative_source_path":"src/markupsafe/__init__.py","start_line":48,"end_line":61,"content_hash":"298008fe4439aff21113921fafefd1e3bf96850fcaad39354db8f66c6fdbc8e8"}],"generation":{"schema_version":"1","provider":"openai_compatible","model":"glm-5.3-flash","language":"en"}}
```

### FD-02 - `test_escape`

- Repository/project: MarkupSafe M17 Smoke (`project_id=1`)
- Source: `tests/test_escape.py:33-34`
- Provider calls: 1
- First output passed service validation: False
- Application regeneration: False
- Contract: FAIL; service accepted=False; citation valid=None
- Expected fact coverage: not assessable/3
- Missing expected facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: []
- Parameter / raises / side-effect / dependency validity: False / None / None / None
- Language adherence: None
- Semantic result: **FAIL** (VALIDATION)
- Latency: 16.695 s
- Review note: The captured output ends inside detailed_description and is not valid JSON. No finish reason was captured, so truncation is not inferred.

#### Attempt Records

- Attempt 1: provider_completed=True; schema/parameters=False; language=None; service=False; failure=invalid_output; latency=16.678s

#### Exact Captured Model Output

Attempt 1 SHA-256: `8a371f7cdb6a138ee0850908696e211bed82b70a3636ebbe65c4c470a6592c3f`

```text
{"summary": "این تست بررسی می‌کند که نتیجه escape(value) با Markup(expect) برابر باشد.", "detailed_description": "عبارت assert نتیجه واقعی فراخوانی escape روی پارامتر ورودی value را با مقدار مورد انتظار Markup(expect)
```

#### Exact Final User-Visible API Response

```json
{"error":{"code":"documentation_invalid_output","message":"Model output is not valid JSON","details":{}}}
```

### FD-03 - `Patient.__init__`

- Repository/project: Hospital-System (`project_id=2`)
- Source: `models/patient.py:6-16`
- Provider calls: 1
- First output passed service validation: False
- Application regeneration: False
- Contract: FAIL; service accepted=False; citation valid=None
- Expected fact coverage: not assessable/10
- Missing expected facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: []
- Parameter / raises / side-effect / dependency validity: False / None / None / None
- Language adherence: None
- Semantic result: **FAIL** (VALIDATION)
- Latency: 17.577 s
- Review note: The captured output ends inside the notes array and is not valid JSON. No finish reason was captured, so truncation is not inferred.

#### Attempt Records

- Attempt 1: provider_completed=True; schema/parameters=False; language=None; service=False; failure=invalid_output; latency=17.547s

#### Exact Captured Model Output

Attempt 1 SHA-256: `2f21a662749cf32d320c089bd7d0c64055c2b527aa0627a6c7eb3c85297917bb`

```text
{
  "summary": "Initializes a Patient instance by storing the supplied personal details as attributes and creating a new Appointments instance.",
  "detailed_description": "Each constructor argument is assigned to a same-named instance attribute on the Patient object. The full_name attribute is derived by joining first_name and last_name with a single space. A new Appointments instance is created and assigned to the appointments attribute.",
  "parameters": [
    {"name": "self", "description": "The Patient instance being initialized."},
    {"name": "first_name", "description": "Stored as the instance attribute first_name and used to build full_name."},
    {"name": "last_name", "description": "Stored as the instance attribute last_name and used to build full_name."},
    {"name": "national_id", "description": "Stored as the instance attribute national_id."},
    {"name": "phone_num", "description": "Stored as the instance attribute phone_num."},
    {"name": "password", "description": "Stored as the instance attribute password."},
    {"name": "gender", "description": "Stored as the instance attribute gender."},
    {"name": "city", "description": "Stored as the instance attribute city."},
    {"name": "insurance_num", "description": "Stored as the instance attribute insurance_num."}
  ],
  "return_value": null,
  "raises": [],
  "side_effects": [
    "Sets the instance attributes first_name, last_name, national_id, phone_num, password, gender, city, and insurance_num from the corresponding arguments.",
    "Sets the instance attribute full_name to the value of first_name followed by a space and last_name.",
    "Creates an Appointments instance and assigns it to the instance attribute appointments."
  ],
  "dependencies": ["Appointments"],
  "notes": [
    "full_name is computed with an f-string
```

#### Exact Final User-Visible API Response

```json
{"error":{"code":"documentation_invalid_output","message":"Model output is not valid JSON","details":{}}}
```

### FD-04 - `QueueArray.dequeue`

- Repository/project: Hospital-System (`project_id=2`)
- Source: `data_structures/queue.py:22-33`
- Provider calls: 1
- First output passed service validation: False
- Application regeneration: False
- Contract: NOT_ASSESSABLE; service accepted=False; citation valid=None
- Expected fact coverage: not assessable/3
- Missing expected facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: []
- Parameter / raises / side-effect / dependency validity: None / None / None / None
- Language adherence: None
- Semantic result: **INCONCLUSIVE** (PROVIDER)
- Latency: 24.817 s
- Review note: The production path returned documentation_provider_failure and no model output was available for semantic review.

#### Attempt Records

- Attempt 1: provider_completed=False; schema/parameters=None; language=None; service=False; failure=provider_failure; latency=24.790s

#### Exact Captured Model Output

No model output was captured because the provider call failed.

#### Exact Final User-Visible API Response

```json
{"error":{"code":"documentation_provider_failure","message":"Documentation provider failed","details":{}}}
```

### FD-05 - `Book.save`

- Repository/project: CS-Bookstore (`project_id=3`)
- Source: `store/models.py:67-70`
- Provider calls: 1
- First output passed service validation: False
- Application regeneration: False
- Contract: NOT_ASSESSABLE; service accepted=False; citation valid=None
- Expected fact coverage: not assessable/3
- Missing expected facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: []
- Parameter / raises / side-effect / dependency validity: None / None / None / None
- Language adherence: None
- Semantic result: **INCONCLUSIVE** (PROVIDER)
- Latency: 13.879 s
- Review note: The production path returned documentation_provider_failure and no model output was available for semantic review.

#### Attempt Records

- Attempt 1: provider_completed=False; schema/parameters=None; language=None; service=False; failure=provider_failure; latency=13.848s

#### Exact Captured Model Output

No model output was captured because the provider call failed.

#### Exact Final User-Visible API Response

```json
{"error":{"code":"documentation_provider_failure","message":"Documentation provider failed","details":{}}}
```

### FD-06 - `CommentForm.clean_name`

- Repository/project: CS-Bookstore (`project_id=3`)
- Source: `blog/forms.py:45-51`
- Provider calls: 1
- First output passed service validation: False
- Application regeneration: False
- Contract: NOT_ASSESSABLE; service accepted=False; citation valid=None
- Expected fact coverage: not assessable/4
- Missing expected facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: []
- Parameter / raises / side-effect / dependency validity: None / None / None / None
- Language adherence: None
- Semantic result: **INCONCLUSIVE** (PROVIDER)
- Latency: 14.332 s
- Review note: The production path returned documentation_provider_failure and no model output was available for semantic review.

#### Attempt Records

- Attempt 1: provider_completed=False; schema/parameters=None; language=None; service=False; failure=provider_failure; latency=14.293s

#### Exact Captured Model Output

No model output was captured because the provider call failed.

#### Exact Final User-Visible API Response

```json
{"error":{"code":"documentation_provider_failure","message":"Documentation provider failed","details":{}}}
```

## Failure Attribution

- FD-02 and FD-03 are validation failures: provider content was captured, but it was not valid complete JSON and the production service rejected it.
- FD-04 through FD-06 are provider failures: no model output was captured, so semantic quality is inconclusive.
- FD-01 was contract-valid and fully covered its three behavior facts, but omitted `Markup` from the frozen expected dependency list.

No failure is attributed to retrieval because Function Documentation does not use retrieval. No finish reason, usage, cost, or hidden reasoning field was retained by the provider adapter, so none is inferred.

## Conclusion

**M20 cannot be closed from this review.** The service accepted 1/6 final outputs. The semantic distribution was 0 PASS, 1 PARTIAL, 2 FAIL, and 3 INCONCLUSIVE.

## Reproducibility

- Matrix SHA-256: `c85fd5a3f5ffb5262d42936bda2f49fd53c26e6141befd341def7db1b375292a`
- Rubric SHA-256: `1e6542b748de383cb87d0d1df2d3478e32e79ffeb2df663b63fb07717bec6741`
- Model: `glm-5.3-flash`
- Provider: `openai_compatible`
- Temperature: `0`
- Max tokens: `1200`
- Provider/transport retries: `0`
- Manual reruns: `0`
