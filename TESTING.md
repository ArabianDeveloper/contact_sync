# Testing Contact Sync with real data (acceptance checklist)

The automatic tests use fake versions of Google, so they cannot tell if the program works with **your** Google account,
**your** Workspace settings and **your** real files. This checklist does. Do the parts in order and write down
anything that does not match the "Expected" column.

> **Important:** the program has no undo. Everything in Parts D to H creates real contacts, labels and Chat spaces.
> Use the test names in this file (they start with `ZZ-`) and delete them afterwards (Part K).

## Part A: automatic tests

```
pip install -r requirements-dev.txt
python -m unittest discover -s tests -t .
```

Expected: `OK` and **no skipped tests**. A skipped test means a library is missing (`python-calamine` for the XLSX test).

## Part B: reading files

Run `python inspect_file.py "<file>"` on each file and compare. The files are in `tests/sample_files`.

| File | Expected |
|---|---|
| `acceptance_contacts.csv` | Type CSV, encoding utf-8-sig, 18 rows, header row 1, Arabic names are readable |
| `acceptance_contacts_cp1256.csv` | Type CSV, an Arabic Windows encoding (cp1256), Arabic text readable (not `?` or strange letters) |
| `acceptance_arabic_headers.xlsx` | Type XLSX, header row **3** (the title row is skipped), Arabic headers readable, the phone of the first row is `99123456` (not `99123456.0`) |
| `contacts.xls`, `contacts.ods`, `contacts_objects.json`, `contacts.tsv` | The right type is detected and the rows are the same as in the other files |
| **Your own real file** | Same checks. Also try it with a wrong extension (rename `.xlsx` to `.csv`): the type must still be detected |

## Part C: validation

Run `python validate_file.py tests\sample_files\acceptance_contacts.csv`.

Expected: **17 rows, 9 valid, 7 rejected, 1 duplicate removed, 9 distinct labels**, and:

| Row | What it tests | Expected |
|---|---|---|
| 2 | Same phone as row 7 | Removed as a duplicate of row 7 |
| 3 | Arabic name, Arabic digits in the phone | Valid, phone `+96898123456`, name unchanged |
| 4 | `sara` / `khan` in lowercase | Valid, name `Sara Khan` |
| 5 | `00968` prefix, `JOHN SMITH`, label repeated | Valid, `John Smith`, labels `Team3, Team4` |
| 6 | Brackets and a dash in the phone, an empty label item | Valid, phone `+96872123456`, labels `Team1, Team2` |
| 7 | Duplicate of row 2 | Valid, labels merged: `Team1, Team2, Team5` |
| 8 to 13, 18 | Missing or invalid phone, email, labels, name | Rejected, each with the right reason |
| 14 | Hidden direction characters in the phone | Valid, phone `+96899123470` |
| 15 | Name with Arabic and English | Valid, name left untouched |
| 16 | Arabic labels | Valid, two labels |
| 17 | Arabic comma `،` inside a label | Valid, **one** label (only the normal comma separates labels) |

Also run it on your own file and check that the rejected rows really are wrong, and that no good row is rejected.

## Part D: Google setup

1. `python main.py`, open **Settings**, choose your `credentials.json`. Expected: a green "valid (Desktop app)" message.
   A Web application or service account file must give a red message.
2. Click **Sign in**. A browser opens: sign in with your Workspace account and allow every permission.
   Expected: the **Setup check** dialog shows everything `OK`.
3. Disable one of the APIs in Google Cloud and click **Run setup check**. Expected: `FAILED` with a message and a link. Enable it again.
4. In the sign-in page, allow only some permissions (if Google lets you). Expected: the check says which permissions are missing.
5. Click **Delete token**, confirm, and sign in again with another account if you have one.

## Part E: the first real import (small and safe)

1. Copy `tests/sample_files/real_test_template.csv` and replace `YOUR_TEST_USER_1@yourdomain.com` and
   `YOUR_TEST_USER_2@yourdomain.com` with two real test users of **your** Workspace domain.
