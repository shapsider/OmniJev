import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from report_public_benchmark import conservative_paired_interval, quantile, budget_forced, semantic_choice


class PublicReportTests(unittest.TestCase):
    def pairs(self, n, left=True, right=True):
        return [(dict(correct=left, image_sha256=str(i)), dict(correct=right)) for i in range(n)]

    def test_zero_disagreements_still_has_uncertainty(self):
        low,high=conservative_paired_interval(self.pairs(300))
        self.assertLess(low,0)
        self.assertGreater(high,0)
        self.assertLess(high,2)
        self.assertAlmostEqual(-low,high)

    def test_tiny_sample_cannot_prove_noninferiority(self):
        low,high=conservative_paired_interval(self.pairs(1))
        self.assertLess(low,-90)
        self.assertGreater(high,90)

    def test_direction_and_repeated_images(self):
        low,high=conservative_paired_interval(self.pairs(100,True,False))
        self.assertGreater(low,90)
        self.assertEqual(high,100)
        pair=self.pairs(1)
        self.assertIsNone(conservative_paired_interval(pair+pair))

    def test_latency_quantile(self):
        self.assertEqual(quantile([1,2,3,4],.5),2.5)

    def test_budget_marker_requires_backend_token_evidence(self):
        r={'response':{'choices':[{'message':{'reasoning_content':'I have to answer now.'}}]},
           'usage':{'completion_tokens_details':{'reasoning_tokens':20}}}
        self.assertFalse(budget_forced(r))
        r['usage']['completion_tokens_details']['reasoning_tokens']=8198
        self.assertTrue(budget_forced(r))
        r['response']['choices'][0]['message']['reasoning_content']=None
        self.assertFalse(budget_forced(r))
        self.assertFalse(budget_forced({'error':'transport failure'}))

    def test_final_answer_normalization_does_not_mine_reasoning(self):
        r={'method':'reasoning','raw_text':'First A or B could work.\nThe correct option is D.\n\nD'}
        self.assertEqual(semantic_choice(r,list('ABCD')),'D')
        for bad in ('A and B','D is not correct','No final answer','Answer: E'):
            r['raw_text']=bad
            self.assertIsNone(semantic_choice(r,list('ABCD')))
        r={'raw_text':'','response':{'choices':[{'message':{'reasoning_content':'D'}}]}}
        self.assertIsNone(semantic_choice(r,list('ABCD')))


if __name__=='__main__':
    unittest.main()
