# Contributing

## Local verification

```powershell
$env:PYTHONPATH = "src"
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

Keep transport parsing in `api`, use-case orchestration in `services`, state
meaning in `domain`, and persistence behavior behind the repository protocol.
New collection inputs must be bounded. New resource reads must include an
organization scope. New writes to existing resources must define their
concurrency and retry behavior.

Pull requests should include boundary and failure tests, not only a happy path.

