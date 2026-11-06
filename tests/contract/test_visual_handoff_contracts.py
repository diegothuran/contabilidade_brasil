"""Checks de tooling/contratos; não executam RVE, Claude ou browser."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / '.claude/skills/rastro-visual-handoff'
SCRIPT = SKILL / 'scripts/inspect_visual.py'
spec = importlib.util.spec_from_file_location('rastro_visual_inspector', SCRIPT)
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)
CSS = b'''.rastro{--blue-rastro:#1f5c86;--ref:url(https://example.test/x)}
.rastro{--blue-rastro:#18486a}.x{transition:opacity 150ms ease}
@keyframes demo{from{opacity:0}to{opacity:1}}
@media (prefers-reduced-motion:reduce){.x{animation:none}}
@media print{.x{animation:none}}'''
HTML = b'<style>' + CSS + b'</style><script>const hidden="NEVER_EXPORT_ME";requestAnimationFrame(x);</script>'


class VisualHandoffContracts(unittest.TestCase):
    def test_separate_css_is_supported(self):
        data = inspector.inspect(CSS, 'css')
        self.assertEqual(data['source']['kind'], 'css')
        self.assertEqual(data['classification'], 'observado_estatico')
        self.assertEqual(data['javascript_marker_counts']['requestAnimationFrame'], 0)
        self.assertEqual(data['motion_declarations'][0]['value'], 'opacity 150ms ease')

    def test_html_does_not_export_script(self):
        data = inspector.inspect(HTML, 'html')
        self.assertEqual(data['javascript_marker_counts']['requestAnimationFrame'], 1)
        self.assertNotIn('NEVER_EXPORT_ME', json.dumps(data))
        self.assertNotIn('hidden=', json.dumps(data))

    def test_duplicates_preserved_not_computed(self):
        data = inspector.inspect(CSS, 'css')
        self.assertEqual([x['value'] for x in data['css_custom_property_definitions']], ['#1f5c86', '#18486a'])
        self.assertNotIn('computed_styles', data)
        self.assertNotIn('--ref', json.dumps(data))

    def test_keyframe_media_reduce(self):
        data = inspector.inspect(CSS, 'css')
        self.assertEqual(data['keyframe_definitions'][0]['name'], 'demo')
        self.assertEqual(len(data['reduced_motion_blocks']), 1)
        self.assertIn('print', data['media_query_headers'])

    def test_invalid_kind_encoding_and_size(self):
        with self.assertRaises(ValueError):
            inspector.inspect(CSS, 'tsx')
        with self.assertRaises(UnicodeError):
            inspector.inspect(b'\xff\xfe', 'css')
        with self.assertRaises(ValueError):
            inspector.inspect(b'x' * (inspector.MAX_BYTES + 1), 'css')

    def cli(self, source, target):
        return subprocess.run([sys.executable, str(SCRIPT), '--input', str(source), '--output', str(target)],
                              text=True, capture_output=True, timeout=10)

    def test_cli_no_overwrite_and_css_read(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = base/'source.css'; source.write_bytes(CSS)
            target = base/'new/report.json'
            self.assertEqual(self.cli(source, target).returncode, 0)
            saved = target.read_bytes()
            self.assertEqual(self.cli(source, target).returncode, 1)
            self.assertEqual(target.read_bytes(), saved)
            self.assertEqual(len(json.loads(saved)['source']['sha256']), 64)

    def test_cli_rejects_symlink_and_other_extensions(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = base/'source.css'; source.write_bytes(CSS)
            real = base/'real'; real.mkdir(); (base/'link').symlink_to(real, target_is_directory=True)
            self.assertEqual(self.cli(source, base/'link/out.json').returncode, 1)
            self.assertFalse((real/'out.json').exists())
            bad = base/'source.tsx'; bad.write_bytes(HTML)
            self.assertEqual(self.cli(bad, base/'out.json').returncode, 1)
            symlink = base/'sym.css'; symlink.symlink_to(source)
            self.assertEqual(self.cli(symlink, base/'out.json').returncode, 1)

    def test_rastro_identity_matches_observed_stylesheet(self):
        tokens = json.loads((ROOT/'design/rastro/tokens.json').read_text())
        stylesheet = (ROOT/'apps/web/src/rastro/rastro.css').read_text()
        for name in ('ink', 'blue', 'paper', 'surface', 'line', 'info', 'attention', 'danger', 'success'):
            self.assertIn(tokens['identity'][name], stylesheet)
        self.assertEqual(tokens['identity']['blue'], '#1f5c86')
        self.assertEqual(tokens['identity']['info'], '#2f80ed')
        for difference in tokens['knownDifferences']:
            self.assertEqual(difference['status'], 'reconciled_v0.7.0')
            observed = difference.get('stylesheet', difference.get('stylesheetPanel', difference.get('stylesheetButton')))
            self.assertEqual(difference['contract'], observed)
        self.assertEqual(tokens['status'], 'runtime_visual_adoption_v0.7.0_optional_primitives_not_imported')

    def test_proposed_motion_is_scoped_optional_and_bounded(self):
        css = (ROOT/'design/rastro/motion.css').read_text()
        timings = [int(x) for x in re.findall(r':\s*(\d+)ms', css)]
        self.assertTrue(timings)
        self.assertTrue(all(140 <= x <= 180 for x in timings))
        self.assertIn('.rastro .rastro-motion-panel', css)
        self.assertIn('@media (prefers-reduced-motion: reduce)', css)
        self.assertIn('@media print', css)
        self.assertNotRegex(css, r'transition\s*:\s*all\b')
        for path in (ROOT/'apps/web/src').rglob('*.tsx'):
            self.assertNotIn('design/rastro/motion.css', path.read_text())

    def test_skill_metadata_and_resources(self):
        text = (SKILL/'SKILL.md').read_text()
        metadata = yaml.safe_load(text.split('---', 2)[1])
        self.assertEqual(metadata['name'], 'rastro-visual-handoff')
        self.assertTrue(metadata['description'])
        self.assertNotIn('[TODO:', text)
        self.assertLess(len(text.splitlines()), 500)
        for path in ('references/workflow.md', 'templates/HANDOFF.md', 'scripts/inspect_visual.py'):
            self.assertTrue((SKILL/path).is_file())
        self.assertFalse((SKILL/'scripts/example.py').exists())

    def test_evals_are_traceable_not_executed(self):
        data = json.loads((ROOT/'docs/design-motion/eval-cases.json').read_text())
        requirements = set(re.findall(r'## (RVM-\d{3})', (ROOT/'docs/design-motion/spec.md').read_text()))
        cases = data['cases']; ids = [x['id'] for x in cases]
        self.assertEqual(len(cases), 12)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(data['execution_status'], 'not_run')
        covered = set()
        for case in cases:
            self.assertEqual(case['status'], 'not_run')
            self.assertTrue(set(case['requirements']) <= requirements)
            self.assertTrue(case['input'] and case['steps'] and case['oracle'] and case['evidence_required'])
            self.assertIn(case['severity'], ('critical', 'high', 'medium', 'low'))
            covered.update(case['requirements'])
        self.assertEqual(covered, requirements)


if __name__ == '__main__':
    unittest.main()
