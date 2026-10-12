import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import setup_gitlab_template as setup  # noqa: E402

BASE_URL = "https://gitlab.test"
API = f"{BASE_URL}/api/v4"


class Response:
    def __init__(self, data):
        self.data = data
        self.ok = True
        self.text = "body"
        self.headers = {}

    def json(self):
        return self.data


class FakeGitLab:
    """Session factice : enregistre les appels et refuse ce que GitLab refuse."""

    def __init__(self, labels=(), milestones=(), branches=(), tags=()):
        self.calls = []
        self.labels = list(labels)
        self.milestones = list(milestones)
        self.branches = list(branches)
        self.tags = list(tags)

    def get(self, url, params=None):
        self.calls.append(("GET", url))
        if url.endswith("/milestones"):
            # GitLab répond 400 si les deux paramètres arrivent ensemble.
            sent = {key for key in ("include_ancestors", "include_parent_milestones") if key in (params or {})}
            expected = {"include_ancestors"} if "/groups/" in url else {"include_parent_milestones"}
            assert sent == expected, (url, sent)
            return Response(self.milestones)
        if url.endswith("/labels"):
            return Response(self.labels)
        if url.endswith("/protected_branches"):
            return Response(self.branches)
        if url.endswith("/protected_tags"):
            return Response(self.tags)
        raise AssertionError(f"GET inattendu : {url}")

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs.get("json")))
        return Response({})

    def writes(self):
        return [call for call in self.calls if call[0] != "GET"]


def levels(*access_levels):
    return [{"access_level": level} for level in access_levels]


class QuietTestCase(unittest.TestCase):
    def setUp(self):
        # Les labels portent des emojis que la console Windows (cp1252) ne sait pas afficher.
        stdout = contextlib.redirect_stdout(io.StringIO())
        stdout.__enter__()
        self.addCleanup(stdout.__exit__, None, None, None)


class LabelsAndMilestoneTest(QuietTestCase):
    def test_creates_everything_on_the_given_scope(self):
        expected = len(setup.LABELS_DPT) + len(setup.LABELS_W)
        for scope in ("/projects/9", "/groups/5"):
            with self.subTest(scope=scope):
                gitlab = FakeGitLab()
                setup.ensure_labels(gitlab, BASE_URL, scope)
                setup.ensure_backlog_milestone(gitlab, BASE_URL, scope)

                posts = [call for call in gitlab.writes() if call[0] == "POST"]
                self.assertEqual(len(posts), expected + 1)
                self.assertTrue(all(call[1].startswith(f"{API}{scope}/") for call in posts))

    def test_rerun_writes_nothing_when_up_to_date(self):
        labels = [{"name": title, "description": description, "id": 1}
                  for title, _color, description, *_ in setup.LABELS_DPT + setup.LABELS_W]
        for scope in ("/projects/9", "/groups/5"):
            with self.subTest(scope=scope):
                gitlab = FakeGitLab(labels=labels, milestones=[{"title": "Backlog"}])
                setup.ensure_labels(gitlab, BASE_URL, scope)
                setup.ensure_backlog_milestone(gitlab, BASE_URL, scope)
                self.assertEqual(gitlab.writes(), [])

    def test_outdated_description_is_updated_except_on_inherited_labels(self):
        gitlab = FakeGitLab(labels=[
            {"name": "[W] \U0001F4CC To Do", "description": "old", "id": 7, "is_project_label": True},
            {"name": "[P] \U0001F7E0 P2 · High", "description": "old", "id": 8, "is_project_label": False},
        ])
        setup.ensure_labels(gitlab, BASE_URL, "/projects/9")

        puts = [call[:2] for call in gitlab.writes() if call[0] == "PUT"]
        self.assertEqual(puts, [("PUT", f"{API}/projects/9/labels/7")])


class ProtectionsTest(QuietTestCase):
    def conforming_branches(self):
        return [{"name": name, "push_access_levels": levels(0), "merge_access_levels": levels(40),
                 "allow_force_push": False} for name in setup.PROTECTED_BRANCHES]

    def test_protects_branches_and_tag_when_nothing_is_protected(self):
        gitlab = FakeGitLab()
        setup.ensure_protected_branches(gitlab, BASE_URL, 1)
        setup.ensure_protected_tags(gitlab, BASE_URL, 1)
        self.assertEqual([call[0] for call in gitlab.writes()], ["POST"] * 4)

    def test_rerun_writes_nothing_when_already_protected(self):
        gitlab = FakeGitLab(branches=self.conforming_branches(),
                            tags=[{"name": "v*", "create_access_levels": levels(40)}])
        setup.ensure_protected_branches(gitlab, BASE_URL, 1)
        setup.ensure_protected_tags(gitlab, BASE_URL, 1)
        self.assertEqual(gitlab.writes(), [])

    def test_looser_protections_are_recreated(self):
        branches = self.conforming_branches()
        branches[0] = {"name": "main", "push_access_levels": levels(40), "merge_access_levels": levels(40),
                       "allow_force_push": False}
        gitlab = FakeGitLab(branches=branches, tags=[{"name": "v*", "create_access_levels": levels(30)}])
        setup.ensure_protected_branches(gitlab, BASE_URL, 1)
        setup.ensure_protected_tags(gitlab, BASE_URL, 1)

        writes = [call[:2] for call in gitlab.writes()]
        self.assertEqual(writes, [
            ("DELETE", f"{API}/projects/1/protected_branches/main"),
            ("POST", f"{API}/projects/1/protected_branches"),
            ("DELETE", f"{API}/projects/1/protected_tags/v%2A"),
            ("POST", f"{API}/projects/1/protected_tags"),
        ])


if __name__ == "__main__":
    unittest.main()
