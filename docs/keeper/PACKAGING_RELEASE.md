# Packaging and Release

Build with:

`powershell -File scripts/build-keeper.ps1 -PythonPath python`

Smoke-test with:

`powershell -File scripts/test-keeper-package.ps1 -PythonPath python`

The output is `dist/keeper.pyz`; generated artifacts are release outputs and are not
committed. It contains the Keeper package and launches one desktop process. Upgrades
replace the `.pyz`; schema migrations run at startup and application data remains
separate. Release checks require focused/full tests, strict typing, compilation,
diff checks, foundation verification, dependency checks, package smoke, and a fresh
mock pilot.
