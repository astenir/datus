#!/usr/bin/env python3
"""
Installation verification script for the Redshift adapter.

This script performs a series of checks to verify that the adapter
is correctly installed and can be imported without errors.

Run this script AFTER installing the package with: pip install -e .
"""

import sys


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_success(text):
    """Print a success message."""
    print(f"✓ {text}")


def print_error(text):
    """Print an error message."""
    print(f"✗ {text}")


def main():
    """Run all verification checks."""
    
    all_checks_passed = True
    
    print_header("Redshift Adapter Installation Verification")
    
    # Check 1: Python version
    print("\n1. Checking Python version...")
    if sys.version_info >= (3, 8):
        print_success(f"Python version {sys.version_info.major}.{sys.version_info.minor} is compatible")
    else:
        print_error(f"Python version {sys.version_info.major}.{sys.version_info.minor} is too old (requires 3.8+)")
        all_checks_passed = False
    
    # Check 2: Import main package
    print("\n2. Checking if datus_redshift can be imported...")
    try:
        import datus_redshift
        print_success("datus_redshift package imported successfully")
        print(f"   Version: {datus_redshift.__version__}")
    except ImportError as e:
        print_error(f"Cannot import datus_redshift: {e}")
        print("   Make sure you installed the package with: pip install -e .")
        all_checks_passed = False
        return 1
    
    # Check 3: Import config
    print("\n3. Checking if RedshiftConfig can be imported...")
    try:
        from datus_redshift import RedshiftConfig
        print_success("RedshiftConfig imported successfully")
    except ImportError as e:
        print_error(f"Cannot import RedshiftConfig: {e}")
        all_checks_passed = False
    
    # Check 4: Import connector
    print("\n4. Checking if RedshiftConnector can be imported...")
    try:
        from datus_redshift import RedshiftConnector
        print_success("RedshiftConnector imported successfully")
    except ImportError as e:
        print_error(f"Cannot import RedshiftConnector: {e}")
        all_checks_passed = False
    
    # Check 5: Verify dependencies
    print("\n5. Checking required dependencies...")
    
    dependencies = {
        'redshift_connector': 'Amazon Redshift Python driver',
        'pyarrow': 'Apache Arrow for efficient data handling',
        'pandas': 'Data analysis library',
        'pydantic': 'Data validation library',
    }
    
    for package, description in dependencies.items():
        try:
            __import__(package)
            print_success(f"{package:20s} - {description}")
        except ImportError:
            print_error(f"{package:20s} - NOT FOUND ({description})")
            all_checks_passed = False
    
    # Check 6: Create config object
    print("\n6. Testing RedshiftConfig creation...")
    try:
        from datus_redshift import RedshiftConfig
        config = RedshiftConfig(
            host="test.redshift.amazonaws.com",
            username="testuser",
            password="testpass"
        )
        print_success("Can create RedshiftConfig object")
        print(f"   Config host: {config.host}")
        print(f"   Config port: {config.port}")
        print(f"   Config ssl: {config.ssl}")
    except Exception as e:
        print_error(f"Cannot create RedshiftConfig: {e}")
        all_checks_passed = False
    
    # Check 7: Verify connector class methods
    print("\n7. Checking RedshiftConnector methods...")
    try:
        from datus_redshift import RedshiftConnector
        required_methods = [
            'test_connection',
            'execute_query',
            'execute_arrow',
            'execute_pandas',
            'execute_csv',
            'get_databases',
            'get_schemas',
            'get_tables',
            'get_views',
            'get_schema',
            'close',
        ]
        
        for method in required_methods:
            if hasattr(RedshiftConnector, method):
                print_success(f"Method '{method}' exists")
            else:
                print_error(f"Method '{method}' not found")
                all_checks_passed = False
    except Exception as e:
        print_error(f"Cannot check methods: {e}")
        all_checks_passed = False
    
    # Check 8: Verify registration function
    print("\n8. Checking Datus registration...")
    try:
        from datus_redshift import register
        print_success("register() function found")
        print("   The adapter will auto-register with Datus when imported")
    except ImportError:
        print_error("register() function not found")
        all_checks_passed = False
    
    # Check 9: Verify __all__ exports
    print("\n9. Checking module exports...")
    try:
        import datus_redshift
        expected_exports = ['RedshiftConnector', 'RedshiftConfig', 'register']
        for export in expected_exports:
            if export in datus_redshift.__all__:
                print_success(f"'{export}' is exported")
            else:
                print_error(f"'{export}' not in __all__")
                all_checks_passed = False
    except Exception as e:
        print_error(f"Cannot check exports: {e}")
        all_checks_passed = False
    
    # Check 10: Try to check Datus integration (optional)
    print("\n10. Checking Datus Agent integration (optional)...")
    try:
        from datus.tools.db_tools import connector_registry
        print_success("Datus connector_registry imported")
        print("   Note: Full integration requires Datus Agent to be installed")
    except ImportError:
        print("   ℹ️  Datus Agent not installed - this is optional for testing")
        print("   Install with: pip install datus-agent>=0.2.2")
    
    # Final summary
    print_header("Verification Summary")
    
    if all_checks_passed:
        print("\n✅ All checks passed!")
        print("\nThe Redshift adapter is correctly installed and ready to use.")
        print("\nNext steps:")
        print("  1. Configure your Redshift credentials in example_usage.py")
        print("  2. Run: python example_usage.py")
        print("  3. Or use the adapter in your own code")
        print("\nQuick test:")
        print("  python -c \"from datus_redshift import RedshiftConnector; print('Success!')\"")
        return 0
    else:
        print("\n❌ Some checks failed!")
        print("\nPlease fix the errors above before using the adapter.")
        print("\nCommon fixes:")
        print("  - Make sure you installed with: pip install -e .")
        print("  - Check that you're in the correct Python environment")
        print("  - Install missing dependencies with: pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    """
    Run verification checks.
    
    Usage:
        python verify_installation.py
        
    Exit codes:
        0 - All checks passed
        1 - Some checks failed
    """
    exit_code = main()
    sys.exit(exit_code)

