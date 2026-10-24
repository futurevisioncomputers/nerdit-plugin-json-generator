# DEPRECATED — code a learner must never see or download

`check_modern_code.py` reads this file. It scans every Python block a lesson shows (run lines,
Try It starters, predict and solution blocks) and every downloaded `.py` and `.ipynb`. Comments
are not scanned, so a lesson may still *say* "never call `datetime.utcnow()`".

Each line of a block is `<regular expression>  =>  <what to write instead>`.

Why: a learner who copies a deprecated call gets a warning on the next library release and an
error on the one after. A course must teach the code they will keep using.

```deprecated
\btyping\.(List|Dict|Tuple|Set|Optional|Union)\b  =>  list, dict, tuple, set, X | None, X | Y
\bfrom typing import\b[^\n]*\b(List|Dict|Tuple|Set|Optional|Union)\b  =>  list, dict, tuple, set, X | None, X | Y
\bdatetime\.utcnow\(  =>  datetime.now(UTC)
\butcfromtimestamp\(  =>  datetime.fromtimestamp(ts, UTC)
\basyncio\.get_event_loop\(\)  =>  asyncio.run()
\bexcept\s*\(?\s*asyncio\.TimeoutError\b  =>  except TimeoutError (one class since 3.11)
@\w+\.on_event\(  =>  FastAPI lifespan= context manager
\.parse_obj\(|\.parse_raw\(  =>  Model.model_validate(), Model.model_validate_json()
^\s*class Config\s*:  =>  model_config = ConfigDict(...)
@validator\(  =>  @field_validator
@root_validator\b  =>  @model_validator
\.dict\(\s*\)  =>  .model_dump()
\binplace\s*=\s*True\b  =>  assign the result: df = df.dropna()
\bOneHotEncoder\([^)]*\bsparse\s*=  =>  OneHotEncoder(sparse_output=...)
\bos\.popen\(  =>  subprocess.run()
\b(import|from)\s+distutils\b  =>  setuptools or sysconfig
^\s*import imp\b  =>  importlib
```

**New courses only** (decision 12, 2026-10-23). Flagged when the check runs with `--new-course`;
existing courses switch when they are regenerated.

```new-course
^\s*(import httpx\b|from httpx\b)  =>  httpx2 (import httpx2): Pydantic's drop-in continuation of httpx
```

Found at run time instead (the checks run every file with warnings as errors, `-W error`):
`DataFrame.append` (removed in pandas 2), Pydantic v1 `.json()` on a model, and any library
deprecation this list does not name yet. Add a line here when a run finds one.
