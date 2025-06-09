#!/usr/bin/env python3
"""Check all configuration fields in HTML template against the config module."""

import re
from pathlib import Path

def extract_data_keys_from_html():
    """Extract all data-key attributes from the configuration HTML template."""
    html_file = Path(__file__).parent.parent / "app/templates/admin/configuration.html"
    
    with open(html_file, 'r') as f:
        content = f.read()
    
    # Find all data-key attributes
    pattern = r'data-key="([^"]+)"'
    keys = re.findall(pattern, content)
    
    # Group by category
    categorized_keys = {}
    for key in keys:
        if '.' in key:
            category, field = key.split('.', 1)
            if category not in categorized_keys:
                categorized_keys[category] = []
            categorized_keys[category].append(field)
    
    return categorized_keys

def extract_config_keys_from_python():
    """Extract configuration keys from the config.py module."""
    config_file = Path(__file__).parent.parent / "app/blueprints/admin/config.py"
    
    with open(config_file, 'r') as f:
        content = f.read()
    
    # Extract GET method config_get calls
    pattern = r'config_get\("([^"]+)"'
    keys = re.findall(pattern, content)
    
    # Group by category
    categorized_keys = {}
    for key in keys:
        if '.' in key:
            category, field = key.split('.', 1)
            if category not in categorized_keys:
                categorized_keys[category] = []
            categorized_keys[category].append(field)
    
    return categorized_keys

def main():
    """Compare HTML template fields with Python configuration."""
    print("Configuration Field Comparison")
    print("=" * 80)
    
    html_keys = extract_data_keys_from_html()
    python_keys = extract_config_keys_from_python()
    
    # Get all unique categories
    all_categories = sorted(set(html_keys.keys()) | set(python_keys.keys()))
    
    missing_in_python = []
    missing_in_html = []
    
    for category in all_categories:
        print(f"\n{category.upper()} Category:")
        print("-" * 40)
        
        html_fields = set(html_keys.get(category, []))
        python_fields = set(python_keys.get(category, []))
        
        # Fields in HTML but not in Python (need to be added to config.py)
        in_html_only = html_fields - python_fields
        if in_html_only:
            print(f"\n  ❌ Missing in Python config (need to add to GET method):")
            for field in sorted(in_html_only):
                print(f"     - {category}.{field}")
                missing_in_python.append(f"{category}.{field}")
        
        # Fields in Python but not in HTML (might be unused)
        in_python_only = python_fields - html_fields
        if in_python_only:
            print(f"\n  ⚠️  In Python but not in HTML (might be unused):")
            for field in sorted(in_python_only):
                print(f"     - {category}.{field}")
                missing_in_html.append(f"{category}.{field}")
        
        # Fields that match
        matching = html_fields & python_fields
        if matching:
            print(f"\n  ✅ Matching fields: {len(matching)}")
            for field in sorted(matching):
                print(f"     - {category}.{field}")
    
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print(f"  - Total missing in Python: {len(missing_in_python)}")
    print(f"  - Total unused in Python: {len(missing_in_html)}")
    
    if missing_in_python:
        print("\n🔧 FIELDS TO ADD TO PYTHON CONFIG:")
        for field in missing_in_python:
            category, key = field.split('.', 1)
            # Suggest the uppercase key name
            upper_key = key.upper()
            if category == "ldap":
                upper_key = "LDAP_" + upper_key
            elif category == "graph":
                upper_key = "GRAPH_" + upper_key
            elif category == "genesys":
                upper_key = "GENESYS_" + upper_key
            elif category == "data_warehouse":
                upper_key = "DATA_WAREHOUSE_" + upper_key
            elif category == "flask":
                upper_key = "FLASK_" + upper_key
            elif category == "auth":
                if "session" in key:
                    upper_key = "SESSION_" + upper_key.replace("SESSION_", "")
                else:
                    upper_key = "AUTH_" + upper_key
            elif category == "search":
                if "cache" in key:
                    upper_key = "CACHE_" + upper_key.replace("CACHE_", "")
                else:
                    upper_key = "SEARCH_" + upper_key
            elif category == "audit":
                upper_key = "AUDIT_" + upper_key
                
            print(f'    "{upper_key}": config_get("{field}", ""),')

if __name__ == "__main__":
    main()