from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skill" / "external-model-executor"


class SkillLayoutTests(unittest.TestCase):
    def test_required_files_exist(self) -> None:
        self.assertTrue((SKILL / "SKILL.md").is_file())
        self.assertTrue((SKILL / "agents" / "openai.yaml").is_file())
        self.assertTrue((SKILL / "scripts" / "external_executor.py").is_file())
        self.assertTrue((SKILL / "references" / "provider-compatibility.md").is_file())

    def test_skill_frontmatter_is_minimal(self) -> None:
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1]
        keys = [line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line]
        self.assertEqual(keys, ["name", "description"])


if __name__ == "__main__":
    unittest.main()
