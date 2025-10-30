Windows installer packaging
===========================

This repo contains an Inno Setup script that builds a Windows installer for the Viscose CLI.

What it does
- Installs `viscose.exe` into `C:\Program Files\Viscose`.
- Appends the install directory to the system `PATH` so you can run `viscose` from any terminal.
- Adds Start Menu and optional desktop shortcuts.

Prerequisites
- Build the CLI executable with PyInstaller
  - `py -m pip install -r requirements-build.txt`
  - `pyinstaller packaging/viscose.spec`

Build the installer
- Install Inno Setup (https://jrsoftware.org/isinfo.php) and ensure `iscc` is on PATH.
- Run: `iscc packaging/viscose.iss`
- The installer `Viscose-Setup.exe` will be placed under `dist/`.

End-user guidance
- Run `Viscose-Setup.exe` as administrator.
- Install the Google Cloud SDK separately if you want the automated `viscose auth` flow:
  - https://cloud.google.com/sdk/docs/install
  - Once installed, the CLI will detect `gcloud` automatically.
- Without the SDK you can run the manual setup at any time via:
  - `viscose auth --manual`
- After install, open a new PowerShell/terminal and run:
  - `viscose auth` to set up credentials.
  - `viscose watch` or `viscose upload` for normal operation.
- Future releases can be installed by running `viscose update`, which downloads the latest installer from GitHub (`https://github.com/XWAP06yg/viscose-uploader/releases`).
- If you keep the repository private, provide a GitHub personal access token via the `VISCOSE_UPDATE_TOKEN` environment variable so the updater can authenticate.

Notes
- The CLI falls back to the manual service-account key workflow when `gcloud` is not installed.
- Feel free to extend the installer script if you want to offer optional SDK downloads in future releases.
