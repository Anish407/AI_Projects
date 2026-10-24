import sys, unittest
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gitlab_client import GitLabClient

class EnsureTagTests(unittest.TestCase):
    def check(self, existing=False, lost_response=False):
        posts = []
        reads = []
        def handler(request):
            path = request.url.path
            if path.endswith('/repository/tags') and request.method == 'GET':
                reads.append(request)
                tags = [{'name': 'v2', 'target': 'sha'}] if existing or (lost_response and posts) else []
                return httpx.Response(200, json=tags)
            if request.method == 'POST':
                self.assertEqual(path, '/api/v4/projects/87191376/repository/tags')
                self.assertEqual(request.url.params['tag_name'], 'v2')
                self.assertEqual(request.url.params['ref'], 'main')
                posts.append(request)
                if lost_response:
                    raise httpx.ReadTimeout('response lost', request=request)
                return httpx.Response(201, json={'name': 'v2', 'target': 'sha'})
            return httpx.Response(200, json={'id': 87191376, 'path_with_namespace': 'anish5416/myproj2'})
        client = GitLabClient.__new__(GitLabClient)
        client.client = httpx.Client(base_url='https://example.test/api/v4', transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        result = client.ensure_tag('anish5416/myproj2', 'v2')
        self.assertEqual(result['project_id'], 87191376)
        self.assertEqual(result['name'], 'v2')
        self.assertEqual(result['created'], not existing and not lost_response)
        self.assertEqual(len(posts), 0 if existing else 1)

    def test_reuses_existing_without_post(self):
        self.check(existing=True)

    def test_creates_missing_tag_in_correct_project(self):
        self.check()

    def test_recovers_lost_response_without_duplicate_post(self):
        self.check(lost_response=True)

class PrepareReleaseTests(unittest.TestCase):
    def test_named_tag_bypasses_numbering(self):
        from unittest.mock import Mock
        client = GitLabClient.__new__(GitLabClient)
        client.ensure_tag = Mock(return_value={"project_id": 8, "name": "v2"})
        client.get_next_tag = Mock()
        self.assertEqual(client.prepare_release("anish5416/myproj2", "proj", "v2")["name"], "v2")
        client.get_next_tag.assert_not_called()
        client.ensure_tag.assert_called_once_with("anish5416/myproj2", "v2", "main")

    def test_auto_tag_resolves_id_and_numbers(self):
        from unittest.mock import Mock
        client = GitLabClient.__new__(GitLabClient)
        client.client = httpx.Client(base_url="https://example.test/api/v4", transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"id": 8, "path_with_namespace": "anish5416/myproj2"})))
        self.addCleanup(client.close)
        client.get_next_tag = Mock(return_value={"latest_tag": "proj9", "next_tag": "proj10"})
        client.ensure_tag = Mock(return_value={"project_id": 8, "name": "proj10"})
        result = client.prepare_release("anish5416/myproj2", "proj")
        self.assertEqual(result["previous_tag"], "proj9")
        client.get_next_tag.assert_called_once_with(8, "proj")
        client.ensure_tag.assert_called_once_with("anish5416/myproj2", "proj10", "main")
