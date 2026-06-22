"""
Setup configuration for pinecone-backend
"""
from setuptools import setup, find_packages

setup(
    name="pinecone-backend",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        # Listed in requirements.txt
    ],
    python_requires=">=3.9",
)

