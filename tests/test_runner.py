import unittest

from app.core.errors import ContactSyncError
from app.core.models import CleanRow
from app.runner.import_runner import ImportRunner, RunCancelled, RunOptions
from app.services.chat import ChatService, DuplicateSpaceError
from app.services.contacts import ContactsService
from tests.fake_services import FakeChat, FakePeople
from tests.fakes import FakeHttpError, patch_fake_libraries


def make_row(n, labels=("Team1",), name=None):
    return CleanRow(row_number=n, name=name or f"Person {n}", phone=f"+9689912{n:04d}",
                    email=f"u{n}@x.com", labels=list(labels))


def group(name, resource):
    return {"name": name, "resourceName": resource, "groupType": "USER_CONTACT_GROUP"}


def space(name, display):
    return {"name": name, "displayName": display, "spaceType": "SPACE"}


class RunnerBase(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch_fake_libraries().stop)
        self.people = FakePeople(page_size=100)
        self.chat = FakeChat(page_size=100)
        self.contacts = ContactsService(self.people)
        self.chat_service = ChatService(self.chat)
        self.progress = []
        self.logs = []

    def runner(self, **options):
        return ImportRunner(
            self.contacts, self.chat_service, RunOptions(**options),
            on_progress=lambda done, total: self.progress.append((done, total)),
            on_log=lambda level, text: self.logs.append((level, text)),
        )

    def run_all(self, rows, **options):
        runner = self.runner(**options)
        self.assertEqual(runner.prepare(rows), [])
        return runner, runner.run(rows)

    def calls(self, name):
        return [c for c in self.people.calls + self.chat.calls if c[0] == name]


class HappyPathTests(RunnerBase):
    def test_counts_and_calls(self):
        self.people.groups = [group("Team1", "contactGroups/t1")]
        self.people.connections = [{
            "resourceName": "people/old",
            "phoneNumbers": [{"value": "+96899120002"}],
            "memberships": [{"contactGroupMembership": {"contactGroupResourceName": "contactGroups/t1"}}],
        }]
        self.chat.spaces_data = [space("spaces/1", "Team1")]
        rows = [make_row(2, ["Team1", "Team2"], name="Ahmed"), make_row(3, ["Team1"], name="محمد")]
        # row 2 -> phone +96899120002 (exists, already in Team1); row 3 is new

        _, summary = self.run_all(rows)

        self.assertEqual(summary.total_rows, 2)
        self.assertEqual(summary.processed_rows, 2)
        self.assertEqual((summary.contacts_existing, summary.contacts_created), (1, 1))
        self.assertEqual(summary.already_in_labels, 1)          # row 2 in Team1
        self.assertEqual(summary.added_to_labels, 2)            # row 2 in Team2, row 3 in Team1
        self.assertEqual(summary.labels_created, 1)             # Team2
        self.assertEqual(summary.spaces_created, 1)             # Team2
        self.assertEqual(summary.added_to_spaces, 3)
        self.assertEqual(summary.failed_count, 0)
        self.assertEqual(summary.reported, [])
        self.assertFalse(summary.cancelled or summary.stopped)
        self.assertEqual(self.progress, [(1, 2), (2, 2)])
        self.assertEqual(len(self.calls("createContact")), 1)
        self.assertEqual(len(self.calls("groups.create")), 1)
        self.assertEqual(len(self.calls("spaces.create")), 1)
        self.assertTrue(any("محمد" in text for _, text in self.logs))     # live log shows names

    def test_run_requires_prepare(self):
        with self.assertRaises(RuntimeError):
            self.runner().run([make_row(2)])


class ToggleTests(RunnerBase):
    def test_missing_label_and_space_are_reported_but_the_contact_is_still_added_elsewhere(self):
        self.people.groups = [group("Team1", "contactGroups/t1")]
        self.chat.spaces_data = [space("spaces/1", "Team1")]
        rows = [make_row(2, ["Team1", "Team2"]), make_row(3, ["Team2"])]

        _, summary = self.run_all(rows, create_labels=False, create_spaces=False)

        self.assertEqual(summary.contacts_created, 2)
        self.assertEqual(summary.added_to_labels, 1)
        self.assertEqual(summary.added_to_spaces, 1)
        self.assertEqual(self.calls("groups.create") + self.calls("spaces.create"), [])
        grouped = summary.reported_by_target()
        self.assertIn(("label", "Team2", [2, 3]), grouped)
        self.assertIn(("space", "Team2", [2, 3]), grouped)
        self.assertEqual(summary.failed_count, 0)


