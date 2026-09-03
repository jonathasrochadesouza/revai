## ADDED Requirements

### Requirement: Structured error response contract
Every non-2xx JSON response from the RevAI API SHALL return `detail` as an
object (or array of objects, for multi-field validation failures) shaped as
`{ "error_key": string, "params": object }`. No non-2xx response SHALL return
`detail` as a plain string or as FastAPI's default pydantic error array shape.

#### Scenario: Validation error on config save returns structured detail
- **WHEN** a client submits `PUT /api/config` with `warn_above_usd` greater
  than `max_spend_usd`
- **THEN** the response is `422` with
  `detail.error_key == "budget.warn_above_exceeds_max"` and
  `detail.params == { "warn_above_usd": <submitted value>, "max_spend_usd": <submitted value> }`

#### Scenario: Not-found error returns structured detail
- **WHEN** a client requests a project id that does not exist
- **THEN** the response is `404` with a non-empty `detail.error_key` starting
  with `"project."` and a `detail.params` object (which may be empty)

#### Scenario: Unmapped internal error still returns the contract shape
- **WHEN** an unexpected server error occurs that is not a `RevaiError` or a
  `PydanticCustomError`-backed validation failure
- **THEN** the response still returns `detail` as an object with an
  `error_key` (e.g. `"internal.unexpected_error"`) rather than a raw traceback
  or a bare string

### Requirement: Central exception handling
The backend SHALL convert every application-raised error into the structured
contract through exactly two exception handlers registered on the FastAPI app
(one for `RevaiError`, one for `RequestValidationError`). No route handler
SHALL construct a `JSONResponse` or format `detail` text directly.

#### Scenario: A route raises a domain error
- **WHEN** a route handler raises `RevaiError(status_code=422, error_key="git.not_a_repository", params={"path": "/tmp/x"})`
- **THEN** the `RevaiError` exception handler produces a `422` response whose
  body matches the structured contract without the route handler having built
  the response body itself

#### Scenario: A pydantic validator rejects a field
- **WHEN** a `@model_validator` or `@field_validator` raises a
  `PydanticCustomError` with an error key and a context dict
- **THEN** the `RequestValidationError` handler renders a `422` response using
  that error key as `detail.error_key` and that context dict as `detail.params`,
  not pydantic's default `"Value error, ..."` message text

### Requirement: Every user-facing error site has an assigned error key
Every current user-facing error-producing site in the API (pydantic
validators in `domain/models.py`, `export/serializers.py`,
`api/routes/reviews.py`; `HTTPException` sites in `api/routes/*.py`; and
exceptions raised by `git/repo.py`, `storage/base.py`, `storage/repositories.py`,
`system/folder_picker.py`, `pipeline/ai.py`, `analyzers/runner.py`) SHALL be
migrated to raise a `RevaiError` or a `PydanticCustomError` carrying a
dot-namespaced `error_key` (`<domain>.<reason>`) instead of a hand-formatted
string. No user-facing raise site SHALL forward a raw `OSError`, `YAMLError`,
git stderr string, or pydantic default message as the primary response text;
where that raw text remains useful for debugging, it SHALL be carried as a
named entry inside `params` (e.g. `params.detail`), never concatenated into a
key or into pre-formatted prose.

#### Scenario: Git failure exposes structured params instead of raw stderr as the message
- **WHEN** a git command invoked by the API fails
- **THEN** the resulting error response has a specific `error_key` under the
  `git.` namespace and carries the raw git output as `detail.params.detail`
  rather than as the entire `error_key` or as unstructured `detail` text

#### Scenario: Malformed config.yaml on disk
- **WHEN** `config.yaml` fails schema validation on read
- **THEN** the resulting error response has `error_key` under the `storage.`
  namespace and `params` includes the file name and the underlying validation
  summary as a named field, not as the sole message text

### Requirement: Frontend error translation catalog
The frontend SHALL resolve every `error_key` received from the API into a
human-readable sentence in both `en-US` and `pt-BR` using a catalog module
that maps `error_key` to locale-specific templates, interpolating `params`
into placeholders. The resolution SHALL use the user's current `ui.locale`
preference (the same locale value that already drives navigation-label
translation).

#### Scenario: Known error key renders localized text
- **WHEN** the frontend receives `error_key: "budget.warn_above_exceeds_max"`
  with `params: { warn_above_usd: 1.4, max_spend_usd: 0.25 }` and the active
  locale is `pt-BR`
- **THEN** the rendered message is the Portuguese template with `1.4` and
  `0.25` interpolated in place of their placeholders, and contains no raw
  `error_key` string, no `loc` path fragments, and no literal `"Value error"`
  text

#### Scenario: Known error key renders in English
- **WHEN** the same error is received while the active locale is `en-US`
- **THEN** the rendered message is the English template with the same
  interpolated values

#### Scenario: Unmapped error key degrades safely
- **WHEN** the frontend receives an `error_key` that does not exist in its
  local catalog
- **THEN** it renders a generic locale-appropriate fallback message that
  includes the raw `error_key` for diagnosability, and does not throw an
  unhandled exception or render blank/empty error text

#### Scenario: Multiple validation failures in one response
- **WHEN** the API returns `detail` as an array of
  `{ error_key, params }` entries for a single request
- **THEN** the frontend resolves each entry independently through the catalog
  and joins the resulting sentences into one combined message, in the request's
  active locale
