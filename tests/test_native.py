import unittest

try:
    import torch
except ImportError:
    torch = None

try:
    from omnijev.vision_env import ACTIONS, oracle_success
except ImportError:
    oracle_success = None

try:
    from omnijev.native import ParallelDecisionHead, delivery_of, expected_calibration_error, parse_letter
    from omnijev.rlcd import corrective_loss, group_relative_loss, proper_score_loss
    from omnijev.tasks import shuffle_options
except ImportError:
    ParallelDecisionHead = expected_calibration_error = parse_letter = None
    group_relative_loss = proper_score_loss = shuffle_options = None


@unittest.skipUnless(parse_letter is not None, 'torch is required')
class LetterAndCalibration(unittest.TestCase):
    def test_answer_line_beats_an_earlier_letter(self):
        self.assertEqual(parse_letter('Option A is tempting.\nAnswer: C', 4), 'C')

    def test_missing_letter_is_invalid(self):
        self.assertIsNone(parse_letter('no decision', 4))

    def test_a_close_call_is_held(self):
        self.assertEqual(delivery_of({'A': 0.42, 'B': 0.40, 'C': 0.18})['delivery'], 'hold')

    def test_a_separated_call_acts(self):
        decision = delivery_of({'A': 0.80, 'B': 0.12, 'C': 0.08}, margin=0.15)
        self.assertEqual(decision['delivery'], 'act')
        self.assertAlmostEqual(decision['margin'], 0.68)

    def test_perfect_bins_have_zero_error(self):
        measured = expected_calibration_error([0.0, 1.0], [False, True])
        self.assertAlmostEqual(measured['ece'], 0.0)

    def test_option_shuffle_is_stable_and_tracks_the_label(self):
        first, gold = shuffle_options('Color?', ['red', 'blue', 'green'], 0, 7)
        again, gold_again = shuffle_options('Color?', ['red', 'blue', 'green'], 0, 7)
        self.assertEqual(first, again)
        self.assertEqual(gold, gold_again)
        self.assertEqual(first[gold], 'red')


@unittest.skipUnless(oracle_success is not None, 'PIL is required')
class VisualTask(unittest.TestCase):
    def test_oracle_places_the_block_and_abstains_on_a_blank_frame(self):
        for seed in range(12):
            self.assertTrue(oracle_success(seed, blank=False, lie=False))
            self.assertTrue(oracle_success(seed, blank=False, lie=True))
            self.assertTrue(oracle_success(seed, blank=True))

    def test_action_menu_matches_the_oracle_vocabulary(self):
        self.assertIn('insufficient evidence', ACTIONS)
        self.assertEqual(len(ACTIONS), len(set(ACTIONS)))


@unittest.skipUnless(ParallelDecisionHead is not None, 'torch is required')
class DecisionObjective(unittest.TestCase):
    def test_masked_candidate_cannot_be_selected_and_loss_learns(self):
        torch.manual_seed(0)
        head = ParallelDecisionHead(16, proj=8, dropout=0.0)
        optimizer = torch.optim.Adam(head.parameters(), lr=1e-2)
        candidates = torch.randn(3, 16)
        before = None
        for _ in range(30):
            gold = torch.randint(0, 2, (8,))
            state = candidates[gold] + 0.05 * torch.randn(8, 16)
            encoded = candidates.unsqueeze(0).expand(8, -1, -1)
            mask = torch.tensor([[True, True, False]]).expand(8, -1)
            logits = head.logits_from_state(state, encoded, mask)
            self.assertTrue(torch.all(logits[:, 2] < -1e4))
            loss, _ = proper_score_loss(logits, gold, mask)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            before = float(loss.detach())
        self.assertLess(before, 0.5)

    def test_a_wrong_lead_costs_more_than_a_correct_one(self):
        mask = torch.ones(1, 3, dtype=torch.bool)
        wrong = corrective_loss(torch.tensor([[3.0, 0.0, 0.0]]), torch.tensor([1]), mask)[0]
        right = corrective_loss(torch.tensor([[0.0, 3.0, 0.0]]), torch.tensor([1]), mask)[0]
        self.assertGreater(float(wrong), float(right))

    def test_group_advantage_increases_the_better_action(self):
        log_probabilities = torch.tensor([0.0, -1.0], requires_grad=True)
        loss = group_relative_loss(log_probabilities, torch.tensor([1.0, 0.0]))
        loss.backward()
        self.assertLess(log_probabilities.grad[0], 0)
        self.assertGreater(log_probabilities.grad[1], 0)


if __name__ == '__main__':
    unittest.main()
