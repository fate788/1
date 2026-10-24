# Codex Handoff

## Project

This repository contains the static-analysis and maintenance tooling for an old StarCraft II trainer, with the current work focused on the 260804 payload and compatibility investigation. The intended GitHub destination is `https://github.com/fate788/1.git`.

The project is being migrated from a local analysis workspace. No historical Git repository was present in the workspace, so this document records the current state without claiming an earlier commit history.

## Current objective

Create a reversible, testable maintenance path for the 260804 trainer while keeping the original EXE, game files, saved games, credentials, and security settings unchanged. The work must separate startup-check compatibility from later `SC2_x64.exe` feature compatibility.

## Completed work

- Static analysis identified the custom PE/Lua payload chain and the 260804 root startup checks.
- Child Proto 5 and captured table `R23` were structurally parsed. The table is filled from fixed-width response slices and consumed by the `OnTimer` path.
- The direct consumers at Lua PCs 189 and 203–205 were mapped. Their instruction-level selection constants are 306 and 317, and both paths call the global `gameIntCode(true)`.
- Runtime observation confirmed a real payload chain, the verified `lua53-64.dll`, a 887-byte response, equal marker/key metadata, `string.find` returning nil, and the explicit false path at Child Proto 5 PCs 28–29. The observation stopped diagnostically and did not validate normal UI or game functionality.
- A fail-closed local policy model exists at `work/repair-260804/local-module/local_maintenance_policy.py`. It does not contact the network, execute Lua, or force a true result.
- A custom LuaScript parser/writer exists at `work/repair-260804/roundtrip_parser.py` and `roundtrip_writer.py`. Three existing samples (0604, 260718, 260804) were parsed, serialized from the parsed structure, reparsed, and verified byte-identical with matching structure and zero remaining bytes. See `work/repair-260804/roundtrip/roundtrip-report.json` when the generated artifacts are available locally.
- `work/repair-260804/cetrainer_codec.py` and `archive_codec.py` provide bounded, structure-based outer-container decode/encode. The existing codec report records content-preserving no-op and controlled-mutation tests for all three samples; recompression makes the outer byte stream non-identical while decoded XML/entries remain identical.
- `work/repair-260804/tests/run_codec_tests.py` is the unified codec test entry point. Generated test-run binaries, PML traces, decoded payloads, and local baselines are ignored by Git.

## Current files and entry points

- `work/repair-260804/roundtrip_parser.py` — bounded custom Lua format parser.
- `work/repair-260804/roundtrip_writer.py` — structure-based Lua serializer.
- `work/repair-260804/local-module/local_maintenance_policy.py` — offline R23/Child Proto 5 policy model.
- `work/repair-260804/tests/run_offline_tests.py` — repair policy unit-test entry point.
- `work/repair-260804/build_repair_candidate.py` — hash-guarded candidate builder.
- `work/archive-history/finalized/parse_custom_luac.py` — earlier read-only parser and reference implementation.

## Test commands

From the repository root:

```powershell
python .\work\repair-260804\tests\run_offline_tests.py
python .\work\repair-260804\roundtrip_writer.py
python .\work\repair-260804\tests\run_codec_tests.py
python .\work\repair-260804\build_repair_candidate.py
```

The first command tests the local policy module with synthetic data. The second performs the three-sample LuaScript no-op roundtrip. The third runs the LuaScript, CETRAINER, and ARCHIVE content-preserving codec tests, including controlled constant/XML/entry mutations; it never starts the target or game. The final command verifies reference hashes and refuses to emit an EXE unless the remaining policy and integration prerequisites are available.

## Verified

- Original trainer copy SHA-256: `CEA1493191BBD5513F556413D167E2FAD81879E91294DFF7C5CDCA61497CC9EF`.
- Current Lua DLL SHA-256: `436F6BF9AC414E7E7259BEF4F6E287702A41E1FDDBDD9AF7D43350D47539A3C9`.
- Inner LuaScript no-op roundtrip: three samples byte-identical and structurally identical.
- Policy tests and diagnostic metadata regressions were recorded separately; they do not prove EXE compatibility.

## Not verified / remaining blockers

- `gameIntCode` registration and implementation are not recovered. The Lua payload contains call sites, but the host registration/side-effect contract is not yet identified.
- The meaning of response records and the distinction between states 306 and 317 remain incomplete.
- CETRAINER outer decode/encode is verified at the decoded-content level for the three samples. Re-encoding is not byte-identical because the current deflate output is not deterministic; the controlled XML mutation tests pass.
- ARCHIVE container repacking is verified at the decoded-entry/trailing-data level for the three samples. Re-encoding is not byte-identical for the same compression reason; controlled entry mutation tests pass.
- The codec implementations are not yet wired into a complete EXE rebuild or validated loader path.
- No modified Lua payload or executable candidate has been generated.
- Normal UI startup and Base98370 feature behavior remain untested.
- No target process or game process should be started as part of repository migration.

## Safety and migration rules

- Never commit real `.env`, API keys, passwords, tokens, private keys, local credentials, PML traces, binary payloads, or virtual environments.
- Keep original EXE and game files outside Git-tracked source. Work only on copies.
- Do not force-push or rewrite remote history. The first push should use a new commit on `main` after review.
- Do not start the trainer or attach to the game while preparing the repository.

## Next development sequence

1. Recover `gameIntCode` registration and the concrete 306/317 state flow from the host integration layer.
2. Keep the codec mutation tests as regression coverage and document any non-deterministic compression metadata.
3. Define a verified local policy record format without inventing response data.
4. Integrate the codecs into a complete, hash-guarded packaging path and only then evaluate a candidate.
5. Only after a candidate is actually built and tested, prepare a single controlled startup test. Game feature compatibility remains a separate acceptance stage.
