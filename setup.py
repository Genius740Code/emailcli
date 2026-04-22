from setuptools import setup, find_packages

setup(
    name="email-cli",
    version="1.0.0",
    description="A fast CLI email tool for custom domain email management",
    author="Email CLI",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "click>=8.0.0",
        "pyyaml>=6.0",
        "keyring>=23.0.0",
        "cryptography>=41.0.0",
        "psutil>=5.9.0",
        "tqdm>=4.64.0",
        "jsonschema>=4.0.0",
    ],
    entry_points={
        "console_scripts": [
            "email-cli=email_cli.cli:main",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