class FailureTests(RunnerBase):
    def setUp(self):
        super().setUp()
        self.people.groups = [group("Team1", "contactGroups/t1")]
        self.chat.spaces_data = [space("spaces/1", "Team1")]

    def test_contact_failure_skips_that_row_only(self):
        self.people.errors["createContact"] = lambda body: FakeHttpError(500) if "Person 2" in body["names"][0]["givenName"] else None
        _, summary = self.run_all([make_row(2), make_row(3)])
        self.assertEqual(summary.contacts_created, 1)
        self.assertEqual(summary.processed_rows, 2)
        self.assertEqual([(f.row_number, f.step, f.error_kind) for f in summary.failed], [(2, "contact", "server")])
        self.assertEqual(summary.added_to_spaces, 1)             # row 3 went through
        self.assertEqual(len(self.calls("members.create")), 1)   # row 2 never reached the space step

    def test_membership_failure_is_listed_and_the_run_continues(self):
        self.chat.errors["members.create"] = lambda parent, body: (
            FakeHttpError(403, {"error": {"status": "PERMISSION_DENIED", "message": "outside"}})
            if body["member"]["name"] == "users/u2@x.com" else None)
        _, summary = self.run_all([make_row(2), make_row(3)])
        self.assertEqual(summary.failed_count, 1)
        self.assertEqual((summary.failed[0].row_number, summary.failed[0].step, summary.failed[0].target),
                         (2, "space", "Team1"))
        self.assertEqual(summary.failed[0].error_kind, "permission")
        self.assertEqual(summary.added_to_spaces, 1)
        self.assertEqual(summary.added_to_labels, 2)             # the label step of row 2 still worked
        self.assertFalse(summary.stopped)

    def test_quota_error_is_a_failure_without_retry(self):
        self.people.errors["members.modify"] = lambda *a: FakeHttpError(429)
        _, summary = self.run_all([make_row(2)])
        self.assertEqual(summary.failed[0].error_kind, "quota")
        self.assertEqual(len(self.calls("members.modify")), 1)
        self.assertEqual(summary.added_to_spaces, 1)             # the space step is independent

    def test_fatal_error_stops_the_run(self):
        self.chat.errors["members.create"] = lambda parent, body: (
            FakeHttpError(401) if body["member"]["name"] == "users/u3@x.com" else None)
        rows = [make_row(n) for n in (2, 3, 4, 5)]
        _, summary = self.run_all(rows)
        self.assertTrue(summary.stopped)
        self.assertIn("sign in", summary.stopped_reason.lower())
        self.assertEqual(summary.processed_rows, 2)
        self.assertEqual(summary.not_processed, [4, 5])
        self.assertEqual(summary.failed[0].row_number, 3)

    def test_disabled_api_stops_the_run(self):
        disabled = FakeHttpError(403, {"error": {"message": "x", "details": [
            {"reason": "SERVICE_DISABLED", "metadata": {"service": "chat.googleapis.com"}}]}})
        self.chat.errors["members.create"] = lambda parent, body: disabled
        _, summary = self.run_all([make_row(2), make_row(3)])
        self.assertTrue(summary.stopped)
        self.assertIn("Google Chat API is not enabled", summary.stopped_reason)
        self.assertEqual(summary.not_processed, [3])


class NetworkTests(RunnerBase):
    def setUp(self):
        super().setUp()
        self.people.groups = [group("Team1", "contactGroups/t1")]
        self.chat.spaces_data = [space("spaces/1", "Team1")]

    def fail_rows(self, numbers):
        """The network fails when the contact of these rows is created."""
        wanted = {f"Person {n}" for n in numbers}
        self.people.errors["createContact"] = lambda body: (
            ConnectionError("offline") if body["names"][0]["givenName"] in wanted else None)

    def test_stops_after_five_network_failures_in_a_row(self):
        self.fail_rows(range(2, 8))
        _, summary = self.run_all([make_row(n) for n in range(2, 12)])
        self.assertTrue(summary.stopped)
        self.assertIn("5 network failures", summary.stopped_reason)
        self.assertEqual(summary.processed_rows, 5)
        self.assertEqual(summary.not_processed, [7, 8, 9, 10, 11])

    def test_a_success_resets_the_counter(self):
        self.fail_rows([2, 3, 4, 5, 7, 8, 9, 10])        # 4 failures, one success (row 6), 4 failures
        _, summary = self.run_all([make_row(n) for n in range(2, 12)])
        self.assertFalse(summary.stopped)
        self.assertEqual(summary.processed_rows, 10)
        self.assertEqual(summary.failed_count, 8)


