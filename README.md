# mindly-py
Unofficial tooling to read and manipulate Mindly mind-map data


## Config


## Environment Variables

#### `MINDLY_CONF_PATH`
Sets path for YAML config file
Defaults to `~/.config/mindly/config.yaml ``





## Mindly object internal state

##### `Mindly.file_data`
Loaded contents of Mindly documents and index, to be modified and written back into the files
Keyed by filename
Do not overload with internal data - changes affect the files

##### `Mindly.nodes`
References to all sections, documents, and idea nodes in file_data
Keyed by node id
Do not overload with internal data - changes affect the files

##### `Mindly.structure`
Dictionary of nodes keyed by node id
Values are list of child node ids
Used to ease access to child/parent relationships

##### `Mindly.filename_by_id`
Dictionary of nodes keyed by node id
Values are the node's containing file
Used to mark relevant files for write when a node is updated


##### `Mindly.id_path` & `Mindly.name_path`

Path of each node, keyed by node id
A path is a list of lineage to address a node in the tree
It starts with the root of the node tree, up to the addressed node
id_path lists ancestors by id, and name_path

For example, the following heirarchy 
```
Items        id1
    Things   id2
        Eggs id3
    Stuff    id4
        Spam id5
Hamsters     id6
```
would result in
```
id_path = {  'id1': ["id1"], 'id2': ["id1", "id2"],
             'id3': ["id1", "id2", "id3"],
             'id4': ["id1", "id4"],
             'id5': ["id1", "id4", "id5"], 'id6': ["id6"]}

name_path = {'id1': ["Items"], 'id2': ["Items", "Things"],
             'id3': ["Items", "Things", "Eggs"],
             'id4': ["Items", "Stuff"],
             'id5': ["Items", "Stuff", "Spam"], 'id6': ["Hamsters"]}
```

##### `Mindly.proxy_filenames`
List of filenames in the proxy
Used to address document proxies in the index file
