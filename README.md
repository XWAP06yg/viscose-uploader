# Viscose Benchmarks Uploader

This utility watches your local Kovaaks stats exports and pushes new personal bests to a Google Sheet. It was written to support the **Viscose Benchmarks** sheet but is configurable enough to work with future layout changes.

## Features
- Built-in CLI (`viscose`) provisions Google Cloud resources and writes the uploader config for you.
- Watches the Kovaaks stats folder and pushes new personal bests automatically for every scenario it discovers.
- Discovers sheet rows on the fly by matching scenario names and updating the first score column whose header matches common patterns (e.g. “High Score”, “Your Score”).
- Caches state (personal bests, processed files) locally so the sheet is only updated when you actually improve.

## Installation (Windows)
- Download the latest `Viscose-Setup.exe` from [GitHub Releases](https://github.com/XWAP06yg/viscose-uploader/releases/latest) and run it to install the CLI to `C:\Program Files\Viscose` and add it to your `PATH`.
- Install the [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) if you want the automated `gcloud`-driven workflow; otherwise run `viscose auth --manual`.

Open a new PowerShell or Command Prompt and run `viscose --help` to verify it’s on PATH.

## Setup

Run `viscose auth` to configure credentials and write `%USERPROFILE%\\.viscose_uploader`.

Two flows are supported:
- Automated (recommended): if `gcloud` is installed, the CLI drives the Google Cloud SDK to sign in, create/reuse a project, enable APIs, create a service account, and save a JSON key. You only need to share your Google Sheet with the printed service-account email.
- Manual fallback: if `gcloud` is not available (or you launch with `viscose auth --manual`), you can paste the path to an existing service-account JSON key; the CLI copies it into your app data directory and finishes config.

## Getting Started

1. **Install with the Windows installer**.
2. **Run `viscose auth`** to set up credentials and write `%USERPROFILE%\\.viscose_uploader\config.json`.
3. **Review `%USERPROFILE%\\.viscose_uploader\config.json`**. Edit it manually to add more scenarios or tweak paths/columns as desired.
4. **Share the Google Sheet** with the service-account email so it has edit rights.

## Updating

- Run `viscose update` at any time to check the latest GitHub release, download the Windows installer, and launch it.
- The CLI checks for new releases on launch and lets you know when an update is available.
- The CLI closes automatically after launching the installer so the update can replace the executable.
- If you prefer to download manually, visit the [GitHub Releases](https://github.com/XWAP06yg/viscose-uploader/releases) page and grab the newest `Viscose-Setup.exe`.
- Using a private fork? Set the environment variable `VISCOSE_UPDATE_TOKEN` to a GitHub personal access token that can read the repository so the updater can access the API.

## Uploading Scores

### One-off upload
Use this when you just want to sync once (for example, after a practice session). The command rescans the entire `stats` directory and resynchronises any stale sheet cells:
```bash
viscose upload
```
### Continuous watch
Keep the CLI running while you play to push high scores as soon as Kovaaks writes the CSV:
```bash
viscose watch
```
This polls the stats folder every few seconds (tweakable via config). Cancel with `Ctrl+C`.

## How the Sheet Update Works
- Every time a new CSV is parsed, the tool searches each worksheet (or the ones you listed) for the scenario name and remembers the matching row.
- It looks for score columns whose header matches the phrases you provided (default: `High Score`, `Your Score`, `Score`, `PB`) and overwrites the cell in that column on the matching row.
- If the sheet layout changes, rerun `viscose auth` (or edit `%USERPROFILE%\\.viscose_uploader\config.json`) with new header keywords.

## State Management
- Personal-best tracking lives in `%USERPROFILE%\\.viscose_uploader\state.json`.
- The CLI remembers which CSV files were already processed (`processed_files`) so it won't spam the sheet when re-running.

## Troubleshooting
- **Missing modules**: Ensure the required Python packages are installed in the environment running the script.
- **Sheet row not found**: Confirm the scenario name in the CSV is present somewhere in the worksheet tab. Names must match exactly, including spaces and casing.
- **Score header not detected**: Add a new header phrase to the `score_headers` array in the config (e.g. `"Your PB"`) so the uploader knows which column to update.
- **Service account lacks access**: Confirm the email in `service_account_email` inside the config has edit permission on the Google Sheet.
- **Different stats directory per user**: Each player should run `viscose auth` locally and provide their own stats path.

## Extending
The config file is ordinary JSON. You can edit it manually to:
- Add or reorder `score_headers` so the uploader knows which columns hold your personal bests.
- Set `worksheet_filter` to limit the search to specific tabs.
- Adjust `poll_interval`, `stats_root`, or other paths without rerunning the wizard.

Enjoy automating your Viscose Benchmarks uploads!

## Building the binary (maintainers only)

Developers can reproduce the standalone binary using [PyInstaller](https://pyinstaller.org/):

```bash
py -m pip install -r requirements-build.txt
pyinstaller packaging/viscose.spec
```

The generated executable appears under `dist/viscose/viscose.exe`. Bundle the contents of that folder when publishing a release.
- Update the version in both `pyproject.toml` and `viscose/version.py` as part of each release.
- Build the installer with Inno Setup (`iscc packaging/viscose.iss`) and upload the resulting `Viscose-Setup.exe` to GitHub releases so the updater can fetch it.
