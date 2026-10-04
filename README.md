# Contact Sync

A Windows desktop application that reads contacts from a data file or a Google Sheet, adds them
to **Google Contacts** with labels taken from the data, and adds them to **Google Chat spaces**
that have the same names as the labels.

Repository: https://github.com/ArabianDeveloper/contact_sync

## What it does

For every valid row of your data:

1. It checks whether a contact with the same **phone number** already exists in Google Contacts.
   If it does, the contact is not created again.
2. It creates the contact (name, phone, email) if it does not exist.
3. It adds the contact to each **label** listed in the row (and creates the label if it does not exist).
4. It adds the person (by **email**) to the **Google Chat space** with the same name as each label
   (and creates the space if it does not exist).

Every label is therefore both a contact label and a Chat space, with the same name.

## Features (version 1)

- **Many sources:** CSV, TSV, XLSX, XLS, ODS, JSON, and Google Sheets (link or ID, with tab and range).
  The file type is detected automatically from the content.
- **Encoding and delimiter detection** for CSV (UTF-8, UTF-8 with BOM, Windows-1256 for Arabic; comma,
  semicolon, tab, pipe).
- **Header row selection** for files with a title above the header, and a **preview** of the first 100 rows.
- **Column mapping** chosen by you: the name can be built from any number of columns in the order you
  choose. The mapping is suggested from the header names (English and Arabic) and **saved as a profile**
  for the next file with the same headers.
- **Cleaning:** Arabic and Indic digits are converted to Latin digits, hidden characters are removed,
  phone numbers are normalized to the international format (default country: Oman, +968), and English
  names can be trimmed, cleaned of extra spaces and capitalized. **Names that contain Arabic letters are never changed.**
- **Validation report:** every row that cannot be imported is listed with the reason.
- **Duplicates inside the file** (same phone) are merged: the last row is kept and the labels of all the
  rows are combined.
- **Existing contacts** are found by normalized phone, so `99123456` and `+968 9912 3456` are the same contact.
  An existing contact is never modified, except that it is added to the labels and spaces of the new file.
- **Auto-create** labels and spaces, each with its own on/off setting (on by default).
- **Spaces with the same name:** the program asks which one to use (or to skip it).
- **Progress bar, live log and a Cancel button.** A results summary lists what was created, what already
  existed, what failed, what was reported, and which rows were not processed.
- **Google account tools:** sign in, setup check (credentials file, permissions, and the three APIs),
  and delete the token to use another account.
- **Update check:** on start the program tells you if a newer release exists on GitHub.
- **Dark theme.** The interface is in English; Arabic data (names, labels) is fully supported.

## What a row needs to be imported

A row is imported only if it has **all four** of these, and each one is valid:

| Field | Rule |
|---|---|
| Name | Not empty after joining the selected name columns |
| Phone | Present and a valid phone number (after normalization) |
| Email | Present and in a valid email format |
| Labels | At least one label (labels are separated by a comma) |

Rows that fail are **not imported** and are listed in the validation report with the reason
(for example "Missing phone; Invalid email"). Empty items in the labels column (`Team1,,Team2`) are ignored.
Only the comma `,` separates labels.

## Requirements

- Windows (the interface is built for Windows; the code itself is Python)
- Python 3.10 or newer
- A **Google Workspace** account
- A Google Cloud project with the **People API**, **Google Chat API** and **Google Sheets API** enabled
  (Sheets is needed only if you load Google Sheets)
- An OAuth client of type **Desktop app** (its `credentials.json` file)

## Setting up Google

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create a project (or use an existing one).
2. In **APIs & Services > Library**, enable: **People API**, **Google Chat API**, **Google Sheets API**.
3. Configure the **OAuth consent screen**. For a Workspace organization you can choose **Internal**.
4. In **APIs & Services > Credentials**, create an **OAuth client ID** of type **Desktop app** and
   download its JSON file. This is your `credentials.json`.
5. In the program, open **Settings**, choose the `credentials.json` file, and click **Sign in**.
   A browser window opens: sign in with your Workspace account and **allow every permission**.
   The setup check then shows if anything is missing.

The permissions the program asks for: Google Contacts, Google Sheets (read only), Google Chat spaces
(read and create) and Google Chat memberships.

> **Never share or commit `credentials.json` or `token.json`.** The `.gitignore` of this repository excludes them.

## Install and run

```
pip install -r requirements.txt
python main.py
```

`python main.py --info` prints where the program stores its files.

## Using the program

1. **Source:** choose a file, or paste a Google Sheet link or ID and click *Load Google Sheet*.
   Pick the sheet/tab and the header row if needed.
2. **Mapping:** choose the column for the name (add several columns and order them), phone, email and labels.
   Check the sample at the bottom. The cleanup options for English names are here too.
3. **Validation:** read the report. Rejected rows are not imported.
4. **Import:** check the numbers and press *Start import*, then confirm. The first time, a browser window
   asks you to sign in. If several spaces have the same name, you choose which one to use.
5. **Results:** see the counts and the tables *Failed*, *Reported* and *Not processed*.
   *New import* starts again.

**Tip:** for your first import, use a small file with 2 or 3 test rows (test names, a test label, an email
on your domain) and run it twice. The second run must not create anything again.

### Settings

| Setting | Meaning |
|---|---|
| credentials.json | The OAuth client file of your Google Cloud project |
| Create a contact label when it does not exist | On by default. When off, a missing label is reported and not created |
| Create a Google Chat space when it does not exist | On by default. When off, a missing space is reported and not created |
| Delete token | Removes the saved sign-in, to sign in with another account |

