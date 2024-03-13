
import argparse
import os
import sys

import yaml

from .mindly import Mindly

class CliInterface:

    help_message = "TODO: Make Help"
    default_operation = 'help'
    operations = {}

    def handle_args(self, args):

        self.operations['help'] = (
            self.operations.get('help')
            or {'handler': self.print_help}
        )

        subcommands = {}
        for name, op in self.operations.items():
            for op_name in op.get('aka', []) + [name]:
                subcommands[op_name] = {
                    'name': name,
                    'handler': op['handler']
                }

        if not args or args[0] not in subcommands.keys():
            args = [self.default_operation] + args

        self.op_name = args.pop(0)
        subcommands[self.op_name]['handler'](args)


    def print_help(self, args):

        print(self.help_message)



class MindlyCli(CliInterface):

    def __init__(self, args):

        self.conf = self._get_config()
        self.mindly = Mindly(self.conf.get('mindly_data_dir'))

        self.operations = {
            'print': {
                'aka': ['ls'],
                'handler': self.ls
            }
        }
        self.handle_args(args)


    def _get_config(self):

        conf_path = ( os.path.expanduser(os.environ.get('MINDLY_CONF_PATH', ""))
                      or os.path.expanduser("~/.config/mindly/config.yaml")
                    )

        with open(conf_path) as fh:
            config = yaml.safe_load(fh)

        for key in ['mindly_data_dir']:
            if type(config.get(key)) == str:
                config[key] = os.path.expanduser(config[key])

        return config

    def ls(self, args):

        print(self.mindly.nodes)
