import sys, unittest
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gitlab_client import GitLabClient

class TagTests(unittest.TestCase):
    def client(self, handler):
        client = GitLabClient.__new__(GitLabClient)
        client.client = httpx.Client(base_url='https://example.test/api/v4', transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        return client

    def test_pagination_and_numeric_order(self):
        def handler(request):
            page = request.url.params['page']
            names = ['v9', 'v2', 'v1.9', 'v100-rc', 'v0'] if page == '1' else ['v10', 'proj25']
            return httpx.Response(200, json=[{'name': n, 'target': 'sha'} for n in names], headers={'X-Next-Page': '2' if page == '1' else ''})
        client = self.client(handler)
        self.assertEqual(client.get_next_tag(1, 'v'), {'latest_tag': 'v10', 'next_tag': 'v11'})
        self.assertEqual(client.get_next_tag(1, 'proj'), {'latest_tag': 'proj25', 'next_tag': 'proj26'})

    def test_no_matching_tags(self):
        client = self.client(lambda request: httpx.Response(200, json=[{'name': 'release', 'target': 'sha'}]))
        self.assertEqual(client.get_next_tag(1, 'v')['next_tag'], 'v1')
        self.assertEqual(client.get_next_tag(1, 'proj')['next_tag'], 'proj1')
        with self.assertRaises(ValueError):
            client.get_next_tag(1, 'other')

    def test_error_is_not_treated_as_empty_repository(self):
        client = self.client(lambda request: httpx.Response(403))
        with self.assertRaises(httpx.HTTPStatusError):
            client.get_next_tag(1, 'v')

if __name__ == '__main__':
    unittest.main()
