"""Pruebas offline con datos sintéticos EXCLUSIVAMENTE dentro de tests.
Nunca alimentan el dashboard público ni son TRM reales.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


def fixture():
    d = pd.date_range("2025-01-02", periods=90, freq="7D")
    return pd.DataFrame({"valor": [3600+i%27*12.25 for i in range(len(d))], "vigenciadesde": d.astype(str)})


class TestTRM(unittest.TestCase):
    def setUp(self):
        self.df = app.clean_frame(fixture())

    def test_clean_date_and_values(self):
        source = fixture().copy()
        source.loc[len(source)] = [-900, "2025-05-30"]
        source.loc[len(source)] = [4100.0, "2025-01-02"]
        result = app.clean_frame(source)
        self.assertEqual(len(result), 90)
        self.assertEqual(result.iloc[0]["valor"], 4100)

    def test_group_month(self):
        selected, options = app.parse_filters({"start":["2025-01-01"], "end":["2025-06-30"], "group":["month"]}, self.df)
        payload = app.build_payload(self.df, selected, options, {"source":"api","updated":None,"warning":None})
        self.assertGreater(len(payload["groups"]), 1)
        self.assertEqual(payload["stats"]["observations"], len(selected))
        self.assertEqual(sum(x["count"] for x in payload["groups"]), len(selected))
        self.assertEqual(len(payload["heatmap"][0]["months"]), 12)

    def test_wrong_dates_and_group(self):
        for q in ({"start":["2025-12-01"],"end":["2025-01-01"]}, {"group":["fail"]}, {"start":["nonsense"]}):
            with self.assertRaises(ValueError):
                app.parse_filters(q, self.df)

    def test_seaborn_real_render(self):
        part, _ = app.parse_filters({"start":["2025-01-01"],"end":["2025-12-31"]}, self.df)
        blob = app.seaborn_png(part)
        self.assertGreater(len(blob), 6000)
        self.assertTrue(blob.startswith(b'\x89PNG\r\n\x1a\n'))

    def test_remote_schema(self):
        rows=[{"valor":"3750.18","vigenciadesde":"2025-04-12T00:00:00","vigenciahasta":"2025-04-13T00:00:00","unidad":"COP"}]
        mock=MagicMock()
        mock.json.return_value=rows
        with patch.object(app.requests,'get',return_value=mock) as req:
            df=app.load_remote()
            self.assertEqual(df['valor'].iloc[0],3750.18)
            self.assertIn('$where',req.call_args.kwargs['params'])

if __name__ == '__main__':
    unittest.main()