2. Open the program, choose the file, go to the validation step.
   Expected: 4 rows, 3 valid, 0 rejected, 1 duplicate removed. The row of `Test Alpha` has the labels
   `ZZ-Test-A, ZZ-Test-B, ZZ-Test-C`.
3. Start the import and confirm. Expected:
   - Contacts created: **3**. Labels created: `ZZ-Test-A`, `ZZ-Test-B`, `ZZ-Test-C`, `ZZ-اختبار`. Spaces created: the same 4 names.
   - Open Google Contacts and Google Chat: the contacts, the labels and the spaces exist, **Arabic names are displayed correctly**,
     and the two test users are in the right spaces.
   - Results show 0 failed.

## Part F: running it again (nothing may be created twice)

Import the same file again. Expected: **0 contacts created, 3 already existing**, 0 labels and 0 spaces created, 0 failed.
"Already in a label" and "already in a space" count the existing memberships.

## Part G: problems that must be reported, not hidden

| Test | Expected |
|---|---|
| Use an email outside your organization in a new row with a new label | That row's space step is listed under **Failed** with a reason; the contact and label steps still worked; the import continues |
| Turn **both** auto-create settings off and import a row with a new label `ZZ-New` | Under **Reported**: label `ZZ-New` and space `ZZ-New`. The contact is still created and added to the other labels and spaces |
| Create two Chat spaces with the same name by hand and import a row with that label | A dialog asks which space to use (or to skip). The choice is respected |
| Disconnect the internet during an import | After 5 network failures in a row the import stops, and the results list the rows not processed. A banner explains it |
| Press **Cancel import** during a larger file (30 or more rows) | It stops after the current row. The rest is listed as not processed. Starting again continues without duplicates |
| Delete the token while the Settings page is open, then start an import | The program asks you to sign in again |

## Part H: Google Sheet

Put the acceptance data in a Google Sheet (or use your own). Paste the link on the Source page.
Expected: the tabs are listed, the preview is correct, a range such as `A1:F10` limits the rows, and the row numbers
in the validation report match the row numbers in the sheet.

## Part I: the window

- It opens fully on your screen and every page is usable (mapping and settings pages scroll if the screen is small).
- Try Windows display scaling 100%, 125% and 150%.
- Arabic text in tables, in the log and in the dialogs is shaped and readable.
- Next buttons are disabled until the step is complete. The sidebar does not allow other pages while an import runs.
- Closing the window during an import asks first.
- Close and open the program: the settings and the saved mapping are still there. The second file with the same headers
  shows "Mapping loaded from a saved profile".

## Part J: the packaged program

1. `python build_exe.py` (needs Inno Setup for the installer).
2. Run `dist\ContactSync\ContactSync.exe` **on a computer without Python** if you can (or at least not from your project folder).
   Repeat Part B (XLSX, XLS, ODS), Part D and Part E. The features that most often fail only in the `.exe` are:
   reading Excel files, phone validation, and Google Sheet loading.
3. Install with `dist\installer\ContactSync-Setup-<version>.exe`, start it from the Start menu, uninstall it. Expected:
   the data in `%APPDATA%\ContactSync` is still there after the uninstall.
4. Create a GitHub release with a higher version tag and check that the update banner appears.

## Part K: cleaning up the test data

There is no undo, so delete by hand:

- In Google Contacts: delete the contacts `Test Alpha`, `Test Beta`, `اختبار تجريبي`, and the labels starting with `ZZ-`.
- In Google Chat: delete (or leave) the spaces starting with `ZZ-`.

## If something goes wrong: what to send me

1. **What you did**, step by step, and **what you expected** compared with what happened.
2. The **screenshot** or the **error text** (copy it, do not retype it).
3. The log file: `%APPDATA%\ContactSync\logs\contact_sync.log` (it has no names, phones or emails).
4. For a file problem: the output of `python inspect_file.py "<file>"` (hide personal data first), or a small file that shows the problem
   with fake data.
5. Your Windows version, your display scaling, and whether you used `python main.py` or the `.exe`.
