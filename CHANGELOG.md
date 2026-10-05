# Changelog

All notable changes to Contact Sync are written here, newest first.
The version number is in `app/config.py`. When you release a new version, add a section for it
(see [RELEASING.md](RELEASING.md)) and copy it into the notes of the GitHub release.

Format: `## [version] - date`, then the groups *Added*, *Changed*, *Fixed*, *Removed*.

## [1.0.0] - Not released yet

First version.

### Added
- Reads contacts from CSV, TSV, XLSX, XLS, ODS, JSON and Google Sheets. The type, the encoding and the delimiter are detected automatically.
- Header row selection, a preview of the first 100 rows, and a Google Sheet tab and range selection.
- Column mapping chosen by the user, with several columns for the name, suggestions from English and Arabic headers, and saved mapping profiles.
- Cleaning of phones (Arabic digits, hidden characters, international format, default country Oman +968) and of English names. Names with Arabic letters are never changed.
- Validation report: rows without a valid name, phone, email and label are not imported and are listed with the reason.
- Merging of duplicate rows in the file (the last row is kept and the labels are combined).
- Adding contacts to Google Contacts without creating existing contacts again (matched by phone), with labels created when missing.
- Adding people to Google Chat spaces with the same names as the labels, with spaces created when missing, and a choice when several spaces have the same name.
- Two settings to turn the creation of labels and of spaces on or off.
- Import with a progress bar, a live log, a cancel button, and a results summary (created, existing, added, failed, reported, not processed).
- Google sign-in, a setup check (credentials, permissions, APIs), and deleting the token to use another account.
- Dark theme, update check from GitHub, a Windows program (`.exe`) and installer.