When an auto-create setting is off and a label or space is missing, it is **reported**, and the contact is still
created and added to the other labels and spaces.

### Where the program stores its files

In `%APPDATA%\ContactSync\`:

| File | Content |
|---|---|
| `settings.json` | Your settings (credentials path, toggles, name cleanup options) |
| `mapping_profiles.json` | Saved column mappings |
| `token.json` | The Google sign-in |
| `logs\contact_sync.log` | Log file (rotating, 1 MB per file, 5 files). It does not contain names, phone numbers or emails |

## Limits and good to know

- **Chat lists only the spaces you belong to.** A space that exists without you in it is not found, and the
  program would create a new space with the same name (if auto-create is on).
- **No automatic retry.** If Google's rate limits are reached during a large import, the affected items are listed as
  *failed*. Import the remaining rows again later; contacts already created are recognized by phone.
- **Failed items and reports cannot be exported** in this version; they are shown in the window only.
- **All your contacts are loaded once at the start of each import** to find existing contacts by phone.
  For a very large address book this adds a waiting time at the start.
- **Google Workspace only.** Personal Gmail accounts have limits on the Chat API.
- Adding a person to a space can fail (for example an email outside your organization). That item is listed as failed
  and the import continues.
- An import stops completely only for problems that affect everything: the sign-in is not valid, a permission is missing,
  an API is disabled, or 5 network failures in a row.

## Building the Windows program and the installer

On Windows:

1. Install Python 3.10 or newer and [Inno Setup](https://jrsoftware.org/isinfo.php) 6.3 or newer (for the installer).
2. Install the libraries: `pip install -r requirements-build.txt`
3. Run `python build_exe.py`

Results:

| Path | What |
|---|---|
| `dist\ContactSync\ContactSync.exe` | The program folder (copy the whole `ContactSync` folder to run it anywhere) |
| `dist\installer\ContactSync-Setup-<version>.exe` | The installer (Program Files, Start menu shortcut, optional desktop shortcut, uninstaller) |

`python build_exe.py --no-installer` builds only the program folder. If Inno Setup is not found, the installer step is skipped
with a message (or set the `ISCC` environment variable to the path of `ISCC.exe`).

The uninstaller does **not** delete your data in `%APPDATA%\ContactSync` (settings, saved mappings, Google sign-in, logs).
An unexpected error is written to the log file and shown in a message box, because the `.exe` has no console window.

### Publishing a new version

1. Change `VERSION` in `app/config.py` (for example `1.0.1`) and run `python build_exe.py`.
2. On GitHub, create a release with the tag `v1.0.1` and attach `ContactSync-Setup-1.0.1.exe`.
3. Programs that are already installed show the update banner the next time they start.

## Updates

On start the program checks the latest release of this repository. If a newer version exists, a banner offers to open
the download page. Nothing is downloaded or installed automatically. Releases must be tagged like `v1.2.0`, and the
repository must be public.

## Command line tools

These tools help to test each part on your real data. The ones marked "creates data" change your Google account
(after a confirmation).

| Tool | Use |
|---|---|
| `python inspect_file.py "file.xlsx"` | Shows how a file is read (type, headers, rows). Options: `--sheet`, `--header-row`, `--rows` |
| `python validate_file.py "file.csv"` | Suggests the mapping, validates, and shows rejected rows and duplicates |
| `python google_check.py login --credentials "path\credentials.json"` | Signs in and runs the setup check. Other commands: `status`, `check`, `delete-token` |
| `python google_try.py labels` / `contacts` / `spaces` | Reads your labels, contacts or spaces |
| `python google_try.py add --name ... --phone ... --email ... --labels "A,B"` | Imports one person (creates data) |
| `python run_import.py "file.csv" --limit 3` | Runs a full import from a file (creates data). Ctrl+C cancels after the current row |

## Tests

```
pip install -r requirements-dev.txt
python -m unittest discover -s tests -t .
```

The tests use in-memory fakes of the Google services, so they never touch your account.
The sample files used by the tests are in `tests/sample_files`.

## Project structure

```
main.py                     starts the window
build_exe.py, contact_sync.spec, installer/, assets/     build the .exe and the installer, and the icon
inspect_file.py, validate_file.py, google_check.py, google_try.py, run_import.py   command line tools
requirements.txt, requirements-dev.txt, requirements-build.txt
app/
  config.py                 constants (version, repository, Google permissions)
  paths.py, settings.py, logging_setup.py     files in AppData, settings, log
  update_check.py           the update check
  resources.py, crash.py    files inside the .exe, and unexpected-error handling
  core/                     the logic (no window, no Google)
    readers/                file detection and readers (CSV, Excel, ODS, JSON, Google Sheet)
    cleaning.py             phone, name, email and label cleanup
    validation.py, dedupe.py, pipeline.py       validation, duplicate rows, the steps in order
    header_suggest.py, profiles.py              column suggestion and saved mappings
    models.py, errors.py
  services/                 Google code: sign-in, Contacts, Chat, Sheets, errors, setup check
  runner/import_runner.py   the import job (progress, cancel, error handling, summary)
  ui/                       the window: state, pages, dialogs, theme, background workers
tests/                      automatic tests and sample files
```

## Status

Written, with automatic tests: the whole program described above, the update check, and the build files for the `.exe` and
the installer (`contact_sync.spec`, `installer/contact_sync.iss`, `build_exe.py`).
Still to do: build the `.exe` and the installer on a Windows machine and check them there, and the final test with real data.

## License

No license has been chosen yet.
