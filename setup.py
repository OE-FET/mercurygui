from setuptools import setup, find_packages

setup(
    name='mercurygui',
    version='1.1.2-dev',
    description="",
    author='Sam Schott',
    author_email='ss2151@cam.ac.uk',
    url='https://github.com/oe-fet/mercurygui.git',
    license='MIT',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    packages=find_packages(),
    package_data={
        'mercurygui': ['*.ui'],
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
        'mercuryitc',
        'numpy',
        'pyqtgraph_cx',
        'qtpy',
        'repr',
        'setuptools',
    ],
    zip_safe=False,
    keywords='mercurygui',
    classifiers=[
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    test_suite='tests',
    tests_require=[
    ]
)
