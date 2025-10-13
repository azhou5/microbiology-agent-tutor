"""Setup script for MicroTutor V4."""

from setuptools import setup, find_packages

setup(
    name="microtutor",
    version="4.0.0",
    description="AI-powered microbiology tutoring system",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "python-multipart>=0.0.6",
        "jinja2>=3.1.2",
        "pydantic>=2.5.3",
        "openai>=1.10.0",
        "python-dotenv>=1.0.0",
    ],
)

