# Function Documentation Review Matrix v2

## Frozen Identity

- Matrix SHA-256: `2408cc6fbc55158deeb97070d6df3278ff15a75a5645fae7575e10162bddc890`
- Rubric SHA-256: `ad9664d35443b4d29c9890d3b118e2e3684b5f9c181fcdc759ba74b2762a5a13`
- Implementation source snapshot: `71a6dc3df6a2448e079902ae3c2e257a6088b57406ab27a053871c6a4a5c3e5f`
- Provider/model: `openai_compatible` / `glm-5.3-flash`
- Temperature / max tokens: `0` / `1200`
- Retrieval: none; provider retries: 0; manual reruns: 0

## Aggregate

| Measure | Result |
|---|---:|
| PASS | 1/6 |
| PARTIAL | 2/6 |
| FAIL | 0/6 |
| INCONCLUSIVE | 3/6 |
| Service accepted | 3/6 |
| Provider calls | 6 |
| Persian regenerations | 0/3 |
| Mean latency | 16.837 s |
| Median latency | 17.013 s |
| Range | 8.750-25.881 s |

## Language Breakdown

| Language | PASS | PARTIAL | FAIL | INCONCLUSIVE |
|---|---:|---:|---:|---:|
| English | 1 | 2 | 0 | 0 |
| Persian | 0 | 0 | 0 | 3 |

## Per-Case Results

| Case | Symbol | HTTP | Calls | Finish | Provider error | Contract | Semantic | Latency |
|---|---|---:|---:|---|---|---|---|---:|
| FD-01 | `escape_silent` | 200 | 1 | stop | none | PASS | PARTIAL | 8.750 s |
| FD-02 | `test_escape` | 502 | 1 | not available | invalid_response | NOT_ASSESSABLE | INCONCLUSIVE | 16.901 s |
| FD-03 | `Patient.__init__` | 200 | 1 | stop | none | PASS | PASS | 13.648 s |
| FD-04 | `QueueArray.dequeue` | 502 | 1 | not available | invalid_response | NOT_ASSESSABLE | INCONCLUSIVE | 18.716 s |
| FD-05 | `Book.save` | 200 | 1 | stop | none | PASS | PARTIAL | 17.126 s |
| FD-06 | `CommentForm.clean_name` | 502 | 1 | not available | invalid_response | NOT_ASSESSABLE | INCONCLUSIVE | 25.881 s |

## Detailed Records

### FD-01 - `escape_silent`

- Source: `src/markupsafe/__init__.py:48-61`
- Provider calls: 1
- Finish reason: stop
- Explicit truncation: False
- Safe provider error type: none
- Regeneration: False
- Contract: PASS; service accepted=True; citation valid=True
- Expected-fact coverage: 3/3
- Missing facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: ["Markup"]
- Parameter / raises / side-effect / dependency validity: True / True / True / False
- Language adherence: True
- Semantic verdict: **PARTIAL** (GENERATION_SEMANTICS)
- Latency: 8.750 s
- Note: All frozen behavior facts are present, but the generated dependencies field omits the frozen expected dependency Markup.

#### Attempt metadata

- Call 1: completed=True; finish=stop; truncation=False; provider_error=None; validation=accepted; latency=8.717s

#### Exact Captured Model Output

Attempt 1 SHA-256: `bc19f087e8dc48924b7c6b50fceb8ccec7e42cecded54e6c939402a45a817773`

```text
{
  "summary": "Like escape but treats None as the empty string.",
  "detailed_description": "Returns an empty Markup when s is None, and otherwise returns escape(s). This is useful with optional values, since escaping None directly would produce the string 'None'. For example, escape(None) yields Markup('None') while escape_silent(None) yields Markup('').",
  "parameters": [
    {
      "name": "s",
      "description": "The value to escape. If it is None, it is treated as the empty string."
    }
  ],
  "return_value": "The escaped value as a Markup, or an empty Markup if s is None.",
  "raises": [],
  "side_effects": [],
  "dependencies": [
    "escape"
  ],
  "notes": [
    "The parameter s is positional-only.",
    "Defined in src/markupsafe/__init__.py at lines 48-61."
  ]
}
```

#### Exact Final User-Visible API Response

