# Releasing a new version

A release is: change the version, build the installer, publish it on GitHub. Programs that are already installed
check the latest GitHub release when they start, and show a banner if its tag is a higher version than theirs.

## 1. Choose the version number

`major.minor.patch`, for example `1.0.1`:

| Change | Example |
|---|---|
| Bug fix only | `1.0.0` to `1.0.1` |
| New feature, nothing breaks | `1.0.1` to `1.1.0` |
| Big change | `1.1.0` to `2.0.0` |

It must be **higher** than the version already installed, or the update banner will not appear.

## 2. Prepare

1. Set the version in **one place**: `VERSION = "1.0.1"` in `app/config.py`. The `.exe` file properties, the installer file name
   and the update check all use it.
2. Add a section to `CHANGELOG.md`: `## [1.0.1] - 2026-10-20`, with what was Added, Changed or Fixed.
   (A test fails if the changelog has no section for the current version.)
3. Run the tests: `python -m unittest discover -s tests -t .` must end with `OK`.
4. Do the parts of [TESTING.md](TESTING.md) that your changes could affect. For a release that changes anything about Google,
   repeat Parts E and F (a small import, then the same import again).

## 3. Build

On Windows, with Inno Setup 6.3 or newer installed:

```
pip install -r requirements-build.txt
python build_exe.py
```

Results:

- `dist\ContactSync\ContactSync.exe`
- `dist\installer\ContactSync-Setup-1.0.1.exe` (the file to publish)

Install this installer on your own computer and check that the program starts and imports a small test file.
Do not publish a file that you did not run.

## 4. Save the code on GitHub

Make sure that `credentials.json` and `token.json` are **not** in the commit (the `.gitignore` excludes them; check with `git status`).

```
git add .
git commit -m "Version 1.0.1"
git push
```

## 5. Create the release

On GitHub: your repository, **Releases**, **Draft a new release**.

1. **Tag:** `v1.0.1` (create it on the latest commit of the main branch). The tag must be the version with a `v` in front.
2. **Title:** `Contact Sync 1.0.1`
3. **Notes:** copy the section of this version from `CHANGELOG.md`.
4. **Files:** attach `dist\installer\ContactSync-Setup-1.0.1.exe`.
5. Keep **Set as the latest release** selected, leave **Pre-release** and **Draft** off, and press **Publish release**.

Or with the GitHub command line tool:

```
gh release create v1.0.1 dist\installer\ContactSync-Setup-1.0.1.exe --title "Contact Sync 1.0.1" --notes-file notes.md
```

(`notes.md` is a file that contains the notes.)

## 6. Check that the update reaches the users

1. Start an **older** installed version of the program. The banner "A new version is available: 1.0.1" must appear.
2. Click the banner button. The release page must open.
3. Download and run the installer. It installs over the old version (the `AppId` in `installer/contact_sync.iss` is the same), and the
   settings, saved mappings and Google sign-in in `%APPDATA%\ContactSync` are kept.

## Good to know

- **First release:** if the first release is tagged `v1.0.0` and the code is `1.0.0`, no banner appears, because the versions
  are equal. The banner appears only when the tag is higher than the installed version.
- **The repository must be public.** For a private repository the update check finds nothing.
- **Drafts and pre-releases are ignored** by the update check (it reads only the latest published release).
- **A wrong release:** delete the release and its tag on GitHub (**Releases**, open the release, **Delete**; then
  **Tags** and delete the tag), fix the problem, and publish again. If users already downloaded it, publish a new higher
  version instead (`1.0.2`); do not reuse a version number that users may already have.
- **Windows warning:** the installer is not code-signed, so Windows can show "Windows protected your PC". Users choose
  **More info**, then **Run anyway**. Removing the warning needs a paid code-signing certificate.
- **Never change the `AppId`** in `installer/contact_sync.iss`. Windows uses it to recognize the same program when a new version is installed.
- **Antivirus:** if an antivirus program blocks the installer, report it as a false positive to the antivirus vendor. The one-folder
  build is used because it is blocked less often than a single-file `.exe`.

## Quick checklist

- [ ] `VERSION` changed in `app/config.py`
- [ ] Section added to `CHANGELOG.md`
- [ ] Tests pass
- [ ] `python build_exe.py` done, and the installer was installed and tried
- [ ] No secrets in the commit, code pushed
- [ ] GitHub release `v<version>` published with the installer attached
- [ ] The update banner appeared in an older version
