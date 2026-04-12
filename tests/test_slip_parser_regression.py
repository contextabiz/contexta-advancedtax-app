import json
import unittest
from pathlib import Path

from extraction.slip_parser import parse_pdf_slip


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "slip_parser_regression_cases.json"


class SlipParserRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def assert_money_close(self, actual: float, expected: float, places: int = 2) -> None:
        self.assertAlmostEqual(float(actual or 0.0), float(expected), places=places)

    def test_sample_slip_regressions(self) -> None:
        missing_files: list[str] = []

        for case in self.cases:
            sample_path = Path(case["path"])
            if not sample_path.exists():
                missing_files.append(str(sample_path))
                continue

            with self.subTest(case=case["name"]):
                parsed = parse_pdf_slip(str(sample_path), sample_path.name)
                self.assertEqual(parsed["type"], case["expected_type"])
                parsed_data = parsed.get("data", {})
                for field_name, expected_value in case["expected_fields"].items():
                    actual_value = parsed_data.get(field_name, 0.0)
                    self.assert_money_close(actual_value, expected_value)

        if missing_files:
            self.skipTest(
                "Sample slip PDFs are missing for regression validation: "
                + ", ".join(missing_files)
            )


if __name__ == "__main__":
    unittest.main()
