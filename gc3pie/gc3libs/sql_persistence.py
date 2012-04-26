#! /usr/bin/env python
#
"""
"""
# Copyright (C) 2011, GC3, University of Zurich. All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
"""This file implements an SQL-based persistency driver to store
GC3pie objects in a SQL DB instead of using Pickle from
`persistent.FilesystemStore` class"""

__docformat__ = 'reStructuredText'
__version__ = '$Revision$'

from gc3libs.persistence import Store, IdFactory
from gc3libs.utils import same_docstring_as
import gc3libs.exceptions
from gc3libs import Task

import cPickle as pickle
import sqlalchemy

class DummyObject:
    pass


def sql_next_id_factory(db):
    """
    This function will return a function which can be used as
    `next_id_fn` argument for the `IdFactory` class constructor.

    `db` is DB connection class conform to DB API2.0 specs

    The function returned has signature:

        sql_next_id(n=1)

    the id returned is the maximum `id` field in the `store` table plus
    1.
    """
    def sql_next_id(n=1):
        q = db.execute('select max(id) from store')
        nextid = q.fetchone()[0]
        if not nextid: nextid = 1
        else: nextid = int(nextid)+1
        return nextid
    
    return sql_next_id


class IntId(int):
    def __new__(cls, prefix, seqno):
        return int.__new__(cls, seqno)

    def __getnewargs__(self):
        return (None, int(self))

class SQL(Store):
    """
    Save and load objects in a SQL db. Uses Python's `pickle` module
    to serialize objects and parse the `Url` object to define the
    driver to use (`sqlite`, `MySQL`, `postgres`...), db, and
    optionally user and password.    

    >>> import tempfile, os
    >>> (fd, name) = tempfile.mkstemp()
    >>> from gc3libs.url import Url
    >>> url = Url('sqlite:///%s' % name)
    >>> db = SQL(url)
    >>> from sql_persistence import DummyObject
    >>> obj = DummyObject()
    >>> obj.x = 'test'
    >>> db.save(obj)
    1
    >>> db.list()
    [1]
    >>> db.save(obj)
    1
    >>> del obj
    >>> y = db.load(1)
    >>> y.x
    'test'
    
    >>> import os
    >>> os.remove(name)
    """
    def __init__(self, url, idfactory=None):
        """
        Open a connection to the storage database identified by
        url. It will use the correct backend (MySQL, psql, sqlite3)
        based on the url.scheme value
        """
        # if url.scheme not in DRIVERS:
        #     raise NotImplementedError("DB Driver %s not supported" % url.scheme)

        # gc3libs.url.Url is not RFC compliant, check issue http://code.google.com/p/gc3pie/issues/detail?id=261
        if url.scheme in ('file', 'sqlite'):
            url = "%s://%s/%s" % (url.scheme, url.netloc, url.path)
        self.__engine = sqlalchemy.create_engine(str(url))

        self.__meta = sqlalchemy.MetaData(bind=self.__engine)
        self.__meta.reflect()
        self.extra_fields = ()
        # check if database has 'store' table
        if 'store' not in self.__meta.tables:
            from sqlalchemy import Column, INTEGER, BLOB, VARCHAR, TEXT, Table
            
            table = Table(
                'store',
                self.__meta,
                Column(u'id', INTEGER(), primary_key=True, nullable=False),
                Column(u'data', BLOB()),
                Column(u'type', VARCHAR(length=128)),
                Column(u'jobid', VARCHAR(length=128)),
                Column(u'jobname', VARCHAR(length=255)),
                Column(u'jobstatus', VARCHAR(length=128)),
                )
            self.__meta.create_all()
        else:

            self.extra_fields = (i for i in self.__meta.tables['store'].columns.keys() if i not in ('id', 'data', 'type', 'jobid', 'jobname', 'jobstatus'))


        self.idfactory = idfactory
        if not idfactory:
            self.idfactory = IdFactory(next_id_fn=sql_next_id_factory(self.__engine), id_class=IntId)
            
    @same_docstring_as(Store.list)
    def list(self):
        c = self.__engine
        q = c.execute('select id from store')
        ids = [i[0] for i in q.fetchall()]
        return ids

    @same_docstring_as(Store.replace)
    def replace(self, id_, obj):
        self._save_or_replace(id_, obj, 'replace')
                              
    # copied from FilesystemStore
    @same_docstring_as(Store.save)
    def save(self, obj):
        if not hasattr(obj, 'persistent_id'):
            obj.persistent_id = self.idfactory.new(obj)
        return self._save_or_replace(obj.persistent_id, obj, 'save')

    def _save_or_replace(self, id_, obj, action):
        c = self.__engine


        pdata = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL).encode('base64')
        # insert into db
        otype = ''
        extra_fields = {}
            
        for i in self.extra_fields:
            if hasattr(obj, i):
                extra_fields[i] = getattr(obj, i)

        if isinstance(obj, Task):
            otype = 'job'
            extra_fields['jobstatus'] = obj.execution.state
            if hasattr(obj.execution, 'lrms_jobid'):
                extra_fields['jobid'] = SQL.escape(obj.execution.lrms_jobid)
            extra_fields['jobname'] = SQL.escape(obj.jobname)

            
        query = "select id from store where id=%d" % id_
        q = c.execute(query)
        if not q.fetchone():
            extras = extra_fields.items()            
            kline = (i[0] for i in extras)
            kline = ","+", ".join(kline) if extras else ""
            vline = ("'%s'" % SQL.escape(str(i[1])) for i in extras)
            vline = ","+", ".join(vline) if extras else ""

            query = """insert into store ( \
id, data, type %s) \
values (%d, '%s', '%s' %s)""" % (
kline, id_, pdata, otype, vline )
            # gc3libs.log.debug("Executing query `%s`" % query)
            q = c.execute(query)
            
        else:
            extra = "," + ", ".join("%s='%s'" % (i[0], SQL.escape(str(i[1]))) for i in extra_fields.iteritems()) if extra_fields else ""
            query = """update store set  \
data='%s', type='%s' %s \
where id=%d""" % (pdata,otype, extra, id_)
            # gc3libs.log.debug("Executing query `%s`" % query)
            q = c.execute(query)
        obj.persistent_id = id_

        # return id
        return obj.persistent_id

    @same_docstring_as(Store.load)
    def load(self, id_):
        c = self.__engine
        q = c.execute('select data  from store where id=%d' % id_)
        rawdata = q.fetchone()
        if not rawdata:
            raise gc3libs.exceptions.LoadError("Unable to find object %d" % id_)
        data = pickle.loads(rawdata[0].decode('base64'))
        return data

    @same_docstring_as(Store.remove)
    def remove(self, id_):
        self.__engine.execute('delete from store where id=%d' % id_)

    @staticmethod
    def escape(s):
        """escape string `s` so that it can be used in a sql query.

        Please note that for now we only escape "'" chars because of
        the queries we are doing, thus this function is not at all a
        fully-featured SQL escaping function!

        >>> SQL.escape("Antonio's boat")
        "Antonio''s boat"
        >>> SQL.escape(u"Antonio's unicode boat")
        u"Antonio''s unicode boat"
        >>> SQL.escape(9)
        9
        
        """
        if hasattr(s, 'replace'):
            return s.replace("'", "''")
        else:
            return s
        
## main: run tests

if "__main__" == __name__:
    import doctest
    doctest.testmod(name="sql_persistence",
                    optionflags=doctest.NORMALIZE_WHITESPACE)
