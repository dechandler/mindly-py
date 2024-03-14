"""
Custom exceptions

"""

class UnsupportedMindlyFileFormatVersion(Exception):
    """
    Error if Mindly starts using new data format versions

    """

class AmbiguousNamePath(Exception):
    """
    Error for multiple matches for a name path

    """

class NoSuchNodeError(Exception):
    """
    Error for having no matching nodes

    """
