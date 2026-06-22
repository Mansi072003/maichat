"""
Setup configuration for rag-backend
"""
from setuptools import setup, find_packages

setup(
    name="rag-backend",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        # Listed in requirements.txt
    ],
    python_requires=">=3.9",
)

