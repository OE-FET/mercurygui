from setuptools import setup, find_packages

setup(
    name='mercurygui',
    version='1.1.3',
    description="",
    author='Sam Schott',
    author_email='ss2151@cam.ac.uk',
    url='https://github.com/oe-fet/mercurygui.git',
    license='MIT',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    package_data={
        'mercurygui': ['*.ui', '*/*.ui'],
    },
    entry_points={
        'console_scripts': [
            'mercurygui=mercurygui.main:run'
        ],
        'gui_scripts': [
            'mercurygui=mercurygui.main:run'
        ]
    },
    install_requires=[
        'pyvisa',
        'mercuryitc>=0.2.1',
        'numpy',
        'cx_pyqtgraph>=0.12.1',
        'qtpy',
        'repr',
        'setuptools',
    ],
    zip_safe=False,
    keywords='mercurygui',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Operating System :: Unix',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
)
