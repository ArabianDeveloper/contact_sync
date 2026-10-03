"""In-memory fakes of the Google People and Chat clients (for tests)."""
from types import SimpleNamespace


class Request:
    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


def page(items, token, size):
    start = int(token) if token else 0
    chunk = items[start:start + size]
    nxt = start + size
    return chunk, (str(nxt) if nxt < len(items) else None)


class FakePeople:
    def __init__(self, page_size=2):
        self.groups = []            # dicts like Google's contactGroups
        self.connections = []       # dicts like Google's Person
        self.calls = []
        self.page_size = page_size
        self.errors = {}            # operation -> exception (raised when executed)
        self.modify_response = {}
        self._counter = 0

    def _maybe_fail(self, op, *args):
        error = self.errors.get(op)
        if callable(error):
            error = error(*args)
        if error is not None:
            raise error

    def contactGroups(self):
        def list_(pageSize=None, pageToken=None):
            self.calls.append(("groups.list", pageToken))

            def run():
                self._maybe_fail("groups.list")
                chunk, nxt = page(self.groups, pageToken, self.page_size)
                out = {"contactGroups": chunk}
                if nxt:
                    out["nextPageToken"] = nxt
                return out
            return Request(run)

        def create(body):
            def run():
                self._maybe_fail("groups.create", body)
                self._counter += 1
                group = {"resourceName": f"contactGroups/new{self._counter}",
                         "name": body["contactGroup"]["name"], "groupType": "USER_CONTACT_GROUP"}
                self.groups.append(group)
                self.calls.append(("groups.create", body))
                return group
            return Request(run)

        def modify(resourceName, body):
            def run():
                self.calls.append(("members.modify", resourceName, body))
                self._maybe_fail("members.modify", resourceName, body)
                return self.modify_response
            return Request(run)

        return SimpleNamespace(list=list_, create=create, members=lambda: SimpleNamespace(modify=modify))

    def people(self):
        def connections_list(resourceName, personFields, pageSize=None, pageToken=None):
            self.calls.append(("connections.list", resourceName, personFields))

            def run():
                self._maybe_fail("connections.list")
                chunk, nxt = page(self.connections, pageToken, self.page_size)
                out = {"connections": chunk}
                if nxt:
                    out["nextPageToken"] = nxt
                return out
            return Request(run)

        def create_contact(body):
            def run():
                self._maybe_fail("createContact", body)
                self._counter += 1
                self.calls.append(("createContact", body))
                return {"resourceName": f"people/c{self._counter}"}
            return Request(run)

        return SimpleNamespace(createContact=create_contact,
                               connections=lambda: SimpleNamespace(list=connections_list))


class FakeChat:
    def __init__(self, page_size=2):
        self.spaces_data = []
        self.calls = []
        self.page_size = page_size
        self.errors = {}
        self._counter = 0

    def _maybe_fail(self, op, *args):
        error = self.errors.get(op)
        if callable(error):
            error = error(*args)
        if error is not None:
            raise error

    def spaces(self):
        def list_(pageSize=None, pageToken=None):
            def run():
                self._maybe_fail("spaces.list")
                chunk, nxt = page(self.spaces_data, pageToken, self.page_size)
                out = {"spaces": chunk}
                if nxt:
                    out["nextPageToken"] = nxt
                return out
            return Request(run)

        def create(body):
            def run():
                self._maybe_fail("spaces.create", body)
                self._counter += 1
                self.calls.append(("spaces.create", body))
                space = {"name": f"spaces/NEW{self._counter}", "displayName": body["displayName"],
                         "spaceType": "SPACE"}
                self.spaces_data.append(space)
                return space
            return Request(run)

        def members_create(parent, body):
            def run():
                self._maybe_fail("members.create", parent, body)
                self.calls.append(("members.create", parent, body))
                return {"name": f"{parent}/members/1"}
            return Request(run)

        return SimpleNamespace(list=list_, create=create,
                               members=lambda: SimpleNamespace(create=members_create))


class FakeSheets:
    """In-memory Google Sheets client. `tabs` is {tab title: rows}."""

    def __init__(self, tabs):
        self.tabs = tabs
        self.calls = []
        self.errors = {}

    def _maybe_fail(self, op):
        if op in self.errors:
            raise self.errors[op]

    def spreadsheets(self):
        def get(spreadsheetId, fields=None):
            def run():
                self._maybe_fail("get")
                self.calls.append(("get", spreadsheetId))
                return {"sheets": [{"properties": {"title": t}} for t in self.tabs]}
            return Request(run)

        def values_get(spreadsheetId, range, valueRenderOption=None):
            def run():
                self._maybe_fail("values.get")
                self.calls.append(("values.get", spreadsheetId, range, valueRenderOption))
                title = range.split("!")[0].strip("'").replace("''", "'")
                return {"values": self.tabs[title]}
            return Request(run)

        return SimpleNamespace(get=get, values=lambda: SimpleNamespace(get=values_get))
