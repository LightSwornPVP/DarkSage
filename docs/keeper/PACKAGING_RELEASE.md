# Packaging and Release

The product desktop is built with the isolated PySide6/Nuitka toolchain:

```powershell
powershell -File scripts/build-keeper-desktop.ps1 `
  -PythonPath C:\path\to\venv\Scripts\python.exe `
  -OutputDirectory C:\tmp\keeper-desktop-package
```

The result is `Keeper.dist`, containing `Keeper.exe`, the Qt runtime, the official Keeper icon, QML, and `keeper-package-manifest.json`. Every runtime file is hashed. Build-time Dependency Walker downloads are handled by Nuitka inside the disposable build cache selected by the script. No tool is installed machine-wide.

Verify the artifact through packaged diagnostics, deterministic mock workflow, Windows-platform rendered UI smoke, manifest validation, protected-content/secret/private-path scans, and the lifecycle tests. Generated build outputs are not committed.

The legacy `scripts/build-keeper.ps1` zipapp remains available for headless compatibility and recovery diagnostics; it is not the primary desktop product.

Per-user install, same-version repair, upgrade, one-generation rollback, status, and data-preserving uninstall are documented in [`DESKTOP_INSTALLATION.md`](DESKTOP_INSTALLATION.md). Publishing a tag or public release remains a separate Founder action.
