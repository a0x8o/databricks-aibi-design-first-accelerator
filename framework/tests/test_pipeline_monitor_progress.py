"""Exercise browser rendering against the reported stale-phase scenario."""
import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'Node required for browser logic test')
class MonitorProgressTests(unittest.TestCase):
    def test_server_status_is_preserved_and_tools_render_at_step_level(self):
        source = (Path(__file__).resolve().parents[2] / 'app/templates/pipeline_monitor.html').read_text()
        accordion = source.split('function renderAccordion(){', 1)[1].split('function renderPhaseDetail(', 1)[0]
        status = source.split('function updateStepStatus(order, status){', 1)[1].split('/* ─── Cancel / Resume', 1)[0]
        script = '''
const assert = require('node:assert/strict');
const panel = {innerHTML:''};
const document = {getElementById:()=>panel};
const STEPS = [{id:'config',status:'running'}, {id:'data',status:'pending'}];
const substeps = {data:[{phase_id:'parse_erd',name:'Parse ERD',status:'running'}]};
const stepRecentTools = {data:[{label:'Running Notebook',detail:'dbldatagen'}]};
const userAccordionState = {}, userPhaseDetailState = {};
const calls = [];
function buildStepToolSummary(){return '';}
function renderPhaseDetail(phase,tools){calls.push({phase,tools}); return 'detail';}
function renderCompletedPhaseDetail(){return '';}
'''
        script += 'function renderAccordion(){' + accordion
        script += 'function updateStepStatus(order, status){' + status
        script += '''
updateStepStatus(2,'running');
assert.equal(STEPS[0].status,'running');
renderAccordion();
assert.equal(calls.find(c=>c.phase.phase_id==='parse_erd').tools, undefined);
assert.equal(calls.find(c=>c.tools).phase.phase_id, undefined);
assert.equal(calls.find(c=>c.tools).tools[0].detail,'dbldatagen');
updateStepStatus(1,'failed');
assert.equal(STEPS[1].status,'running');
'''
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
