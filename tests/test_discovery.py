"""Tests for test file discovery."""

from pathlib import Path

from catalyst_ci_test.discovery import discover_test_files, load_yaml_test_cases


class TestDiscoverTestFiles:
    def test_find_yaml_files(self, tmp_path):
        (tmp_path / "pipeline.test.yml").write_text("description: test\nasserts: []")
        (tmp_path / "other.yml").write_text("not a test")

        yaml_files, py_files = discover_test_files(tmp_path)
        assert len(yaml_files) == 1
        assert yaml_files[0].name == "pipeline.test.yml"
        assert len(py_files) == 0

    def test_find_python_files(self, tmp_path):
        (tmp_path / "test_pipeline.py").write_text("def test_x(): pass")
        (tmp_path / "helpers.py").write_text("# not a test")

        yaml_files, py_files = discover_test_files(tmp_path)
        assert len(yaml_files) == 0
        assert len(py_files) == 1
        assert py_files[0].name == "test_pipeline.py"

    def test_find_both(self, tmp_path):
        (tmp_path / "pipeline.test.yml").write_text("description: test\nasserts: []")
        (tmp_path / "test_pipeline.py").write_text("def test_x(): pass")

        yaml_files, py_files = discover_test_files(tmp_path)
        assert len(yaml_files) == 1
        assert len(py_files) == 1

    def test_single_yaml_file(self, tmp_path):
        f = tmp_path / "pipeline.test.yml"
        f.write_text("description: test\nasserts: []")

        yaml_files, py_files = discover_test_files(f)
        assert len(yaml_files) == 1
        assert len(py_files) == 0

    def test_nested_files(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.test.yml").write_text("description: test\nasserts: []")

        yaml_files, _ = discover_test_files(tmp_path)
        assert len(yaml_files) == 1

    def test_empty_directory(self, tmp_path):
        yaml_files, py_files = discover_test_files(tmp_path)
        assert yaml_files == []
        assert py_files == []


class TestLoadYamlTestCases:
    def test_single_document(self, tmp_path):
        f = tmp_path / "test.yml"
        f.write_text(
            'description: "Test 1"\n'
            "project: .\n"
            "asserts:\n"
            "  - type: success\n"
        )

        cases = load_yaml_test_cases(f)
        assert len(cases) == 1
        assert cases[0][0].description == "Test 1"

    def test_multi_document(self, tmp_path):
        f = tmp_path / "test.yml"
        f.write_text(
            '---\ndescription: "Test 1"\nasserts:\n  - type: success\n'
            '---\ndescription: "Test 2"\nasserts:\n  - type: failure\n'
        )

        cases = load_yaml_test_cases(f)
        assert len(cases) == 2
        assert cases[0][0].description == "Test 1"
        assert cases[1][0].description == "Test 2"

    def test_empty_documents_skipped(self, tmp_path):
        f = tmp_path / "test.yml"
        f.write_text(
            "---\n"
            '---\ndescription: "Test 1"\nasserts:\n  - type: success\n'
            "---\n"
        )

        cases = load_yaml_test_cases(f)
        assert len(cases) == 1
