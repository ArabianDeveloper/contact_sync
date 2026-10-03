import unittest

from app.core.errors import ContactSyncError
from app.services.contacts import ADDED, ALREADY, ContactInfo, ContactsService
from tests.fake_services import FakePeople
from tests.fakes import FakeHttpError, patch_fake_libraries


def group(name, resource, kind="USER_CONTACT_GROUP"):
    return {"name": name, "resourceName": resource, "groupType": kind}


def person(resource, phones=(), groups=()):
    return {
        "resourceName": resource,
        "phoneNumbers": [p if isinstance(p, dict) else {"value": p} for p in phones],
        "memberships": [{"contactGroupMembership": {"contactGroupResourceName": g}} for g in groups]
        + [{"domainMembership": {"inViewerDomain": True}}],
    }


class Base(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch_fake_libraries().stop)
        self.people = FakePeople(page_size=2)
        self.service = ContactsService(self.people)


class LabelTests(Base):
    def test_load_labels_pages_and_ignores_system_groups(self):
        self.people.groups = [
            group("myContacts", "contactGroups/myContacts", "SYSTEM_CONTACT_GROUP"),
            group("Team1", "contactGroups/t1"),
            group("الفريق الأول", "contactGroups/ar"),
            group("Friends", "contactGroups/friends", "SYSTEM_CONTACT_GROUP"),
            group("Team2", "contactGroups/t2"),
        ]
        self.assertEqual(self.service.load_labels(), 3)          # 3 pages were read
        self.assertEqual(self.service.ensure_label(" team1 ", create=False).resource_name, "contactGroups/t1")
        self.assertEqual(self.service.ensure_label("الفريق الأول", create=False).resource_name, "contactGroups/ar")
        self.assertIsNone(self.service.ensure_label("Friends", create=False))   # system group is not a user label

    def test_missing_label_is_created_or_reported(self):
        self.service.load_labels()
        self.assertIsNone(self.service.ensure_label("New", create=False))
        ref = self.service.ensure_label("  New ", create=True)
        self.assertTrue(ref.created)
        self.assertEqual(self.people.groups[-1]["name"], "New")   # trimmed
        again = self.service.ensure_label("new", create=True)      # found in memory, no second creation
        self.assertFalse(again.created)
        self.assertEqual(again.resource_name, ref.resource_name)
        self.assertEqual(len([c for c in self.people.calls if c[0] == "groups.create"]), 1)

    def test_label_created_meanwhile(self):
        self.service.load_labels()
        self.people.groups.append(group("Late", "contactGroups/late"))
        self.people.errors["groups.create"] = FakeHttpError(409, {"error": {"status": "ALREADY_EXISTS"}})
        ref = self.service.ensure_label("Late", create=True)
        self.assertEqual((ref.resource_name, ref.created), ("contactGroups/late", False))

    def test_other_errors_are_raised(self):
        self.service.load_labels()
        self.people.errors["groups.create"] = FakeHttpError(500)
        with self.assertRaises(FakeHttpError):
            self.service.ensure_label("X", create=True)

    def test_add_to_label(self):
        contact = ContactInfo("people/c1")
        self.assertEqual(self.service.add_to_label(contact, "contactGroups/t1"), ADDED)
        self.assertEqual(self.service.add_to_label(contact, "contactGroups/t1"), ALREADY)   # no second request
        modify_calls = [c for c in self.people.calls if c[0] == "members.modify"]
        self.assertEqual(len(modify_calls), 1)
        self.assertEqual(modify_calls[0][2], {"resourceNamesToAdd": ["people/c1"]})

    def test_contact_not_found_by_google(self):
        self.people.modify_response = {"notFoundResourceNames": ["people/c1"]}
        with self.assertRaises(ContactSyncError):
            self.service.add_to_label(ContactInfo("people/c1"), "contactGroups/t1")


class ContactTests(Base):
    def test_load_contacts_matches_phones_in_any_format(self):
        self.people.connections = [
            person("people/c1", ["99123456"], ["contactGroups/t1"]),
            person("people/c2", ["+968 9912 3457", {"value": "weird", "canonicalForm": "+96899123458"}]),
            person("people/c3", []),                                  # no phone
            person("people/c4", ["abc"]),                             # invalid phone
            person("people/c5", ["+96899123456"]),                    # same phone as c1: the first wins
        ]
        progress = []
        self.assertEqual(self.service.load_contacts(progress.append), 5)
        self.assertEqual(progress, [2, 4, 5])
        self.assertEqual(self.service.find("+96899123456").resource_name, "people/c1")
        self.assertEqual(self.service.find("+96899123456").groups, {"contactGroups/t1"})   # other membership types ignored
        self.assertEqual(self.service.find("+96899123457").resource_name, "people/c2")
        self.assertEqual(self.service.find("+96899123458").resource_name, "people/c2")
        self.assertIsNone(self.service.find("+96899999999"))
        self.assertEqual(self.people.calls[0], ("connections.list", "people/me", "phoneNumbers,memberships"))

    def test_create_contact(self):
        info = self.service.create_contact("محمد سالم العلوي", "+96899123457", "m@example.com")
        self.assertEqual(info.resource_name, "people/c1")
        body = self.people.calls[-1][1]
        self.assertEqual(body["names"], [{"givenName": "محمد سالم العلوي"}])
        self.assertEqual(body["phoneNumbers"], [{"value": "+96899123457"}])
        self.assertEqual(body["emailAddresses"], [{"value": "m@example.com"}])
        self.assertIs(self.service.find("+96899123457"), info)       # a later duplicate in the same run is found

    def test_create_contact_error_is_raised(self):
        self.people.errors["createContact"] = FakeHttpError(500)
        with self.assertRaises(FakeHttpError):
            self.service.create_contact("A", "+96899123456", "a@x.com")
        self.assertIsNone(self.service.find("+96899123456"))


if __name__ == "__main__":
    unittest.main()
