
"""
"""

class CondaDependenciesModel(QAbstractTableModel):
    """ """
    def __init__(self, parent, dic):
        super(CondaDependenciesModel, self).__init__(parent)
        self._parent = parent
        self._packages = dic
        self._rows = []
        self._bold_rows = []

        if len(dic) == 0:
            self._rows = [[_(u'Updating dependency list...'), u'']]
            self._bold_rows.append(0)
        else:
            if 'actions' in dic:
                dic = dic['actions']
            titles = {'FETCH': _('Packages to download'),
                      'UNLINK': _('Packages to unlink'),
                      'LINK': _('Packages to link'),
                      'EXTRACT': _('Packages to extract')
                      }
            order = ['FETCH', 'EXTRACT', 'LINK', 'UNLINK']
            row = 0

            for key in order:
                if key in dic:
                    self._rows.append([u(titles[key]), ''])
                    self._bold_rows.append(row)
                    row += 1
                    for item in dic[key]:
                        name, version, build = \
                            conda_api_q.split_canonical_name(item)
                        self._rows.append([name, version])
                        row += 1

    def flags(self, index):
        """Override Qt method"""
        if not index.isValid():
            return Qt.ItemIsEnabled
        column = index.column()
        if column in [0, 1]:
            return Qt.ItemFlags(Qt.ItemIsEnabled)
        else:
            return Qt.ItemFlags(Qt.NoItemFlags)

    def data(self, index, role=Qt.DisplayRole):
        """Override Qt method"""
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return to_qvariant()
        row = index.row()
        column = index.column()

        # Carefull here with the order, this has to be adjusted manually
        if self._rows[row] == row:
            name, size, = [u'', u'']
        else:
            name, size = self._rows[row]

        if role == Qt.DisplayRole:
            if column == 0:
                return to_qvariant(name)
            elif column == 1:
                return to_qvariant(size)
        elif role == Qt.TextAlignmentRole:
            if column in [0]:
                return to_qvariant(int(Qt.AlignLeft | Qt.AlignVCenter))
            elif column in [1]:
                return to_qvariant(int(Qt.AlignHCenter | Qt.AlignVCenter))
        elif role == Qt.ForegroundRole:
            return to_qvariant()
        elif role == Qt.FontRole:
            font = QFont()
            if row in self._bold_rows:
                font.setBold(True)
                return to_qvariant(font)
            else:
                font.setBold(False)
                return to_qvariant(font)
        return to_qvariant()

    def rowCount(self, index=QModelIndex()):
        """Override Qt method"""
        return len(self._rows)

    def columnCount(self, index=QModelIndex()):
        """Override Qt method"""
        return 2

    def row(self, rownum):
        """ """
        return self._rows[rownum]

