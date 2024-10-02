from setuptools import setup, find_packages

def parse_requirements(filename):
    """ load requirements from a pip requirements file """
    with open(filename, 'r') as file:
        return [line.strip() for line in file if line.strip() and not line.startswith('#')]


setup(
    name="crossformer", 
    packages=find_packages(include=['crossformer', 'crossformer.*']),
    install_requires=parse_requirements('requirements.txt'),
)

