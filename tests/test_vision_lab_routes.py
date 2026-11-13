import unittest
from unittest.mock import patch
import app as atelier_app

class VisionLabRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = atelier_app.app.test_client()
        self.old_key = atelier_app.OPENROUTER_API_KEY
        atelier_app.OPENROUTER_API_KEY = 'test-key'
    def tearDown(self):
        atelier_app.OPENROUTER_API_KEY = self.old_key
    def test_rejects_non_object_payload(self):
        response = self.client.post('/vision-lab/generate', data='[]', content_type='application/json')
        self.assertEqual(response.status_code, 400)
    def test_rejects_image_references_before_job_creation(self):
        with patch.object(atelier_app, 'new_job') as new_job:
            response = self.client.post('/vision-lab/generate', json={'references':[{'role':'look'}]})
        self.assertEqual(response.status_code, 400)
        self.assertIn('text-only', response.get_json()['error'])
        new_job.assert_not_called()
    def test_rejects_unsupported_model(self):
        response = self.client.post('/vision-lab/generate', json={'instructions':'A portrait', 'target_model_id':'unknown/model'})
        self.assertEqual(response.status_code, 400)
    def test_rejects_unsupported_output_language(self):
        with patch.object(atelier_app, "new_job") as new_job:
            response = self.client.post("/vision-lab/generate", json={"language":"French","instructions":"A portrait"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("language must be", response.get_json()["error"])
        new_job.assert_not_called()
    def test_valid_payload_creates_job(self):
        with patch.object(atelier_app, 'new_job', return_value='vl-job') as new_job, patch.object(atelier_app, 'job_access_token', return_value='test-token'), patch.object(atelier_app, 'WorkerThread') as thread:
            response = self.client.post('/vision-lab/generate', json={'mode':'advanced','instructions':'Keep the blue coat.','selections':{'outfit_styling':{'description':'Blue coat'}},'language':'Hindi'})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json(), {'job_id':'vl-job', 'access_token':'test-token'})
        new_job.assert_called_once_with('vision_lab', 'advanced')
        self.assertEqual(thread.call_args.kwargs['args'][1]['language'], 'Hindi')
        self.assertEqual(thread.call_args.kwargs['args'][2], atelier_app.MODEL)
        self.assertEqual(thread.call_args.kwargs['args'][3], '')
    def test_validate_flags_changed_protected_instruction(self):
        response = self.client.post('/vision-lab/validate', json={'prompt':'A detailed cinematic portrait with natural light and rich texture.', 'instructions':'Keep the red jacket.'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['instruction_integrity'], 'review_required')
        self.assertFalse(response.get_json()['quality']['passed'])
    def test_validate_rejects_oversized_prompt(self):
        response = self.client.post('/vision-lab/validate', json={'prompt':'x' * 20001})
        self.assertEqual(response.status_code, 400)
    def test_repair_rejects_invalid_payload(self):
        response = self.client.post('/vision-lab/repair', json={'prompt':' '})
        self.assertEqual(response.status_code, 400)
    def test_repair_returns_proposal_without_mutating_original(self):
        expected={'status':'review_required','original_prompt':'Original','repaired_prompt':'Repaired','original_quality':{'score':70},'repaired_quality':{'score':90},'provider_model':'mock/model','user_decision_required':True}
        with patch.object(atelier_app, 'propose_prompt_repair', return_value=expected) as repair:
            response = self.client.post('/vision-lab/repair', json={'prompt':'Original','instructions':'Keep blue','target_model_id':'midjourney'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['original_prompt'], 'Original')
        repair.assert_called_once()
        self.assertEqual(repair.call_args.kwargs['target_model_id'], 'midjourney')

if __name__ == '__main__':
    unittest.main()