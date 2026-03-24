"""Tests for translation file consistency and completeness."""
import json
import os
import re
from pathlib import Path
import pytest

# Get the project root
PROJECT_ROOT = Path(__file__).parent.parent
TRANSLATIONS_DIR = PROJECT_ROOT / "src" / "translations"
TEMPLATES_DIR = PROJECT_ROOT / "src" / "templates"


class TestTranslationFileConsistency:
    """Tests to ensure all translation files have the same keys."""

    def test_all_translation_files_exist(self):
        """Test that all expected translation files exist."""
        expected_languages = [
            "ar", "de", "en", "es", "fa", "fr", "id", "it",
            "ja", "ko", "nl", "pl", "pt", "tr", "uk", "vi", "zh"
        ]
        
        for lang in expected_languages:
            filepath = TRANSLATIONS_DIR / f"{lang}.json"
            assert filepath.exists(), f"Translation file missing: {lang}.json"

    def test_all_translation_files_are_valid_json(self):
        """Test that all translation files are valid JSON."""
        for filename in os.listdir(TRANSLATIONS_DIR):
            if filename.endswith('.json'):
                filepath = TRANSLATIONS_DIR / filename
                with open(filepath, 'r', encoding='utf-8') as f:
                    try:
                        json.load(f)
                    except json.JSONDecodeError as e:
                        pytest.fail(f"Invalid JSON in {filename}: {e}")

    def test_all_translation_files_have_same_keys(self):
        """Test that all translation files have the exact same set of keys."""
        translation_files = {}
        
        for filename in os.listdir(TRANSLATIONS_DIR):
            if filename.endswith('.json'):
                filepath = TRANSLATIONS_DIR / filename
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                translation_files[filename] = set(data.keys())
        
        # Get the keys from the first file as reference
        first_file = list(translation_files.keys())[0]
        reference_keys = translation_files[first_file]
        
        # Check all other files have the same keys
        for filename, keys in translation_files.items():
            missing_keys = reference_keys - keys
            extra_keys = keys - reference_keys
            
            if missing_keys:
                pytest.fail(f"{filename} is missing keys: {missing_keys}")
            if extra_keys:
                pytest.fail(f"{filename} has extra keys: {extra_keys}")
        
        # Report total count for informational purposes
        assert len(reference_keys) > 0, "Translation files are empty"

    def test_translation_files_have_required_keys(self):
        """Test that all translation files have essential keys."""
        required_keys = [
            "language_name",
            "language_code",
            "subtitle_toolkit",
            "translate",
            "time_shift",
            "convert",
        ]
        
        for filename in os.listdir(TRANSLATIONS_DIR):
            if filename.endswith('.json'):
                filepath = TRANSLATIONS_DIR / filename
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for key in required_keys:
                    assert key in data, f"{filename} missing required key: {key}"


class TestTranslationKeyReferences:
    """Tests to ensure all translation key references in templates are defined."""

    def test_all_template_translation_references_exist(self):
        """Test that all translation key references in templates exist in translation files."""
        # Load English translations as reference
        with open(TRANSLATIONS_DIR / "en.json", 'r', encoding='utf-8') as f:
            en_translations = json.load(f)
        
        # Find all translation key references in templates
        # Pattern 1: translations.key_name (but not translations.get)
        # Pattern 2: translations.get('key_name', ...)
        pattern1 = r'translations\.(\w+)(?!\s*\(.*get)'
        pattern2 = r'translations\.get\([\'"]([^\'"]+)[\'"]'
        
        referenced_keys = set()
        
        for template_file in TEMPLATES_DIR.rglob("*.html"):
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all translation references using pattern 1 (translations.key_name)
            matches1 = re.findall(pattern1, content)
            # Filter out 'get' since it's a method, not a key
            matches1 = [m for m in matches1 if m != 'get']
            referenced_keys.update(matches1)
            
            # Find all translation references using pattern 2 (translations.get('key', ...))
            matches2 = re.findall(pattern2, content)
            referenced_keys.update(matches2)
        
        # Check all referenced keys exist in translations
        missing_keys = referenced_keys - set(en_translations.keys())
        
        if missing_keys:
            pytest.fail(f"Translation keys referenced in templates but not defined in en.json: {missing_keys}")

    def test_no_duplicate_keys_in_translation_files(self):
        """Test that no translation file has duplicate keys."""
        for filename in os.listdir(TRANSLATIONS_DIR):
            if filename.endswith('.json'):
                filepath = TRANSLATIONS_DIR / filename
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Parse and check for duplicates
                data = json.loads(content)
                keys = list(data.keys())
                unique_keys = set(keys)
                
                if len(keys) != len(unique_keys):
                    # Find duplicates
                    seen = set()
                    duplicates = set()
                    for key in keys:
                        if key in seen:
                            duplicates.add(key)
                        seen.add(key)
                    pytest.fail(f"Duplicate keys in {filename}: {duplicates}")
