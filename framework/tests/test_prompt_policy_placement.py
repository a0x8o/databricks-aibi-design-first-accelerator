"""Preserve v2's master/instructions/guardrails/validation/runbook separation."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
PROMPTS=ROOT/'framework/agent_skills/v2/prompts'

class PolicyPlacementTests(unittest.TestCase):
    def test_data_policy_lives_in_own_guardrails(self):
        guard=(PROMPTS/'data_layer/guardrails.md').read_text()
        instructions=(PROMPTS/'data_layer/instructions.md').read_text()
        validation=(PROMPTS/'data_layer/validation.md').read_text()
        for policy in ('DL-G1','DL-G2','DL-G3'):
            self.assertIn(policy,guard)
            self.assertIn(policy,instructions)
            self.assertIn(policy,validation)
        self.assertIn('parent_pk: member_id',guard)
        self.assertNotIn('parent_pk: member_id',instructions)
    def test_shared_rules_do_not_own_data_spec(self):
        shared=(PROMPTS/'shared/global_guardrails.md').read_text()
        self.assertNotIn('parent_pk: member_id',shared)
        self.assertIn('### Explicit workspace file and notebook transport',shared)
        self.assertIn('### Selection persistence and completion acknowledgement',shared)
        self.assertEqual(shared.count('## G-19:'),1)
    def test_app_system_prompt_references_policies_instead_of_embedding_them(self):
        source=(ROOT/'app/llm/agent_loop.py').read_text()
        system=source.split('if context_vars.get("STEP_NAME") == "master":',1)[1].split('        parts = [',1)[0]
        self.assertIn("active stage's own guardrails.md",system)
        self.assertNotIn('phase_id=run_selected',system)
    def test_failure_diagnostics_remain_failure_only(self):
        master=(PROMPTS/'00_master_prompt.md').read_text()
        self.assertIn('A failure runbook is not a startup input',master)
        runbook=(PROMPTS/'data_layer/runbook.md').read_text()
        self.assertIn('GENERATED_IDENTIFIER_ERROR',runbook)
        self.assertIn('KeyError parent_pk',runbook)

if __name__=='__main__': unittest.main()
