# DevLoop-CI

Independent synthetic smoke and regression tests on standard GitHub-hosted Windows and Linux, Python 3.12. No private source, credentials, model weights, production data, or self-hosted runner access. These tests do not certify the DevLoop product.

## Test inventory

- 5 basic environment, SQLite, Python AST, Git and UTF-8 file tests.
- 7 independent repair-sequence acceptance tests.
- 10 portable path, strict JSON, atomic state replacement and exact digest tests.
- 4 disposable Git tests for ref compare-and-swap, source isolation, frozen blobs and dirty worktrees.
- Windows-only PowerShell parser positive/negative controls and script syntax check.

Run the 26 Python tests using Python 3.12 and Git:

```sh
python -B -m unittest -v test_cloud_smoke test_acceptance_contract test_ci_contracts test_git_contracts
```

On Windows with PowerShell 7:

```powershell
./Test-PowerShellContracts.ps1
```

The helpers are generic reference implementations. Path validation is lexical only, not filesystem confinement; atomic replacement assumes a trusted directory and does not guarantee recovery after power loss or serialize competing writers. PowerShell parsing does not prove runtime behavior.

Private product validation remains separate. Shared code may count as preflight evidence only when exact tested source bytes match the private candidate; synthetic tests do not establish actual VM, model, Docker, installation or production acceptance. Never add secrets, private source, private artifacts or VM access to this repository.
