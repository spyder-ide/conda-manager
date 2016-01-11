# -*- coding:utf-8 -*-
#
# Copyright © 2015 The Spyder Development Team
# Copyright © 2014 Gonzalo Peña-Castellanos (@goanpeca)
#
# Licensed under the terms of the MIT License

"""
MultiColumnSortFilterProxy Implements a QSortFilterProxyModel that allows for
custom filtering on several columns.
"""

# Third party imports
from qtpy.QtCore import QSortFilterProxyModel

# Local imports
from conda_manager.utils import constants


class MultiColumnSortFilterProxy(QSortFilterProxyModel):
    """Implements a QSortFilterProxyModel that allows for custom filtering.

    Add new filter functions using add_filter_function(). New functions should
    accept two arguments, the column to be filtered and the currently set
    filter string, and should return True to accept the row, False otherwise.

    Filter functions are stored in a dictionary for easy removal by key. Use
    the add_filter_function() and remove_filter_function() methods for access.

    The filterString is used as the main pattern matching string for filter
    functions. This could easily be expanded to handle regular expressions if
    needed.

    Copyright https://gist.github.com/dbridges/4732790
    """
    def __init__(self, parent=None):
        super(MultiColumnSortFilterProxy, self).__init__(parent)
        # if parent is stored as self.parent then PySide gives the following
        # TypeError: 'CondaPackagesTable' object is not callable
        self._parent = parent
        self._filter_string = ''
        self._filter_status = constants.ALL
        self._filter_functions = {}

    def set_filter(self, text, status):
        """
        text : string
            The string to be used for pattern matching.
        status : int
            TODO: add description
        """
        self._filter_string = text.lower()
        self._filter_status = status
        self.invalidateFilter()

    def add_filter_function(self, name, new_function):
        """
        name : hashable object
            The object to be used as the key for
            this filter function. Use this object
            to remove the filter function in the future.
            Typically this is a self descriptive string.

        new_function : function
            A new function which must take two arguments,
            the row to be tested and the ProxyModel's current
            filterString. The function should return True if
            the filter accepts the row, False otherwise.

            ex:
            model.add_filter_function(
                'test_columns_1_and_2',
                lambda r,s: (s in r[1] and s in r[2]))
        """
        self._filter_functions[name] = new_function
        self.invalidateFilter()

    def remove_filter_function(self, name):
        """Removes the filter function associated with name, if it exists.

        name : hashable object
        """
        if name in self._filter_functions.keys():
            del self._filter_functions[name]
            self.invalidateFilter()

    def filterAcceptsRow(self, row_num, parent):
        """Qt override.

        Reimplemented from base class to allow the use of custom filtering.
        """
        model = self.sourceModel()

        # The source model should have a method called row()
        # which returns the table row as a python list.
        tests = [func(model.row(row_num), self._filter_string,
                 self._filter_status) for func in
                 self._filter_functions.values()]

        return False not in tests  # Changes this to any or all!
