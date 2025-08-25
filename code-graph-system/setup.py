from setuptools import setup, find_packages

setup(
    name="code-graph-system",
    version="0.1.0",
    description="Universal Code Graph System - Plugin-based code analysis platform",
    author="Your Name",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "py2neo>=2021.2.3",
        "click>=8.0.0",
        "pyyaml>=6.0",
        "grpcio>=1.50.0",
        "grpcio-tools>=1.50.0",
        "protobuf>=4.0.0",
        "gitpython>=3.1.0",
        "redis>=4.0.0",
        "pandas>=1.5.0",
        "tqdm>=4.65.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "cgs=code_graph_system.cli:main",
        ],
    },
)