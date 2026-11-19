import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

try:
    import yaml
except ImportError:
    yaml = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CI_DIR = os.path.join(ROOT, "ci")
STARTERS_DIR = os.path.join(CI_DIR, "starters")
RAW_URL = re.compile(
    r"^https://gitlab\.com/windy6191/gitlab-workflow-template/-/raw/(v\d+\.\d+\.\d+)/ci/([a-z-]+\.yml)$"
)
INPUT = re.compile(r"\$\[\[\s*inputs\.([a-z0-9_]+)\s*\]\]")
STAGES = ("build", "test", "deploy", "rollback")
RESERVED = {"stages", "workflow", "default", "variables", "include", "spec"}


def template_names():
    return sorted(f for f in os.listdir(CI_DIR) if f.endswith(".yml"))


def load_template(name):
    """Retourne (inputs déclarés, configuration brute) d'un template."""
    with open(os.path.join(CI_DIR, name), encoding="utf-8") as handle:
        docs = list(yaml.safe_load_all(handle))
    if len(docs) == 1:
        return {}, docs[0]
    return docs[0]["spec"]["inputs"], docs[1]


def render(node, values):
    """Interpole comme GitLab : une valeur réduite à un input prend son type, sinon son texte."""
    if isinstance(node, dict):
        return {render(key, values): render(value, values) for key, value in node.items()}
    if isinstance(node, list):
        return [render(value, values) for value in node]
    if isinstance(node, str):
        whole = INPUT.fullmatch(node.strip())
        if whole:
            return values[whole.group(1)]
        return INPUT.sub(lambda m: str(values[m.group(1)]), node)
    return node


def defaults(inputs):
    return {name: spec.get("default") for name, spec in inputs.items()}


def used_inputs(name):
    with open(os.path.join(CI_DIR, name), encoding="utf-8") as handle:
        body = handle.read().split("\n---\n", 1)[-1]
    return set(INPUT.findall(body))


def jobs(config):
    return {key: value for key, value in config.items() if key not in RESERVED and not key.startswith(".")}


def starter_includes():
    for starter in sorted(os.listdir(STARTERS_DIR)):
        with open(os.path.join(STARTERS_DIR, starter), encoding="utf-8") as handle:
            for include in yaml.safe_load(handle)["include"]:
                yield starter, include


@unittest.skipIf(yaml is None, "PyYAML absent : ces tests tournent dans le job templates")
class TemplatesTest(unittest.TestCase):
    def test_inputs_used_and_declared_match(self):
        for name in template_names():
            declared, _ = load_template(name)
            with self.subTest(template=name):
                self.assertEqual(used_inputs(name), set(declared))

    def test_every_input_has_a_description_and_a_default(self):
        for name in template_names():
            declared, _ = load_template(name)
            for input_name, spec in declared.items():
                with self.subTest(template=name, input=input_name):
                    self.assertTrue(spec.get("description"))
                    self.assertIn("default", spec)

    def test_jobs_are_named_after_their_stage(self):
        for name in template_names():
            declared, raw = load_template(name)
            config = render(raw, defaults(declared))
            for job_name, job in jobs(config).items():
                stage = job.get("stage") or config.get(job.get("extends", ""), {}).get("stage")
                with self.subTest(template=name, job=job_name):
                    self.assertIn(stage, STAGES)
                    self.assertRegex(job_name, r"^%s_[a-z0-9_]+$" % stage)

    def test_base_keeps_long_branch_pipelines(self):
        _, base = load_template("base.yml")
        rules = [rule.get("if", "") for rule in base["workflow"]["rules"]]
        self.assertIn('$CI_PIPELINE_SOURCE == "merge_request_event"', rules)
        self.assertIn("$CI_COMMIT_BRANCH =~ /^(develop|staging|main)$/", rules)
        self.assertFalse([rule for rule in rules if "CI_OPEN_MERGE_REQUESTS" in rule])
        self.assertEqual(base["stages"], list(STAGES))

    def test_starters_pin_one_version_of_existing_templates(self):
        versions = set()
        for starter, include in starter_includes():
            match = RAW_URL.match(include["remote"])
            with self.subTest(starter=starter, include=include["remote"]):
                self.assertIsNotNone(match)
                versions.add(match.group(1))
                declared, _ = load_template(match.group(2))
                self.assertLessEqual(set(include.get("inputs", {})), set(declared))
        self.assertEqual(len(versions), 1, versions)

    @unittest.skipIf(shutil.which("check-jsonschema") is None, "check-jsonschema absent")
    def test_rendered_templates_match_gitlab_schema(self):
        for name in template_names():
            declared, raw = load_template(name)
            config = render(raw, defaults(declared))
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, ".gitlab-ci.yml")
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(config, handle)
                result = subprocess.run(
                    ["check-jsonschema", "--builtin-schema", "vendor.gitlab-ci", path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    universal_newlines=True,
                )
            with self.subTest(template=name):
                self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
