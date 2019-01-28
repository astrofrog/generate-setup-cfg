#!/usr/bin/env python

# Script to generate setup.cfg files based on metadata in setup.py. This works
# by running egg_info then reading the information from there (since setup.py
# can be highly unstructured)

import os
import sys
import glob
import subprocess
from collections import defaultdict
from configparser import ConfigParser
from pkginfo import Develop
from collections import OrderedDict

class handler:
    def __init__(self, setup_cfg_name):
        self.setup_cfg_name = setup_cfg_name


class long_description_handler(handler):
    def serialize(self, value):
        if os.path.exists('README.rst'):
            return 'file: README.rst'
        else:
            return None


class str_handler(handler):
    def serialize(self, value):
        if value is None:
            return None
        else:
            return str(value)


class list_comma_handler(handler):

    def __init__(self, setup_cfg_name, newline=False):
        super().__init__(setup_cfg_name)
        self.newline = newline

    def serialize(self, values):
        if isinstance(values, str):
            values = values.split(',')
        if values is None or len(values) == 0 or values == ['UNKNOWN']:
            return None
        else:
            if self.newline:
                return os.linesep + os.linesep.join(values)
            else:
                return ', '.join(values)


METADATA_KEYS = {'name': str_handler('name'),
                 'version': str_handler('version'),
                 'home_page': str_handler('url'),
                 'download_url': str_handler('download_url'),
                 'author': str_handler('author'),
                 'author_email': str_handler('author_email'),
                 'maintainer': str_handler('maintainer'),
                 'maintainer_email': str_handler('maintainer_email'),
                 'classifiers': list_comma_handler('classifiers', newline=True),
                 'license': str_handler('license'),
                 'summary': str_handler('description'),
                 'description': long_description_handler('long_description'),
                 'keywords': list_comma_handler('keywords'),
                 'platforms': list_comma_handler('platforms'),
                 'provides': list_comma_handler('provides'),
                 'requires': list_comma_handler('requires'),
                 'obsoletes': list_comma_handler('obsoletes')
                 }


def main():

    # Start off by running egg_info
    subprocess.call([sys.executable, 'setup.py', 'egg_info'])

    # Check that only one egg-info directory exists
    egg_info_dir = glob.glob('*.egg-info')
    if len(egg_info_dir) != 1:
        print("Expected only one .egg-info directory, got {0}".format(egg_info_dir))
        sys.exit(1)
    else:
        egg_info_dir = egg_info_dir[0]

    # Read in any existing setup.cfg file (this will just create an empty
    # configuration if the file doesn't exist yet)
    conf = ConfigParser()
    conf.read('setup.cfg')

    # Add required sections

    if not conf.has_section('metadata'):
        conf.add_section('metadata')

    if not conf.has_section('options'):
        conf.add_section('options')

    # Parse the PKG-INFO file
    dist = Develop('.')

    # Populate the metadata
    for key, handler in METADATA_KEYS.items():
        translated = handler.serialize(getattr(dist, key))
        if translated is not None:
            conf.set('metadata', handler.setup_cfg_name, translated)

    # Populate the options
    conf.set('options', 'zip_safe', str(not os.path.exists(os.path.join(egg_info_dir, 'not-zip-safe'))))
    conf.set('options', 'packages', 'find:')
    conf.set('options', 'include_package_data', str(True))
    if dist.requires_python is not None:
        conf.set('options', 'python_requires', dist.requires_python)

    # Check entry points, if they exist
    if os.path.exists(os.path.join(egg_info_dir, 'entry_points.txt')):

        # Entry points are stored in a file that has a config-compatible syntax
        entry = ConfigParser()
        entry.read(os.path.join(egg_info_dir, 'entry_points.txt'))

        if not conf.has_section('options.entry_points'):
            conf.add_section('options.entry_points')

        for section in entry.sections():
            entry_points = []
            for item in entry[section]:
                entry_points.append('{0} = {1}'.format(item, entry[section][item]))
            conf.set('options.entry_points', section, os.linesep + os.linesep.join(entry_points))

    # Check install and extras requirements
    if os.path.exists(os.path.join(egg_info_dir, 'requires.txt')):

        # The syntax is
        #
        # install requirements, one per line
        #
        # [extra name]
        # requirements, one per line
        #
        # [another extra name]
        # etc.

        with open(os.path.join(egg_info_dir, 'requires.txt')) as f:
            requires = defaultdict(list)
            section = 'default'
            for req in f:
                if req.startswith('['):
                    section = req.strip()[1:-1]
                elif req.strip() != '':
                    requires[section].append(req.strip())

            conf.set('options', 'install_requires', os.linesep + os.linesep.join(requires['default']))

            # If there are more than one entries in the requires dict, there are some extras
            if len(requires) > 1:
                if not conf.has_section('options.extras_require'):
                    conf.add_section('options.extras_require')
                for section in sorted(requires):
                    if section != 'default':
                        conf.set('options.extras_require', section, '; '.join(requires[section]))

    # Sort the sections
    def sections_key(section):
        if section == 'metadata':
            return 'a'
        elif section == 'options':
            return 'b'
        elif section.startswith('options'):
            return 'c' + section
        else:
            return 'd'
    conf._sections = OrderedDict([(section, conf._sections[section]) for section in sorted(conf._sections, key=sections_key)])

    with open('setup.cfg', 'w') as f:
        conf.write(f)


if __name__ == "__main__":
    main()
