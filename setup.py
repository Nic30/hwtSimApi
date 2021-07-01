from setuptools import setup, find_packages
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='hwtSimApi',
    version='1.3',
    description='RTL simulator API',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author_email='Nic30original@gmail.com',
    install_requires=[
        "sortedcontainers>=2.2.2",  # for calendar queue in simulator
        "pyMathBitPrecise>=1.0",  # bit precise integer types for sim
    ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
        "Topic :: System :: Hardware",
        "Topic :: System :: Emulators",
        "Topic :: Utilities"],
    license='MIT',
    packages=find_packages(),
    zip_safe=True,
)
