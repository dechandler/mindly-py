"""
Core module for reading and manipulating Mindly files

"""
import json
import os
#import pathlib
import random
#import sys
import zlib

from datetime import datetime, timezone

from .exceptions import UnsupportedMindlyFileFormatVersion

class Mindly:  # pylint: disable=too-many-instance-attributes
    """
    Object to load and manipulate Mindly data files

    """
    def __init__(self, data_dir:str|os.PathLike):

        self.data_dir = data_dir

        # keys are filenames marked as having changes to be written
        self.files_modified = {}

        self._set_defaults()
        self._reset_state()

        self.load_files()

    def _gen_id(self) -> str:
        """
        Generates an id in the style of Mindly's native convention,
        excepting that a random 3-digit int is used instead of Mindly's
        incrementing index number

        :returns: ID string
        :rtype: str

        """
        return f"id{datetime.now().strftime("%s")}_{random.randint(100, 999)}"



  # Common operations for writing

    def mark_modified(self, filename:str) -> None:
        """
        Marks the filename as having changes that need to be written
        to disk in the next call to Mindly.write()

        The index is assumed for all changes

        :param filename: Filename in base_dir
        :type filename: str

        """
        self.files_modified[filename] = True
        if filename == "mindly.index":
            return

        mtime = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S %z")
        self.file_data[filename]['dateModified'] = mtime

        pos = self.proxy_filenames.index(filename)
        self.file_data["mindly.index"]['proxies'][pos]['dateModified'] = mtime

        self.mark_modified("mindly.index")

    def write(self) -> None:
        """
        Write staged changes to file

        """
        for filename in [ k for k, v in self.files_modified.items() if v ]:

            document = self.file_data[filename]
            path = os.path.join(self.data_dir, filename)

            if filename == "mindly.index":
                with open(path, 'w', encoding='utf-8') as fh:
                    json.dump(document, fh)
                    return

            with open(path, 'wb') as fh:
                fh.write(zlib.compress(bytes(
                    json.dumps({
                        'ideaDocumentDataObject': document
                    }), 'utf-8'
                )))

        self.files_modified = {}

  # Load files into internal state

    def _set_defaults(self) -> None:

        self.proxy_defaults = {
            'section': '',
            'hasNote': False,
            'hasWebLink': False,
            'color': "blue0"
        }
        self.idea_defaults = {
            'ideaType': 1,
            'note': '',
            'color': "blue0",
            'colorThemeType': 0
        }

    def load_files(self) -> None:
        """
        Sets internal data to empty, then runs setup methods
        to populate them from Mindly files in data_dir

        Is run in __init__ and can be called to reset and reload

        """
        # Set empty internal data
        self._reset_state()

        # Populate internal data
        self._load_index()
        self._load_sections()
        self._load_documents()

    def _reset_state(self) -> None:
        """
        Reset internal data
        The internal data structures are documented more
        extensively in the README

        file_data, nodes
          The contents of files and changes to be written
          Do not overload with internal data

        structure, filename_by_id, proxy_filenames
          Data about how pieces fit together
          Keyed by node id

        id_path, name_path, proxy_filenames
          Data about how nodes can be addressed
          Keyed by node id

        """
        self.file_data = {}
        self.nodes = {}
        self.structure = {'__root': []}
        self.proxy_filenames = []
        self.id_path = {}
        self.name_path = {'__root': []}
        self.filename_by_id = {}

    def _load_index(self) -> None:
        """
        Load {data_dir}/mindly.index to populate
          self.file_data['mindly.index']

        """
        index_path = os.path.join(self.data_dir, "mindly.index")
        with open(index_path, 'r', encoding='utf-8') as fh:
            self.file_data['mindly.index'] = json.load(fh)

        version = self.file_data['mindly.index'].get('fileFormatVersion')
        if version != 2:
            raise UnsupportedMindlyFileFormatVersion(
                f"Index Version {version} not supported\nSupported Versions: [2]"
            )

    def _load_sections(self) -> None:
        """
        Populate self.nodes with sections in the index file

        """
        sections = {}

        for section in self.file_data['mindly.index']['sections']:
            section_id = section['identifier']
            self.id_path[section_id] = [section_id]
            self.name_path[section_id] = [section['text']]

            # Sections are children of imaginary '__root' node
            self.structure['__root'].append(section_id)
            self.structure[section_id] = []
            sections[section_id] = section

        self.nodes.update(sections)


    def _load_documents(self) -> None:
        """
        Populate self.nodes with nodes in documents referenced
          by the index file

        #todo: load unreferenced mndl files and populate index
               this mirrors Mindly's behavior

        """
        for proxy in self.file_data['mindly.index']['proxies']:
            section_id = proxy.get('section', '')
            self.structure[section_id].append(proxy['identifier'])

            self.proxy_filenames.append(proxy['filename'])

            self.nodes.update(self._load_ideas_document(
                proxy['filename'], [section_id, proxy['identifier']]
            ))


    def _load_ideas_document(self,
        filename:str|os.PathLike, id_path:list
    ) -> dict:
        """
        Load a document and return extracted idea node data


        :param filename: filename of the document
        :type filename: str|os.PathLike

        :param id_path:
        :type id_path: str

        """
        path = os.path.join(self.data_dir, filename)
        with open(path, 'rb') as fh:
            self.file_data[filename] = json.loads(
                zlib.decompress(fh.read())
            )['ideaDocumentDataObject']

        version = self.file_data[filename].get('fileFormatVersion')
        if version != 4:
            raise UnsupportedMindlyFileFormatVersion(
                f"Ideas Version {version} not supported\nSupported Versions: [4]"
            )

        nodes = self._extract_nodes(self.file_data[filename]['idea'], id_path)
        self.filename_by_id.update({
            node_id: filename for node_id in nodes
        })
        return nodes

    def _extract_nodes(self, node:dict, id_path:list) -> dict:
        """
        Recurses into lists of sub-ideas to return a flattened
        list of idea nodes

        :param node: Dict of nested idea node data 
        :type node: dict

        :param id_path: List of ids corresponding to the current
                          node's ancestry
                        See Mindly.id_path & Mindly.name_path
                          in the README for further discussion
        :type id_path: list

        :returns: dict keyed by node id, with values as node data
                    linked to the Mindly document
        :rtype: dict

        """
        node_id = node['identifier']

        nodes = {node_id: node}
        self.id_path[node_id] = id_path
        self.name_path[node_id] = self.name_path[id_path[-2]] + [node['text']]

        if not node.get('ideas'):
            return nodes

        self.structure[node_id] = []

        for idea in node['ideas']:
            self.structure[node_id].append(idea['identifier'])
            nodes.update(self._extract_nodes(
                idea, id_path + [idea['identifier']]
            ))

        return nodes
