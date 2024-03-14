"""
CLI interface

"""
#import argparse
import os
import sys

import yaml

from .mindly import Mindly

class CliInterface:
    """
    Generic CLI interface, using .handle_args() to provide
    a structure

    """
    help_message = "TODO: Make Help"
    default_operation = 'help'
    operations = {}

    def handle_args(self, args):
        """
        Determines the subcommand being invoked in the given
        args, then passes along remaining arguments to its
        handler function

        :params args: cli argument list
        :type args: list

        """
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

        if not args or args[0] not in subcommands:
            args = [self.default_operation] + args

        self.op_name = args.pop(0)  # pylint: disable=attribute-defined-outside-init
        subcommands[self.op_name]['handler'](args)


    def print_help(self, args):  # pylint: disable=unused-argument
        """
        Default handler for printing the help message

        :params args: list of args

        """
        print(self.help_message)



class MindlyCli(CliInterface):
    """
    Load config and define main subcommands and their handlers

    """
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


    def _get_config(self) -> dict:
        """
        Determines the Mindly config path,
        loads and processes it, and returns
        the ready-to-use config dict

        :returns: config data, loaded from file and processed
        :rtype: dict

        """
        conf_path = ( os.path.expanduser(os.environ.get('MINDLY_CONF_PATH', ""))
                      or os.path.expanduser("~/.config/mindly/config.yaml")
                    )

        with open(conf_path, 'r', encoding='utf-8') as fh:
            config = yaml.safe_load(fh)

        # Expanduser for certain config options
        for key in ['mindly_data_dir']:
            if isinstance(config.get(key), str):
                config[key] = os.path.expanduser(config[key])

        return config

    def ls(self, args):
        """
        Print the Mindly data in various formats

        subcommands: [paths|nodes|files] (default: paths)

        :param args: relevant argv
        :type args: list

        """
        if not args:
            args.append('paths')

        if args[0] == 'paths':
            for node_id, name_path in self.mindly.name_path.items():
                print(f"'{node_id}': {name_path}")
        elif args[0] == 'nodes':
            for node_id, node_info in self.mindly.nodes.items():
                print(f"'{node_id}': {node_info}")
        elif args[0] == 'files':
            print(self.mindly.file_data)


def main():
    try:
        MindlyCli(sys.argv[1:])
        return 0
    except KeyboardInterrupt:
        return 1

sys.exit(main())
