#!/usr/bin/env python3
"""
Setup script for Datus-agent: AI-powered SQL Agent for data engineering
This version packages only compiled .pyc files, not source .py files
"""

import os
import py_compile
from pathlib import Path

from setuptools import find_packages, setup
from setuptools.command.build_py import build_py
from setuptools.command.install import install


# Get version from datus/__init__.py
def get_version():
    """Read version from datus/__init__.py"""
    init_file = Path(__file__).parent / "datus" / "__init__.py"
    with open(init_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    raise RuntimeError("Unable to find version string.")


# Read the contents of README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")


# Read requirements from requirements.txt
def read_requirements():
    """Read requirements from requirements.txt file"""
    requirements_path = this_directory / "requirements.txt"
    if requirements_path.exists():
        with open(requirements_path, "r", encoding="utf-8") as f:
            requirements = []
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    # Handle version specifiers and comments
                    if "#" in line:
                        line = line.split("#")[0].strip()
                    requirements.append(line)
            return requirements
    return []


# Core dependencies based on your pyproject.toml
CORE_DEPENDENCIES = [
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
    "mcp>=1.9.2",
    "anyio>=4.9.0",
    "torch>=2.2.2; platform_machine!='arm64' or sys_platform!='darwin'",
    "torch>=2.3.0; platform_machine=='arm64' and sys_platform=='darwin'",
]

# Development dependencies
DEV_DEPENDENCIES = [
    "pytest==8.0.2",
    "pytest-asyncio>=0.23.8",
    "black==23.12.1",
    "mypy==1.8.0",
    "tqdm>=4.27.0",
]

# Build dependencies
BUILD_DEPENDENCIES = [
    "torch==2.3.1",
]


class BuildPycOnly(build_py):
    """Custom build command that compiles .py files to .pyc and excludes .py files"""

    def run(self):
        # First run the normal build
        super().run()

        # Then compile all .py files to .pyc and remove .py files
        self.compile_and_remove_py_files()

    def compile_and_remove_py_files(self):
        """Compile all .py files to .pyc and remove the .py files"""
        print("🔨 Compiling Python files to bytecode...")

        build_lib = Path(self.build_lib)

        # Find all .py files in the build directory
        py_files = list(build_lib.rglob("*.py"))

        compiled_count = 0
        for py_file in py_files:
            try:
                # Compile to .pyc
                py_compile.compile(str(py_file), doraise=True, optimize=2)

                # Remove the .py file
                py_file.unlink()
                compiled_count += 1

            except Exception as e:
                print(f"Warning: Failed to compile {py_file}: {e}")

        print(f"✅ Compiled {compiled_count} Python files to bytecode")
        print("✅ Removed source .py files from distribution")


class InstallPycOnly(install):
    """Custom install command for .pyc only packages"""

    def run(self):
        super().run()


# Custom package finder that includes __pycache__ directories
def find_packages_with_pycache(where=".", exclude=()):
    """Find packages including __pycache__ directories"""
    packages = find_packages(where=where, exclude=exclude)

    # Add __pycache__ directories as packages
    pycache_packages = []
    for root, dirs, _ in os.walk(where):
        if "__pycache__" in dirs:
            # Convert path to package name
            rel_path = os.path.relpath(root, where)
            if rel_path != ".":
                package_name = rel_path.replace(os.sep, ".")
                pycache_package = f"{package_name}.__pycache__"
                pycache_packages.append(pycache_package)

    return packages + pycache_packages


setup(
    name="datus-agent",
    version=get_version(),
    author="Datus team",
    author_email="harrison.zhao@datus.ai",
    description="SQL Agent for natural language to SQL conversion and execution (Compiled Version)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/datus/datus-agent",  # Update with your actual repository URL
    project_urls={
        "Bug Reports": "https://github.com/datus/datus-agent/issues",
        "Source": "https://github.com/datus/datus-agent",
        "Documentation": "https://github.com/datus/datus-agent#readme",
    },
    packages=find_packages(exclude=["tests*", "benchmark*", "docs*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Database",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.12",
    install_requires=CORE_DEPENDENCIES,
    extras_require={
        "dev": DEV_DEPENDENCIES,
        "build": BUILD_DEPENDENCIES,
        "all": CORE_DEPENDENCIES + DEV_DEPENDENCIES + BUILD_DEPENDENCIES,
    },
    entry_points={
        "console_scripts": [
            "datus-agent=datus.main:main",
            "datus-cli=datus.cli.main:main",
            "datus=datus.cli.main:main",
            "datus-init=datus.cli.init:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.yml", "*.yaml", "*.json", "*.md", "*.txt", "*.pyc", "*.j2"],
        "datus": ["*.yml", "*.yaml", "*.json", "*.md", "*.txt"],
        "datus.prompts": ["*.txt", "*.md", "*.j2"],
        "datus.prompts.prompt_templates": ["*.j2"],
        "datus.schemas": ["*.json", "*.yml", "*.yaml"],
        "conf": ["*.yml", "*.yaml"],
    },
    zip_safe=False,
    keywords=[
        "sql",
        "ai",
        "agent",
        "natural-language",
        "database",
        "data-engineering",
        "snowflake",
        "duckdb",
        "sqlite",
        "llm",
        "openai",
        "anthropic",
        "compiled",
    ],
    platforms=["any"],
    license="Apache-2.0",
    # Additional metadata
    maintainer="Datus Team",
    maintainer_email="harrison.zhao@datus.ai",
    # Custom build commands
    cmdclass={
        "build_py": BuildPycOnly,
        "install": InstallPycOnly,
    },
)
