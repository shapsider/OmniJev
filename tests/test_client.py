import unittest
from unittest.mock import patch
from omnijev import OmniJev, Policy
from omnijev.server import validate_http_request

OPTIONS=[{'id':'move','description':'Proceed'},{'id':'unknown','description':'Insufficient evidence','abstain':True}]


def response(choice='A', scores=True):
    return dict(valid=choice is not None,choice=choice,raw_text=choice or '',usage={},scores={
        'status':'complete_candidate_set' if scores else 'incomplete_top_k',
        'probabilities':{'A':.8,'B':.2} if scores else None,'margin':.6,'candidate_mass':.9})


class ClientContracts(unittest.TestCase):
    @patch('omnijev.client.decide',return_value=response())
    def test_stable_action_not_letter(self, backend):
        r=OmniJev().decide('Go?',OPTIONS)
        self.assertEqual(r['action'],'move');self.assertEqual(r['scores']['move'],.8)

    @patch('omnijev.client.decide',return_value=response('B'))
    def test_unknown_cannot_be_executed(self, backend):
        r=OmniJev().decide('Go?',OPTIONS)
        self.assertEqual(r['status'],'abstained');self.assertIsNone(r['action'])

    @patch('omnijev.client.decide',return_value=response(scores=False))
    def test_missing_scores_fail_closed_when_gate_requested(self, backend):
        r=OmniJev().decide('Go?',OPTIONS,policy=Policy(min_margin=.1))
        self.assertEqual(r['reason'],'scores_unavailable');self.assertIsNone(r['action'])

    @patch('omnijev.client.decide',return_value=response())
    def test_stale_result_cannot_be_executed(self, backend):
        with patch('omnijev.client.time.perf_counter',side_effect=[10,12]):
            r=OmniJev().decide('Go?',OPTIONS,policy=Policy(max_latency_ms=500))
        self.assertEqual(r['status'],'stale');self.assertIsNone(r['action'])

    @patch('omnijev.client.decide',return_value=response(None))
    def test_invalid_output_cannot_be_executed(self, backend):
        r=OmniJev().decide('Go?',OPTIONS)
        self.assertEqual(r['status'],'invalid');self.assertIsNone(r['action'])

    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):OmniJev().decide('Go?',[OPTIONS[0],OPTIONS[0]])

    def test_http_cannot_read_local_files(self):
        with self.assertRaises(ValueError):validate_http_request({'images':['/etc/passwd']})

    def test_invalid_policy_rejected(self):
        with self.assertRaises(ValueError):Policy(min_margin=float('nan'))
        with self.assertRaises(ValueError):Policy(max_latency_ms=-1)


if __name__=='__main__':unittest.main()
