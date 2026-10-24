import sys, unittest
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from gitlab_client import GitLabClient

class JobTests(unittest.TestCase):
    def test_pipeline_filter_job_pages_and_play_endpoint(self):
        calls = []
        def handler(request):
            calls.append(request)
            if request.url.path.endswith('/pipelines'):
                self.assertEqual(request.url.params['ref'], 'proj3')
                return httpx.Response(200, json=[{'id': 7, 'ref': 'proj3', 'sha': 'sha'}])
            if request.method == 'POST':
                self.assertEqual(request.url.path, '/api/v4/projects/1/jobs/9/play')
                return httpx.Response(200, json={'id': 9, 'name': 'build', 'status': 'pending'})
            page = request.url.params['page']
            return httpx.Response(200, json=[{'id': 8 if page == '1' else 9, 'name': 'test' if page == '1' else 'build', 'status': 'manual'}], headers={'X-Next-Page': '2' if page == '1' else ''})
        client = GitLabClient.__new__(GitLabClient)
        client.client = httpx.Client(base_url='https://example.test/api/v4', transport=httpx.MockTransport(handler))
        self.addCleanup(client.close)
        self.assertEqual(client.list_pipelines(1, 'proj3')[0]['id'], 7)
        self.assertEqual([j['id'] for j in client.list_pipeline_jobs(1, 7)], [8, 9])
        self.assertEqual(client.play_job(1, 9)['status'], 'pending')
        self.assertEqual(sum(r.method == 'POST' for r in calls), 1)