```json
{"extracted":{"citation":{"project_id":1,"project_name":"MarkupSafe M17 Smoke","file_id":4,"symbol_id":12,"chunk_id":"174e43c398b28f69b412f2d8e4abf2ebd96e753e7979083dc965401a12b16c7c","qualified_name":"escape_silent","relative_source_path":"src/markupsafe/__init__.py","start_line":48,"end_line":61,"content_hash":"298008fe4439aff21113921fafefd1e3bf96850fcaad39354db8f66c6fdbc8e8"},"symbol_type":"function","signature":"def escape_silent(s) -> Markup","parameters":["s"],"return_annotation":"Markup","is_async":false,"source_file_hash":"9f20aafab60222866d0e475ea34a5bb7cda76ae174b55c89f067a12f60919191"},"generated":{"summary":"Like escape but treats None as the empty string.","detailed_description":"Returns an empty Markup when s is None, and otherwise returns escape(s). This is useful with optional values, since escaping None directly would produce the string 'None'. For example, escape(None) yields Markup('None') while escape_silent(None) yields Markup('').","parameters":[{"name":"s","description":"The value to escape. If it is None, it is treated as the empty string."}],"return_value":"The escaped value as a Markup, or an empty Markup if s is None.","raises":[],"side_effects":[],"dependencies":["escape"],"notes":["The parameter s is positional-only.","Defined in src/markupsafe/__init__.py at lines 48-61."]},"citations":[{"project_id":1,"project_name":"MarkupSafe M17 Smoke","file_id":4,"symbol_id":12,"chunk_id":"174e43c398b28f69b412f2d8e4abf2ebd96e753e7979083dc965401a12b16c7c","qualified_name":"escape_silent","relative_source_path":"src/markupsafe/__init__.py","start_line":48,"end_line":61,"content_hash":"298008fe4439aff21113921fafefd1e3bf96850fcaad39354db8f66c6fdbc8e8"}],"generation":{"schema_version":"1","provider":"openai_compatible","model":"glm-5.3-flash","language":"en"}}
```

### FD-02 - `test_escape`

- Source: `tests/test_escape.py:33-34`
- Provider calls: 1
- Finish reason: not available
- Explicit truncation: False
- Safe provider error type: invalid_response
- Regeneration: False
- Contract: NOT_ASSESSABLE; service accepted=False; citation valid=None
- Expected-fact coverage: not assessable/3
- Missing facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: []
- Parameter / raises / side-effect / dependency validity: None / None / None / None
- Language adherence: None
- Semantic verdict: **INCONCLUSIVE** (PROVIDER)
- Latency: 16.901 s
- Note: The adapter returned safe provider_error_type=invalid_response and no model content was available for semantic review.

#### Attempt metadata

- Call 1: completed=False; finish=None; truncation=False; provider_error=invalid_response; validation=provider_failure; latency=16.885s

#### Exact Captured Model Output

No model output was captured because the provider adapter returned an error.

#### Exact Final User-Visible API Response

```json
{"error":{"code":"documentation_provider_failure","message":"Documentation provider failed","details":{"provider_error_type":"invalid_response"}}}
```

### FD-03 - `Patient.__init__`

- Source: `models/patient.py:6-16`
- Provider calls: 1
- Finish reason: stop
- Explicit truncation: False
- Safe provider error type: none
- Regeneration: False
- Contract: PASS; service accepted=True; citation valid=True
- Expected-fact coverage: 10/10
- Missing facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: []
- Parameter / raises / side-effect / dependency validity: True / True / True / True
- Language adherence: True
- Semantic verdict: **PASS** (NONE)
- Latency: 13.648 s
- Note: All ten frozen assignment facts, the Appointments dependency, and required identity/citation information are present without unsupported claims.

#### Attempt metadata

- Call 1: completed=True; finish=stop; truncation=False; provider_error=None; validation=accepted; latency=13.615s

#### Exact Captured Model Output

Attempt 1 SHA-256: `e333fe2f393c3be0274b2a1465fa6a687ff62efd68c58442c203dffbfffc3863`

```text
{
  "summary": "Initializes a Patient instance with personal, contact, and insurance details, a derived full name, and a new Appointments instance.",
  "detailed_description": "Stores the provided first_name, last_name, national_id, phone_num, password, gender, city, and insurance_num as instance attributes. Builds the full_name attribute by joining first_name and last_name with a space. Assigns a newly created Appointments instance to the appointments attribute.",
  "parameters": [
    {"name": "self", "description": null},
    {"name": "first_name", "description": null},
    {"name": "last_name", "description": null},
    {"name": "national_id", "description": null},
    {"name": "phone_num", "description": null},
    {"name": "password", "description": null},
    {"name": "gender", "description": null},
    {"name": "city", "description": null},
    {"name": "insurance_num", "description": null}
  ],
  "return_value": null,
  "raises": [],
  "side_effects": [
    "Sets instance attributes first_name, last_name, national_id, phone_num, password, gender, city, full_name, insurance_num, and appointments."
  ],
  "dependencies": [
    "Appointments"
  ],
  "notes": [
    "full_name is formatted as the first name followed by the last name separated by a space.",
    "appointments is initialized to a new Appointments instance."
  ]
}
```

#### Exact Final User-Visible API Response

