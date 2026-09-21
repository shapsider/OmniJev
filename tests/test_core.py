import unittest
from omnijev.core import candidate_scores


class ProbabilityIntegrity(unittest.TestCase):
    def test_missing_option_does_not_get_zero_probability(self):
        r=candidate_scores({'content':[{'token':'A','logprob':-0.1,'top_logprobs':[]}]},['A','B'])
        self.assertEqual(r['status'],'incomplete_top_k')
        self.assertIsNone(r['probabilities'])

    def test_never_use_a_later_token(self):
        r=candidate_scores({'content':[{'token':'The'},{'token':'A','logprob':0}]},['A','B'])
        self.assertEqual(r['status'],'answer_not_at_first_position')

    def test_complete_candidates_normalized_but_not_calibrated(self):
        r=candidate_scores({'content':[{'token':'A','logprob':-1,'top_logprobs':[{'token':'B','logprob':-2}]}]},['A','B'])
        self.assertAlmostEqual(sum(r['probabilities'].values()),1)
        self.assertFalse(r['calibrated'])

    def test_whitespace_variant_is_not_merged_into_canonical_token(self):
        r=candidate_scores({'content':[{'token':'A','logprob':-1,'top_logprobs':[
            {'token':' A','logprob':-3},{'token':'B','logprob':-2}]}]},['A','B'])
        self.assertAlmostEqual(r['probabilities']['A'],0.7310585786300049)

    def test_backend_rounding_does_not_produce_mass_above_one(self):
        r=candidate_scores({'content':[{'token':'A','logprob':0,'top_logprobs':[
            {'token':'B','logprob':-18}]}]},['A','B'])
        self.assertEqual(r['candidate_mass'],1.0)


if __name__=='__main__':unittest.main()
