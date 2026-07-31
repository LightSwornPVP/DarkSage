# Installation

## Requirements

- Windows 10 or later
- Python 3.12 or later with Tkinter
- Git

Clone the repository, create a virtual environment if desired, and run
`powershell -File scripts/keeper-desktop.ps1`. No provider is required for the mock
workflow. Build a portable `.pyz` with `scripts/build-keeper.ps1`.

Application data defaults to `%LOCALAPPDATA%\Keeper`. Uninstall by removing the
launcher/artifact; data is intentionally retained until the user explicitly removes
it. Back up or export the database before manual data removal.