```json
{"extracted":{"citation":{"project_id":2,"project_name":"Hospital-System","file_id":36,"symbol_id":452,"chunk_id":"42a0c185f2075dcce043fd60f2d6469f3048b722ebc4329967e065691664c5e2","qualified_name":"Patient.__init__","relative_source_path":"models/patient.py","start_line":6,"end_line":16,"content_hash":"bedd9e98c2b05f35c5c1f7af90990004d46553d0325729969df4e4bda4ba97c2"},"symbol_type":"method","signature":"def __init__(self, first_name, last_name, national_id, phone_num, password, gender, city, insurance_num)","parameters":["self","first_name","last_name","national_id","phone_num","password","gender","city","insurance_num"],"return_annotation":null,"is_async":false,"source_file_hash":"94807dc22e12abf8a46733e4b7333973834aa74ec17d4080d1986d85f054b873"},"generated":{"summary":"Initializes a Patient instance with personal, contact, and insurance details, a derived full name, and a new Appointments instance.","detailed_description":"Stores the provided first_name, last_name, national_id, phone_num, password, gender, city, and insurance_num as instance attributes. Builds the full_name attribute by joining first_name and last_name with a space. Assigns a newly created Appointments instance to the appointments attribute.","parameters":[{"name":"self","description":null},{"name":"first_name","description":null},{"name":"last_name","description":null},{"name":"national_id","description":null},{"name":"phone_num","description":null},{"name":"password","description":null},{"name":"gender","description":null},{"name":"city","description":null},{"name":"insurance_num","description":null}],"return_value":null,"raises":[],"side_effects":["Sets instance attributes first_name, last_name, national_id, phone_num, password, gender, city, full_name, insurance_num, and appointments."],"dependencies":["Appointments"],"notes":["full_name is formatted as the first name followed by the last name separated by a space.","appointments is initialized to a new Appointments instance."]},"citations":[{"project_id":2,"project_name":"Hospital-System","file_id":36,"symbol_id":452,"chunk_id":"42a0c185f2075dcce043fd60f2d6469f3048b722ebc4329967e065691664c5e2","qualified_name":"Patient.__init__","relative_source_path":"models/patient.py","start_line":6,"end_line":16,"content_hash":"bedd9e98c2b05f35c5c1f7af90990004d46553d0325729969df4e4bda4ba97c2"}],"generation":{"schema_version":"1","provider":"openai_compatible","model":"glm-5.3-flash","language":"en"}}
```

### FD-04 - `QueueArray.dequeue`

- Source: `data_structures/queue.py:22-33`
- Provider calls: 1
- Finish reason: not available
- Explicit truncation: False
- Safe provider error type: invalid_response
- Regeneration: False
- Contract: NOT_ASSESSABLE; service accepted=False; citation valid=None
- Expected-fact coverage: not assessable/3
- Missing facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: []
- Parameter / raises / side-effect / dependency validity: None / None / None / None
- Language adherence: None
- Semantic verdict: **INCONCLUSIVE** (PROVIDER)
- Latency: 18.716 s
- Note: The adapter returned safe provider_error_type=invalid_response and no model content was available for semantic review.

#### Attempt metadata

- Call 1: completed=False; finish=None; truncation=False; provider_error=invalid_response; validation=provider_failure; latency=18.689s

#### Exact Captured Model Output

No model output was captured because the provider adapter returned an error.

#### Exact Final User-Visible API Response

```json
{"error":{"code":"documentation_provider_failure","message":"Documentation provider failed","details":{"provider_error_type":"invalid_response"}}}
```

### FD-05 - `Book.save`

- Source: `store/models.py:67-70`
- Provider calls: 1
- Finish reason: stop
- Explicit truncation: False
- Safe provider error type: none
- Regeneration: False
- Contract: PASS; service accepted=True; citation valid=True
- Expected-fact coverage: 3/3
- Missing facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: ["super().save"]
- Parameter / raises / side-effect / dependency validity: True / True / True / False
- Language adherence: True
- Semantic verdict: **PARTIAL** (GENERATION_SEMANTICS)
- Latency: 17.126 s
- Note: All frozen behavior facts are present, but the generated dependencies field omits the frozen expected dependency super().save.

#### Attempt metadata

- Call 1: completed=True; finish=stop; truncation=False; provider_error=None; validation=accepted; latency=17.089s

#### Exact Captured Model Output

Attempt 1 SHA-256: `353a20cf047ad5f94a5e53f26636423c7d8aeaa13af921c32422d1f209a07b27`

