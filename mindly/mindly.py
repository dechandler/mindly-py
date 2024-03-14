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

from .exceptions import ( UnsupportedMindlyFileFormatVersion,
                          AmbiguousNamePath,
                          NoSuchNodeError
                        )

class Mindly:  # pylint: disable=too-many-instance-attributes
    """
    Object to load and manipulate Mindly data files

    """
    def __init__(self, data_dir:str|os.PathLike):
        """
        Set initial state, then load Mindly data

        :param data_dir: path to Mindly data
        :type data_dir: str|os.PathLike

        """
        self.data_dir = data_dir

        # keys are filenames marked as having changes to be written
        self.files_modified = {}

        self._set_defaults()
        self._reset_state()

        self.load_files()


  # Methods for creating Mindly nodes

    def new_node(self,  # pylint: disable=too-many-arguments
        parent_id:str, text:str,
        idea_type:str="", note:str="",
        color:str="", color_theme_type:str=""
    ) -> dict:
        """
        Generic node creator

        """
        parent_depth = len(self.name_path[parent_id])
        if parent_depth == 0:
            return self.new_section(text)
        if parent_depth == 1:
            return self.new_document(
                text, section_id=parent_id, note=note, color=color
            )

        return self.new_idea(
            parent_id,
            text,
            note=note,
            idea_type=idea_type,
            color=color,
            color_theme_type=color_theme_type
        )

    def new_section(self, text:str) -> dict:
        """
        Creates a new section under the root node

        :param text: Title for the new Section
        :type text: str

        :returns: dict of section info
        :rtype: dict

        """
        section_id = self._gen_id()
        section = {
            'identifier': section_id,
            'text': text
        }
        self.file_data['mindly.index']['sections'].append(section)
        self.mark_modified("mindly.index")

        self.id_path[section_id] = [section_id]
        self.name_path[section_id] = [text]
        self.filename_by_id[section_id] = "mindly.index"

        return section

    def new_document(self, text:str, section_id:str,
        note:str="", color:str=""
    ) -> dict:
        """
        Creates a new document under the specified section

        :param text: Title/main node for the new document
        :type text: str

        :param section_id: ID of section to create the document under
        :type section_id: str

        :param note: Optional note for the node (Default: "")
        :type note: str

        :param color: Optional color for the node (Default: "blue0")
        :type color: str

        :returns: dict of document node info
        :rtype: dict

        """
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S %z")
        node_id = self._gen_id()
        filename = f"{self._gen_id()}.mndl"

        # Configure the proxy in the index
        proxy = dict(self.proxy_defaults)
        proxy.update({
            'dateCreated': now,
            'dateModified': now,
            'itemCount': 1,
            'identifier': node_id,
            'section': section_id,
            'filename': filename,
            'text': text,
            'color': color or self.proxy_defaults['color']
        })
        self.file_data['mindly.index']['proxies'].append(proxy)
        self.proxy_filenames.append(filename)

        # Configure the new document file and populate with root idea node
        self.file_data[filename] = {
            'fileFormatVersion': 4,
            'dateCreated': now,
            'dateModified': now
        }
        idea = dict(self.idea_defaults)
        options = {'note': note, 'color': color}
        idea.update({ k: v for k, v in options.items() if v })
        idea.update({'text': text, 'identifier': node_id})
        self.file_data[filename]['idea'] = idea
        self.nodes[node_id] = idea

        self.mark_modified(filename)

        self.id_path[idea['identifier']] = [section_id, idea['identifier']]
        self.name_path[idea['identifier']] = [
            self.nodes[section_id]['text'], text
        ]
        self.filename_by_id[node_id] = filename

        return self.file_data[filename]['idea']

    def new_idea(self,  # pylint: disable=too-many-arguments
        parent_id:str, text:str,
        idea_type:str="", note:str="",
        color:str="", color_theme_type:str=""
    ) -> dict:
        """
        Creates an idea node under a document or other idea node

        :param parent_id: ID of the parent node the new node is to be created under
        :type parent_id: str

        :param text: Title new idea node
        :type text: str

        :param note: Optional note for the node (Default: "")
        :type note: str

        :param color: Optional color for the node (Default: "blue0")
        :type color: str

        :returns: dict of new node info
        :rtype: dict

        """
        if 'ideas' not in self.nodes[parent_id].keys():
            self.nodes[parent_id]['ideas'] = []

        idea_id = self._gen_id()
        idea = {
            'text': text,
            'identifier': idea_id,
            'note': note,
            'ideaType': idea_type or self.idea_defaults['ideaType'],
            'ideas': [],
            'color': (
                color
                or self.nodes.get(parent_id, {}).get('color')
                or self.idea_defaults['color']
            ),
            'colorThemeType': (
                color_theme_type
                or self.nodes.get(parent_id, {}).get('colorThemeType')
                or self.idea_defaults['colorThemeType']
            )
        }
        self.nodes[parent_id]['ideas'].append(idea)
        self.nodes[idea_id] = idea

        # Increment document item count in index
        filename = self.filename_by_id[parent_id]
        i = self.proxy_filenames.index(filename)
        self.file_data['mindly.index']['proxies'][i]['itemCount'] += 1

        self.mark_modified(self.filename_by_id[parent_id])

        self.id_path[idea_id] = self.id_path[parent_id] + [idea_id]
        self.name_path[idea_id] = self.name_path[parent_id] + [text]
        self.filename_by_id[idea_id] = filename

        return idea


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

    def _gen_id(self) -> str:
        """
        Generates an id in the style of Mindly's native convention,
        excepting that a random 3-digit int is used instead of Mindly's
        incrementing index number

        :returns: ID string
        :rtype: str

        """
        return f"id{datetime.now().strftime("%s")}_{random.randint(100, 999)}"


  # Lookup methods

    def get_node_id_by_name_path(self, name_path:list) -> str:
        """
        Get a single node matching name_path, and raise exceptions
        if there are more or no results

        :param name_path: list of node lineage
        :type name_path: list

        :returns: id of single node corresponding to path
        :rtype: str

        :raises AmbiguousNamePath: multiple nodes match the name path

        :raises NoSuchNodeError: no matching nodes

        """
        matches = self.get_name_path_matches(name_path)
        if len(matches) > 1:
            raise AmbiguousNamePath(f"No duplicate names! {matches}")
        if not matches:
            raise NoSuchNodeError(f"No match for {name_path}")

        return matches[0]

    def get_name_path_matches(self, name_path: list) -> list:
        """
        Get all nodes matching the name path

        :param name_path:
        :type name_path: list

        :returns: list of matching nodes

        """
        return [
            node_id
            for node_id, node_path in self.name_path.items()
            if node_path == name_path
        ]

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
