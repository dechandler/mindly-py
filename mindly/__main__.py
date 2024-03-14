"""
CLI interface

"""
import argparse
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
        # Add help operation
        self.operations['help'] = (
            self.operations.get('help')
            or {'handler': self.print_help}
        )

        # Combine subcommand names and aka values to
        # build a comprehensive operations spec
        subcommands = {}
        for name, op in self.operations.items():
            for op_name in op.get('aka', []) + [name]:
                subcommands[op_name] = {
                    'name': name,
                    'handler': op['handler']
                }

        # If no matching subcommand, use the default
        # operation and set it up to get all args
        # passed to its handler
        if not args or args[0] not in subcommands:
            args = [self.default_operation] + args

        # Remove the subcommand and pass the remaining
        # args to the selected handler
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
    help_message = """
        mindlycli [print|new-node] <subcommand args>

    """
    def __init__(self, args):
        """
        Load config, load Mindly data,
        setup operations, pass args to handler

        :param args: arguments to mindlycli command
        :type args: list

        """
        self.conf = self._get_config()
        self.mindly = Mindly(self.conf.get('mindly_data_dir'))

        self.operations = {
            'print': {
                'aka': ['ls'],
                'handler': self.print
            },
            'new-node': {
                'aka': ['new'],
                'handler': self.new_node
            },
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


    def _normalize_name_path_arg(self, name_path_arg:str) -> list:
        """
        Convert a string version of name_path into the full list
        The string is basically path-like - "/path/to/nodes and things"
        But the first character is generically the delimter,
          so this also works: "|path|to|nodes/things"

        :param name_path_arg: string version of a name_path
        :type name_path_arg: str

        """
        if not name_path_arg:
            return []

        delimeter = name_path_arg[0]
        return name_path_arg.split(delimeter)[1:]



    def print(self, args:list) -> None:
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


    def new_node(self, args:list) -> None:
        """
        Create a new node - section, document, or idea

        If --parent-id and --parent-name-path are both
        unspecified, parent will be the root node, so
        creating a new section

        :param args: relevant argv to be parsed by argparse
        :type args: list

        """
        parser = argparse.ArgumentParser(prog='mindly_new_node')
        arg = parser.add_argument
        arg("--parent-id")
        arg("--parent-name-path")

        arg("--text", required=True)
        arg("--note", default="")
        arg("--idea-type", default="")
        arg("--color", default="")
        arg("--color-theme-type", default="")
        parsed_args = parser.parse_args(args=args)

        base_dir = self.conf.get('mindly_data_dir')
        self.mindly = Mindly(base_dir)

        if parsed_args.parent_id:
            parent_id = parsed_args.parent_id
        elif parsed_args.parent_name_path:
            normalized = self._normalize_name_path_arg(parsed_args.parent_name_path)
            parent_id = self.mindly.get_node_id_by_name_path(normalized)
        else:
            parent_id = '__root'

        print(self.mindly.new_node(
            parent_id,
            parsed_args.text,
            note=parsed_args.note,
            idea_type=parsed_args.idea_type,
            color=parsed_args.color,
            color_theme_type=parsed_args.color_theme_type
        ))
        self.mindly.write()




def main():
    """
    Main function to be called by script file generated
    in PATH during install

    """
    try:
        MindlyCli(sys.argv[1:])
        return 0
    except KeyboardInterrupt:
        return 1

sys.exit(main())
