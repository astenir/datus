#!/usr/bin/env python3
"""
Build script for creating a bytecode-only distribution of Datus-agent
This script compiles all .py files to .pyc and creates a package with only bytecode
"""

import compileall
import os
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


def read_dependencies_from_setup():
    """Read dependencies from the main setup.py file to ensure consistency"""
    setup_py_path = Path(__file__).parent / "setup.py"
    if not setup_py_path.exists():
        return []

    dependencies = []
    try:
        with open(setup_py_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract CORE_DEPENDENCIES from setup.py
        import re

        pattern = r"CORE_DEPENDENCIES\s*=\s*\[(.*?)\]"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            deps_str = match.group(1)
            # Extract quoted strings
            dep_pattern = r'"([^"]+)"'
            dependencies = re.findall(dep_pattern, deps_str)

    except Exception as e:
        print(f"Warning: Could not read dependencies from setup.py: {e}")
        # Fallback to hardcoded list
        dependencies = [
            "python-dotenv==1.0.0",
            "pandas==2.1.4",
            "sqlalchemy==2.0.23",
            "sqlglot>=26.12.0",
            "snowflake-connector-python>=3.6.0",
            "pyyaml==6.0.1",
            "langsmith>=0.0.77",
            "structlog>=23.1.0",
            "openai>=1.12.0",
            "httpx[socks]==0.27.2",
            "tantivy>=0.22.2",
            "aiohttp>=3.11.16",
            "xlsxwriter>=3.2.2",
            "tiktoken>=0.9.0",
            "openai-agents==0.0.11",
            "Markdown==3.8",
            "sqllineage>=0.20.0",
            "lancedb>=0.18.0",
            "datasets>=3.5.1",
            "transformers>=4.51.3",
            "sentence-transformers==4.1.0",
            "pyarrow<19.0.0",
            "pylance>=0.26.1",
            "rich==14.0.0",
            "prompt_toolkit>=3.0.51",
            "textual==3.2.0",
            "anthropic==0.51.0",
            "duckdb-engine>=0.17.0",
            "snowflake-sqlalchemy>=1.7.3",
            "opentelemetry-api>=1.33.1",
        ]

    return dependencies


class PycPackageBuilder:
    """Class to handle bytecode-only package building"""

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"
        self.temp_dir = self.project_root / "temp_pyc_build"
        self.egg_info_dirs = list(self.project_root.glob("*.egg-info"))

        # Source directories
        self.datus_source = self.project_root / "datus"
        self.conf_source = self.project_root / "conf"
        self.templates_source = self.project_root / "datus" / "prompts" / "prompt_templates"
        self.mcp_source = self.project_root / "mcp"

    def get_version(self):
        """Read version from datus/__init__.py"""
        init_file = self.project_root / "datus" / "__init__.py"
        with open(init_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("__version__"):
                    return line.split("=")[1].strip().strip('"').strip("'")
        raise RuntimeError("Unable to find version string.")

    def clean_build_artifacts(self):
        """Clean previous build artifacts"""
        print("🧹 Cleaning previous build artifacts...")

        # Remove dist directory
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
            print(f"   Removed {self.dist_dir}")

        # Remove build directory
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
            print(f"   Removed {self.build_dir}")

        # Remove temp directory
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            print(f"   Removed {self.temp_dir}")

        # Remove egg-info directories
        for egg_dir in self.egg_info_dirs:
            if egg_dir.exists():
                shutil.rmtree(egg_dir)
                print(f"   Removed {egg_dir}")

        print("✅ Cleanup completed\n")

    def create_directory_structure(self):
        """Create the required directory structure for package building"""
        print("📁 Creating directory structure...")

        # Create temp build directory
        self.temp_dir.mkdir(exist_ok=True)

        # Create datus package directory in temp
        datus_temp = self.temp_dir / "datus"
        datus_temp.mkdir(exist_ok=True)

        print(f"   Created {self.temp_dir}")
        print(f"   Created {datus_temp}")
        print("✅ Directory structure created\n")

    def compile_python_files(self):
        """Compile all Python files to bytecode"""
        print("🔧 Compiling Python files to bytecode...")

        # Compile the entire datus package
        if not self.datus_source.exists():
            raise FileNotFoundError(f"Source directory not found: {self.datus_source}")

        # Use compileall to compile all Python files in the datus directory
        success = compileall.compile_dir(
            str(self.datus_source),
            ddir=str(self.temp_dir / "datus"),
            force=True,
            quiet=0,
            legacy=False,
            optimize=0,
            invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH,
        )

        if not success:
            raise RuntimeError("Failed to compile Python files")

        # Copy compiled files to temp directory
        self._copy_compiled_files()

        print("✅ Python files compiled successfully\n")

    def _copy_compiled_files(self):
        """Copy compiled .pyc files from __pycache__ directories to proper locations"""
        print("📋 Copying compiled files...")

        for root, _, files in os.walk(self.datus_source):
            # Skip __pycache__ directories in the search
            if "__pycache__" in root:
                continue

            # Get relative path from datus source
            rel_path = Path(root).relative_to(self.datus_source)
            target_dir = self.temp_dir / "datus" / rel_path
            target_dir.mkdir(parents=True, exist_ok=True)

            # Look for __pycache__ directory in current directory
            pycache_dir = Path(root) / "__pycache__"
            if pycache_dir.exists():
                for pyc_file in pycache_dir.glob("*.pyc"):
                    # Extract original filename (remove .cpython-xx.pyc suffix)
                    original_name = pyc_file.name.split(".")[0] + ".pyc"
                    target_file = target_dir / original_name
                    shutil.copy2(pyc_file, target_file)
                    print(f"   Copied {pyc_file} -> {target_file}")

            # Copy non-Python files (like __init__.py becomes __init__.pyc if compiled)
            for file in files:
                if file.endswith(".py"):
                    continue  # Skip .py files, we want only .pyc

                source_file = Path(root) / file
                target_file = target_dir / file
                shutil.copy2(source_file, target_file)
                print(f"   Copied non-Python file: {source_file} -> {target_file}")

    def copy_data_files(self):
        """Copy configuration and template files to temp directory"""
        print("📄 Copying data files...")

        # Create data directories in temp
        data_dir = self.temp_dir / "datus_data"
        data_dir.mkdir(exist_ok=True)

        conf_dir = data_dir / "conf"
        template_dir = data_dir / "template"
        sample_dir = data_dir / "sample"

        # Copy configuration files (excluding agent.yml)
        if self.conf_source.exists():
            conf_dir.mkdir(exist_ok=True)
            for conf_file in self.conf_source.iterdir():
                if conf_file.is_file() and conf_file.name != "agent.yml":
                    target_file = conf_dir / conf_file.name
                    shutil.copy2(conf_file, target_file)
                    print(f"   Copied {conf_file} -> {target_file}")
                elif conf_file.name == "agent.yml":
                    print(f"   Skipped {conf_file} (excluded from package)")

        # Copy template files
        if self.templates_source.exists():
            shutil.copytree(self.templates_source, template_dir, dirs_exist_ok=True)
            print(f"   Copied {self.templates_source} -> {template_dir}")

        # Copy sample files
        tests_source = self.project_root / "tests"
        sample_demo_file = tests_source / "duckdb-demo.duckdb"

        if sample_demo_file.exists():
            sample_dir.mkdir(exist_ok=True)
            shutil.copy2(sample_demo_file, sample_dir / "duckdb-demo.duckdb")
            print(f"   Copied {sample_demo_file} -> {sample_dir}/duckdb-demo.duckdb")

        print("✅ Data files copied successfully\n")

    def copy_mcp_files(self):
        """Copy MCP server files to temp directory as part of the package (preserving source files)"""
        print("🔧 Copying MCP server files...")

        # Copy MCP files directly to temp directory root (as part of the package)
        if self.mcp_source.exists():
            mcp_target = self.temp_dir / "datus-mcp"

            # Copy files selectively, excluding unnecessary directories
            def ignore_patterns(dir_path, names):
                """Ignore unnecessary files and directories"""
                ignore = set()
                for name in names:
                    if name in {
                        ".venv",
                        ".git",
                        "__pycache__",
                        ".pytest_cache",
                        "node_modules",
                        ".mypy_cache",
                        ".tox",
                        "venv",
                        "env",
                        ".env",
                    }:
                        ignore.add(name)
                    elif name.endswith((".pyc", ".pyo", ".pyd", ".so", ".egg-info")):
                        ignore.add(name)
                return ignore

            shutil.copytree(self.mcp_source, mcp_target, dirs_exist_ok=True, ignore=ignore_patterns)
            print(f"   Copied {self.mcp_source} -> {mcp_target}")

            # Create __init__.py for datus-mcp package
            mcp_init_file = mcp_target / "__init__.py"
            mcp_init_file.write_text('"""MCP Servers for Datus Agent"""\n__version__ = "0.1.0"\n')
            print(f"   Created {mcp_init_file}")

            # Compile Python files in MCP directory (keeping source files)
            self._compile_mcp_python_files(mcp_target)
        else:
            print(f"   ⚠️  MCP source directory not found: {self.mcp_source}")

        print("✅ MCP files copied successfully (source files preserved)\n")

    def _compile_mcp_python_files(self, mcp_dir):
        """Compile Python files in MCP directory but keep source .py files"""
        print("   🔧 Compiling MCP Python files (keeping source files)...")

        compiled_count = 0
        for py_file in mcp_dir.rglob("*.py"):
            try:
                # Compile to .pyc in the same directory
                pyc_file = py_file.with_suffix(".pyc")
                py_compile.compile(str(py_file), str(pyc_file), doraise=True)

                # Keep the original .py file (do not remove)
                compiled_count += 1

            except Exception as e:
                print(f"      Warning: Failed to compile {py_file}: {e}")

        print(f"   ✅ Compiled {compiled_count} MCP Python files (source files preserved)")

    def create_setup_py(self):
        """Create setup.py for the compiled package"""
        print("📝 Creating setup.py for compiled package...")

        version = self.get_version()

        setup_content = f'''#!/usr/bin/env python3
"""
Setup script for Datus-agent compiled package
"""

import os
import sys
import shutil
from pathlib import Path
from setuptools import setup, find_packages
from setuptools.command.install import install

class CustomInstallCommand(install):
    """Custom installation command to set up user directories"""

    def run(self):
        # Run the standard installation
        install.run(self)

        # Set up user directories
        self.setup_user_directories()

    def setup_user_directories(self):
        """Set up ~/.datus directory structure"""
        user_home = Path.home()
        datus_dir = user_home / ".datus"

        # Create directories
        data_dir = datus_dir / "data"
        conf_dir = datus_dir / "conf"
        template_dir = datus_dir / "template"
        sample_dir = datus_dir / "sample"

        for directory in [data_dir, conf_dir, template_dir, sample_dir]:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"Created directory: {{directory}}")

        # Copy configuration, template, and sample files
        package_data_dir = Path(__file__).parent / "datus_data"

        if package_data_dir.exists():
            # Copy conf files
            source_conf = package_data_dir / "conf"
            if source_conf.exists():
                for conf_file in source_conf.iterdir():
                    if conf_file.is_file() and conf_file.name != "agent.yml":
                        target_file = conf_dir / conf_file.name
                        if not target_file.exists():  # Don't overwrite existing config
                            shutil.copy2(conf_file, target_file)
                            print(f"Copied config: {{conf_file.name}}")
                    elif conf_file.name == "agent.yml":
                        print(f"Skipped config: {{conf_file.name}} (not included in package)")

            # Copy template files
            source_template = package_data_dir / "template"
            if source_template.exists():
                for template_file in source_template.rglob("*"):
                    if template_file.is_file():
                        rel_path = template_file.relative_to(source_template)
                        target_file = template_dir / rel_path
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(template_file, target_file)
                        print(f"Copied template: {{rel_path}}")

            # Copy sample files
            source_sample = package_data_dir / "sample"
            if source_sample.exists():
                for sample_file in source_sample.rglob("*"):
                    if sample_file.is_file():
                        rel_path = sample_file.relative_to(source_sample)
                        target_file = sample_dir / rel_path
                        target_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(sample_file, target_file)
                        print(f"Copied sample: {{rel_path}}")

        print(f"\\n✅ Datus user directories set up at {{datus_dir}}")

# Read the contents of README file
this_directory = Path(__file__).parent
readme_path = this_directory / "README.md"
long_description = ""
if readme_path.exists():
    long_description = readme_path.read_text(encoding='utf-8')

setup(
    name="datus-agent",
    version="{version}",
    description="AI-powered SQL Agent for data engineering (Compiled Version)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Datus Team",
    author_email="harrison.zhao@datus.ai",
    url="https://github.com/datus-ai/datus-agent",
    packages=[
        "datus",
        "datus.agent",
        "datus.cli",
        "datus.configuration",
        "datus.models",
        "datus.prompts",
        "datus.prompts.prompt_templates",
        "datus.schemas",
        "datus.storage",
        "datus.storage.document",
        "datus.storage.schema_metadata",
        "datus.storage.metric",
        "datus.tools",
        "datus.tools.db_tools",
        "datus.tools.lineage_graph_tools",
        "datus.tools.llms_tools",
        "datus.tools.output_tools",
        "datus.tools.search_tools",
        "datus.utils",
        "datus_data",
        "datus-mcp",
    ],
    python_requires=">=3.10",
    install_requires=[
        "python-dotenv==1.0.0",
        "pandas==2.1.4",
        "sqlalchemy==2.0.23",
        "sqlglot>=26.12.0",
        "snowflake-connector-python>=3.6.0",
        "starrocks>=1.2.2",
        "pyyaml==6.0.1",
        "langsmith>=0.0.77",
        "structlog>=23.1.0",
        "openai>=1.12.0",
        "httpx[socks]==0.27.2",
        "tantivy>=0.22.2",
        "aiohttp>=3.11.16",
        "xlsxwriter>=3.2.2",
        "tiktoken>=0.9.0",
        "openai-agents==0.0.11",
        "Markdown==3.8",
        "sqllineage>=0.20.0",
        "lancedb>=0.18.0",
        "datasets>=3.5.1",
        "torch>=2.3.0",
        "transformers>=4.51.3",
        "sentence-transformers==4.1.0",
        "pyarrow<19.0.0",
        "pylance>=0.26.1",
        "rich==14.0.0",
        "prompt_toolkit>=3.0.51",
        "textual==3.2.0",
        "anthropic==0.51.0",
        "duckdb-engine>=0.17.0",
        "snowflake-sqlalchemy>=1.7.3",
        "opentelemetry-api>=1.33.1",
        "anthropic>=0.18.1",
        "prompt-toolkit>=3.0.36",
        "rich>=13.7.0",
        "click>=8.1.7",
        "jinja2>=3.1.2",
        "tiktoken>=0.5.2",
        "pyperclip>=1.8.2",
        "colorama>=0.4.6",
        "tabulate>=0.9.0",
        "tqdm>=4.66.1",
    ],
    entry_points={{
        "console_scripts": [
            "datus-agent=datus.main:main",
            "datus-cli=datus.cli.main:main",
            "datus=datus.cli.main:main",
            "datus-init=datus.cli.init:main",
        ],
    }},
    include_package_data=True,
    package_data={{
        "": ["*.pyc", "*.yml", "*.yaml", "*.json", "*.md", "*.txt", "*.j2"],
        "datus": ["*.yml", "*.yaml", "*.json", "*.md", "*.txt"],
        "datus.prompts": ["*.txt", "*.md", "*.j2"],
        "datus.prompts.prompt_templates": ["*.j2"],
        "datus.schemas": ["*.json", "*.yml", "*.yaml"],
        "datus_data": ["**/*"],
        "conf": ["*.yml", "*.yaml"],
        "datus-mcp": ["**/*"],
    }},
    cmdclass={{
        'install': CustomInstallCommand,
    }},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
'''

        setup_file = self.temp_dir / "setup.py"
        setup_file.write_text(setup_content)
        print(f"   Created {setup_file}")
        print("✅ Setup.py created successfully\n")

    def create_manifest(self):
        """Create MANIFEST.in for including data files"""
        print("📋 Creating MANIFEST.in...")

        manifest_content = """# Include data files
recursive-include datus_data *
include README.md
include LICENSE
"""

        manifest_file = self.temp_dir / "MANIFEST.in"
        manifest_file.write_text(manifest_content)
        print(f"   Created {manifest_file}")
        print("✅ MANIFEST.in created successfully\n")

    def copy_readme_and_license(self):
        """Copy README and LICENSE files"""
        print("📄 Copying README and LICENSE...")

        for filename in ["README.md", "LICENSE"]:
            source_file = self.project_root / filename
            if source_file.exists():
                target_file = self.temp_dir / filename
                shutil.copy2(source_file, target_file)
                print(f"   Copied {filename}")

        print("✅ README and LICENSE copied\n")

    def build_package(self):
        """Build the package using setuptools"""
        print("🔨 Building package...")

        # Change to temp directory
        original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        try:
            # Build source distribution
            subprocess.run([sys.executable, "setup.py", "sdist"], check=True)

            # Build wheel distribution
            subprocess.run([sys.executable, "setup.py", "bdist_wheel"], check=True)

            print("✅ Package built successfully\n")

        finally:
            os.chdir(original_cwd)

    def copy_distributions(self):
        """Copy built distributions to main dist directory"""
        print("📦 Copying distributions to dist directory...")

        temp_dist = self.temp_dir / "dist"
        if temp_dist.exists():
            self.dist_dir.mkdir(exist_ok=True)
            for dist_file in temp_dist.iterdir():
                target_file = self.dist_dir / dist_file.name
                shutil.copy2(dist_file, target_file)
                print(f"   Copied {dist_file.name}")

        print("✅ Distributions copied\n")

    def build(self):
        """Main build process"""
        print("🚀 Starting Datus-agent bytecode package build...\n")

        try:
            self.clean_build_artifacts()
            self.create_directory_structure()
            self.compile_python_files()
            self.copy_data_files()
            self.copy_mcp_files()
            self.create_setup_py()
            self.create_manifest()
            self.copy_readme_and_license()
            self.build_package()
            self.copy_distributions()

            print("🎉 Build completed successfully!")
            print(f"📦 Package files available in: {self.dist_dir}")

            # List built files
            if self.dist_dir.exists():
                print("\n📋 Built files:")
                for file in self.dist_dir.iterdir():
                    print(f"   📄 {file.name}")

            # Clean up temp directory after successful build
            self.cleanup_temp_directory()

        except Exception as e:
            print(f"❌ Build failed: {e}")
            # Also cleanup temp directory on failure
            self.cleanup_temp_directory()
            raise

    def cleanup_temp_directory(self):
        """Clean up temporary build directory"""
        if self.temp_dir.exists():
            print("\n🧹 Cleaning up temporary build directory...")
            shutil.rmtree(self.temp_dir)
            print(f"   Removed {self.temp_dir}")
            print("✅ Cleanup completed")


def main():
    """Main entry point"""
    builder = PycPackageBuilder()
    builder.build()


if __name__ == "__main__":
    main()