class CancelTests(RunnerBase):
    def test_cancel_finishes_the_current_row(self):
        self.people.groups = [group("Team1", "contactGroups/t1")]
        self.chat.spaces_data = [space("spaces/1", "Team1")]
        rows = [make_row(n) for n in range(2, 7)]
        runner = self.runner()
        runner.prepare(rows)
        runner._on_progress = lambda done, total: runner.cancel() if done == 2 else None
        summary = runner.run(rows)
        self.assertTrue(summary.cancelled)
        self.assertEqual(summary.processed_rows, 2)
        self.assertEqual(summary.not_processed, [4, 5, 6])
        self.assertEqual(summary.contacts_created, 2)

    def test_cancel_before_start(self):
        runner = self.runner()
        runner.cancel()
        with self.assertRaises(RunCancelled):
            runner.prepare([make_row(2)])


class PrepareTests(RunnerBase):
    def test_google_error_while_loading_is_readable(self):
        self.people.errors["connections.list"] = lambda *a: FakeHttpError(401)
        with self.assertRaises(ContactSyncError) as ctx:
            self.runner().prepare([make_row(2)])
        self.assertIn("contacts", str(ctx.exception))
        self.assertIn("Sign in", str(ctx.exception))

    def test_duplicate_spaces_must_be_chosen_before_run(self):
        self.people.groups = [group("Team1", "contactGroups/t1")]
        self.chat.spaces_data = [space("spaces/1", "Team1"), space("spaces/2", "team1"), space("spaces/3", "Team2")]
        rows = [make_row(2, ["Team1", "Team2"])]
        runner = self.runner()
        unresolved = runner.prepare(rows)
        self.assertEqual([label for label, _ in unresolved], ["Team1"])
        with self.assertRaises(DuplicateSpaceError):
            runner.run(rows)

        self.chat_service.choose("Team1", "spaces/2")
        self.assertEqual(self.chat_service.unresolved_duplicates(["Team1"]), [])
        summary = runner.run(rows)
        self.assertEqual(summary.added_to_spaces, 2)
        self.assertEqual(self.calls("members.create")[0][1], "spaces/2")      # the chosen space
        self.assertEqual(self.calls("spaces.create"), [])                    # nothing was created

    def test_skipping_a_duplicate_space_is_reported(self):
        self.people.groups = [group("Team1", "contactGroups/t1")]
        self.chat.spaces_data = [space("spaces/1", "Team1"), space("spaces/2", "Team1")]
        rows = [make_row(2)]
        runner = self.runner()
        runner.prepare(rows)
        self.chat_service.choose("Team1", None)
        summary = runner.run(rows)
        self.assertEqual(summary.added_to_spaces, 0)
        self.assertEqual(len(summary.reported), 1)
        self.assertIn("skipped by your choice", summary.reported[0].message)


class PrivacyTests(RunnerBase):
    def test_file_log_has_no_personal_data(self):
        import logging
        self.people.groups = [group("Team1", "contactGroups/t1")]
        self.chat.spaces_data = [space("spaces/1", "Team1")]
        self.chat.errors["members.create"] = lambda parent, body: FakeHttpError(
            403, {"error": {"message": "secret@outside.com is not allowed", "status": "PERMISSION_DENIED"}})
        with self.assertLogs("contact_sync", level=logging.DEBUG) as captured:
            self.run_all([make_row(2, name="Sensitive Name")])
        text = "\n".join(captured.output)
        for secret in ("Sensitive Name", "u2@x.com", "secret@outside.com", "+96899120002"):
            self.assertNotIn(secret, text)


if __name__ == "__main__":
    unittest.main()