```text
{
  "summary": "Saves the Book instance, generating a slug from the title when one is not already set.",
  "detailed_description": "If self.slug is empty, it is assigned the result of slugify(self.title). The method then calls the parent class save method, forwarding *args and **kwargs unchanged.",
  "parameters": [
    {"name": "self", "description": null},
    {"name": "*args", "description": null},
    {"name": "**kwargs", "description": null}
  ],
  "return_value": null,
  "raises": [],
  "side_effects": [
    "Sets self.slug to slugify(self.title) when self.slug is empty",
    "Delegates persistence to the parent class save method"
  ],
  "dependencies": [
    "slugify"
  ],
  "notes": [
    "Defined in store/models.py at lines 67-70"
  ]
}
```

#### Exact Final User-Visible API Response

```json
{"extracted":{"citation":{"project_id":3,"project_name":"CS-Bookstore","file_id":85,"symbol_id":609,"chunk_id":"862dff324241a2bb0ceccd033852bd5c6a0f0b969162a4dbee8f077968772b17","qualified_name":"Book.save","relative_source_path":"store/models.py","start_line":67,"end_line":70,"content_hash":"f82bb5ec6199de9881caf26641e7a869037bb7d4e4ad05c165f419aa99a16ee7"},"symbol_type":"method","signature":"def save(self, *args, **kwargs)","parameters":["self","*args","**kwargs"],"return_annotation":null,"is_async":false,"source_file_hash":"eea8d5931e798bf5bc390e66dadb5a3cc05f1a8fc28eaa4b122de2fe2c4291a4"},"generated":{"summary":"Saves the Book instance, generating a slug from the title when one is not already set.","detailed_description":"If self.slug is empty, it is assigned the result of slugify(self.title). The method then calls the parent class save method, forwarding *args and **kwargs unchanged.","parameters":[{"name":"self","description":null},{"name":"*args","description":null},{"name":"**kwargs","description":null}],"return_value":null,"raises":[],"side_effects":["Sets self.slug to slugify(self.title) when self.slug is empty","Delegates persistence to the parent class save method"],"dependencies":["slugify"],"notes":["Defined in store/models.py at lines 67-70"]},"citations":[{"project_id":3,"project_name":"CS-Bookstore","file_id":85,"symbol_id":609,"chunk_id":"862dff324241a2bb0ceccd033852bd5c6a0f0b969162a4dbee8f077968772b17","qualified_name":"Book.save","relative_source_path":"store/models.py","start_line":67,"end_line":70,"content_hash":"f82bb5ec6199de9881caf26641e7a869037bb7d4e4ad05c165f419aa99a16ee7"}],"generation":{"schema_version":"1","provider":"openai_compatible","model":"glm-5.3-flash","language":"en"}}
```

### FD-06 - `CommentForm.clean_name`

- Source: `blog/forms.py:45-51`
- Provider calls: 1
- Finish reason: not available
- Explicit truncation: False
- Safe provider error type: invalid_response
- Regeneration: False
- Contract: NOT_ASSESSABLE; service accepted=False; citation valid=None
- Expected-fact coverage: not assessable/4
- Missing facts: []
- Unsupported/fabricated claims: []
- Missing expected dependencies: []
- Parameter / raises / side-effect / dependency validity: None / None / None / None
- Language adherence: None
- Semantic verdict: **INCONCLUSIVE** (PROVIDER)
- Latency: 25.881 s
- Note: The adapter returned safe provider_error_type=invalid_response and no model content was available for semantic review.

#### Attempt metadata

- Call 1: completed=False; finish=None; truncation=False; provider_error=invalid_response; validation=provider_failure; latency=25.850s

#### Exact Captured Model Output

No model output was captured because the provider adapter returned an error.

#### Exact Final User-Visible API Response

```json
{"error":{"code":"documentation_provider_failure","message":"Documentation provider failed","details":{"provider_error_type":"invalid_response"}}}
```

## Descriptive v1/v2 Comparison

| Run | PASS | PARTIAL | FAIL | INCONCLUSIVE | Service accepted |
|---|---:|---:|---:|---:|---:|
| v1 | 0 | 1 | 2 | 3 | 1/6 |
| v2 | 1 | 2 | 0 | 3 | 3/6 |

The difference is descriptive only. The observability hardening was diagnostic rather than generative, so this run does not establish improved semantic quality or provider reliability.

## New Diagnostic Evidence

- Accepted FD-01, FD-03, and FD-05 explicitly reported `finish_reason=stop`.
- FD-02, FD-04, and FD-06 exposed safe `provider_error_type=invalid_response`.
- No request reported `finish_reason=length`; v2 has no explicit truncation case.
- The remaining `invalid_response` category does not distinguish invalid upstream JSON from missing choices, missing content, or empty content.

## Conclusion

**M20 cannot be closed from v2.** Only 3/6 requests were service-accepted, and no Persian case produced a reviewable result. The evidence does not yet justify prompt, validator, retry, or token-budget changes; only narrower safe invalid-response diagnostics are presently justified.
