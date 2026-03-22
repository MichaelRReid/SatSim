from setuptools import setup, find_packages

setup(
    name="satsim",
    version="1.0.0",
    description="Satellite Bus and EO/IR Payload UCI Simulation",
    packages=find_packages(),
    install_requires=[
        "lxml>=4.9.0",
        "rich>=13.0.0",
        "xmlschema>=2.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "satsim-console=cli.console:main",
        ],
    },
    python_requires=">=3.9",
)
