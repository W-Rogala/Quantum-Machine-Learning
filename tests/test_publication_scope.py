import unittest
import json
from tools.check_publication import publication_files, ROOT

class PublicationCompletenessTests(unittest.TestCase):
    def test_report_reproduction_assets_are_exported(self):
        files={p.relative_to(ROOT).as_posix() for p in publication_files()}
        for required in (
            'docs/mathematical_report/bibliography/report.sqlite',
            'docs/mathematical_report/bibliography/references.bib',
            'docs/mathematical_report/vendor/katex/katex.cjs',
            'docs/mathematical_report/vendor/katex/katex.min.css',
            'docs/mathematical_report/vendor/katex/LICENSE',
            'docs/mathematical_report/vendor/katex/fonts/KaTeX_Main-Regular.woff2',
            'tools/render_report_math.cjs',
            'tools/verify_math_report_browser.cjs',
            'docs/mathematical_report/app_content/ReportContent.jsx',
            'analysis_output/qrc_h3_memory/profile_summaries.csv',
        ):
            with self.subTest(path=required):self.assertIn(required,files)

        manifest=json.loads((ROOT/'docs/mathematical_report/source_manifest.json').read_text(encoding='utf8'))
        self.assertTrue({r['path'] for r in manifest}.issubset(files), 'Every report source must be present in the publication archive')

    def test_local_environments_and_full_archives_are_excluded(self):
        paths=[p.relative_to(ROOT).parts for p in publication_files()]
        forbidden={'.git','.aws','.codex','.agents','output','tmp','personal-project-crm','node_modules','__pycache__'}
        self.assertTrue(all(not forbidden.intersection(p) and not p[0].startswith('.venv') for p in paths))
        self.assertTrue(all('.env' not in p for p in paths))
