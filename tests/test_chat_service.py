import unittest

from app.services.chat import ADDED, ALREADY, ChatService, DuplicateSpaceError
from tests.fake_services import FakeChat
from tests.fakes import FakeHttpError


def space(name, display, kind="SPACE", **extra):
    return {"name": name, "displayName": display, "spaceType": kind, **extra}


class Base(unittest.TestCase):
    def setUp(self):
        self.chat = FakeChat(page_size=2)
        self.service = ChatService(self.chat)


class SpaceTests(Base):
    def test_load_spaces_pages_and_skips_chats(self):
        self.chat.spaces_data = [
            space("spaces/1", "Team1"),
            space("spaces/2", "", "GROUP_CHAT"),
            space("spaces/3", "Direct", "DIRECT_MESSAGE"),
            space("spaces/4", "الفريق الأول"),
            space("spaces/5", "Team2"),
        ]
        self.assertEqual(self.service.load_spaces(), 3)
        self.assertEqual(self.service.ensure_space(" TEAM1 ", create=False).name, "spaces/1")
        self.assertEqual(self.service.ensure_space("الفريق الأول", create=False).name, "spaces/4")

    def test_missing_space_is_created_or_reported(self):
        self.service.load_spaces()
        self.assertIsNone(self.service.ensure_space("New", create=False))
        ref = self.service.ensure_space(" New ", create=True)
        self.assertTrue(ref.created)
        body = self.chat.calls[-1][1]
        self.assertEqual(body, {"spaceType": "SPACE", "displayName": "New"})     # no description
        again = self.service.ensure_space("new", create=True)
        self.assertEqual((again.name, again.created), (ref.name, False))
        self.assertEqual(len([c for c in self.chat.calls if c[0] == "spaces.create"]), 1)

    def test_duplicate_space_names(self):
        self.chat.spaces_data = [
            space("spaces/1", "Team1", createTime="2025-01-01",
                  membershipCount={"joinedDirectHumanUserCount": 5}),
            space("spaces/2", "team1"),
            space("spaces/3", "Team2"),
        ]
        self.service.load_spaces()
        duplicates = self.service.duplicate_names(["Team1", "TEAM1", "Team2", "Other"])
        self.assertEqual(len(duplicates), 1)                                      # each label once
        label, spaces = duplicates[0]
        self.assertEqual(label, "Team1")
        self.assertEqual([s.name for s in spaces], ["spaces/1", "spaces/2"])
        self.assertEqual(spaces[0].member_count, 5)
        self.assertEqual(spaces[0].create_time, "2025-01-01")

        with self.assertRaises(DuplicateSpaceError):
            self.service.ensure_space("Team1")

        self.service.choose("Team1", "spaces/2")
        self.assertEqual(self.service.ensure_space("TEAM1").name, "spaces/2")

        with self.assertRaises(ValueError):
            self.service.choose("Team1", "spaces/3")                              # not one of its spaces

    def test_skip_choice(self):
        self.chat.spaces_data = [space("spaces/1", "A"), space("spaces/2", "A")]
        self.service.load_spaces()
        self.service.choose("A", None)
        self.assertIsNone(self.service.ensure_space("A"))

    def test_errors_are_raised(self):
        self.service.load_spaces()
        self.chat.errors["spaces.create"] = FakeHttpError(403)
        with self.assertRaises(FakeHttpError):
            self.service.ensure_space("X", create=True)


class MemberTests(Base):
    def test_add_member(self):
        self.assertEqual(self.service.add_member("spaces/1", "a@x.com"), ADDED)
        call = self.chat.calls[-1]
        self.assertEqual(call[1], "spaces/1")
        self.assertEqual(call[2], {"member": {"name": "users/a@x.com", "type": "HUMAN"}})

    def test_already_a_member_is_not_a_failure(self):
        self.chat.errors["members.create"] = FakeHttpError(409, {"error": {"status": "ALREADY_EXISTS"}})
        self.assertEqual(self.service.add_member("spaces/1", "a@x.com"), ALREADY)

    def test_other_errors_are_raised(self):
        self.chat.errors["members.create"] = FakeHttpError(403, {"error": {"status": "PERMISSION_DENIED"}})
        with self.assertRaises(FakeHttpError):
            self.service.add_member("spaces/1", "outsider@other.com")


if __name__ == "__main__":
    unittest.main()
