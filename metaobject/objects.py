#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# metaobject
# Copyright (c) 2014, Andrew Robbins, All rights reserved.
# 
# This library ("it") is free software; it is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; you can redistribute it and/or modify it under the terms of the
# GNU Lesser General Public License ("LGPLv3") <https://www.gnu.org/licenses/lgpl.html>.
'''
metaobject - A Meta-Object protocol library
'''
from __future__ import absolute_import
import json
import logging
import collections
from datetime import datetime

logger = logging.getLogger(__name__)

def object_to_json(obj, dict_class=dict):
    if obj is None:
        return None

    if isinstance(obj, collections.Mapping):
        return obj

    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, MetaObject):
        d = dict_class()
        for k, v in obj.items():
            if isinstance(v, MetaObject):
                v = object_to_json(v, dict_class=dict_class)
            elif isinstance(v, list):
                v = map(lambda x: object_to_json(x, dict_class=dict_class), v)
            d[k] = v
        return d

    if hasattr(obj, 'to_json') and obj.to_json:
        try:
            rep = obj.to_json(dict_class=dict_class)
        except:
            rep = obj.to_json()
        return rep

    logger.error("Unknown error serializing %s %s" % (type(obj), repr(obj).encode('ascii', 'ignore')))
    raise ValueError("object_to_json could not serialize object")

class MetaObject(object):

    _required = ()      # a list of required attributes.

    _optional = {}      # a dictionary of optional attributes along with their default values.

    _compared = ()      # a list of attributes to be used for comparison, defaults to _required

    _printed = ()       # a list of attributes to be used for debugging, defaults to _required
                        # any attribute name starting with an underscore is omitted.

    _unlisted = None    # what do we do with an unlisted attribute: None, 'del', 'raise'

    _types = {}         # a dictionary of types, each attribute defaults to object.
                        # Any value given in kwargs will be converted to the given type
                        # and then will be assigned to the attribute on the instance.
                        # Any attribute may also be a list type, denoted `[<type>]`, 
                        # which indicates that the value must be given as a list as well.
                        #
                        # For example: attribute "names": [models.Name],
                        #    will set self.names = map(models.Name, kwargs["names"])
                        #
                        # For example: attribute "customer": models.Customer,
                        #    will set self.customer = models.Customer(kwargs["customer"])
                        # 
                        # For example: attribute "age": int,
                        #    will set self.age = int(kwargs["age"])
                        #

    def __init__(self, obj=None):
        if isinstance(obj, dict):
            # dict constructor
            kwargs = dict(obj)
        elif hasattr(obj, '__dict__'):
            # copy constructor
            kwargs = dict(vars(obj))
        elif obj == None:
            # default constructor
            kwargs = self._optional
        else:
            raise TypeError("expected dict or object: %r" % type(obj))

        # make sure that all keys are binary strings
        kwargs = self._ununicode(kwargs)

        # ensure that all required attributes are in given attributes
        for attr in self._required:
            if attr not in kwargs.keys():
                raise AttributeError("missing attribute: %s from %s" % (attr, obj))

        # handle any attributes given that are neither required or optional
        if self._unlisted:
            for attr in kwargs.keys():
                if not attr in self._listed:
                    if self._unlisted == 'del':
                        del kwargs[attr]
                    elif self._unlisted == 'raise':
                        raise AttributeError("unlisted attribute: %s" % attr)

        self.__dict__.update(self._optional)
        self.__dict__.update(kwargs)    # specific attributes override optional values

        # ensure that all typed attributes are created
        for attr, cls in self._types.items():
            value = getattr(self, attr)
            typed_value = self._instantiate(cls, attr, value)
            setattr(self, attr, typed_value)

        self._reserved = ['_reserved', '_required', '_optional', '_listed', '_changed', '_compared', '_types', '_unlisted', '_printed']
        self._compared = self._compared or self._required
        self._printed = self._printed or self._required

        return

    @staticmethod
    def _ununicode(kwargs):
        for key in kwargs.keys():
            if isinstance(key, unicode):
                value = kwargs[key]
                del kwargs[key]
                key = str(key)
                kwargs[key] = value
        return kwargs

    @staticmethod
    def _instantiate(cls, attr, value):
        try:
            typed_value = None
            if isinstance(cls, (list, tuple)):
                typed_value = map(cls[0], value) if value is not None else [] # create a list of cls objects
            else:
                typed_value = cls(value) if value is not None else cls() # create a cls object
        except:
            logger.error("MetaObject._instantiate(%s, %s, %s)" % (repr(cls), repr(attr), repr(value)))
            raise
        return typed_value

    #def __iter__(self, obj=None):
    #    return iter(self._listed)

    #def __dict__(self):
    #    return

    def __eq__(self, other):
        if type(self) != type(other):
            return False

        return dict(self._compared_items()) == dict(other._compared_items())

    #def __ne__(self, other):
    #    return not self.__eq__(other)

    def _equiv():
        if type(self) != type(other):
            return False

        return dict(self._listed_items()) == dict(other._listed_items())

    #def _not_equiv():
    #    return not self.equiv(other)

    def __repr__(self):
        d = dict(self.__dict__.items())
        for key, _ in d.items():
            if key not in self._listed:
                del d[key]
        s = '%s(%r)' % (self.__class__.__name__, d)
        return s

    def __str__(self):
        s = '<%s>' % self.__class__.__name__
        for _, value in self._printed_items():
            if isinstance(value, unicode):
                value = value.replace(u'\xA0', u' ')
                value = value.encode('latin1', 'ignore')
            s += ' %s' % str(value)
        return s

    def items(self):
        return [(k, v) for k, v in self.__dict__.items() if k[0] != '_' and k not in self._reserved]

    def _compared_items(self):
        return [(k, self.__dict__.get(k)) for k in self._compared]

    def _listed_items(self):
        return [(k, self.__dict__.get(k)) for k in self._listed]

    def _printed_items(self):
        return [(k, self.__dict__.get(k)) for k in self._printed]

    def _required_items(self):
        return [(k, self.__dict__.get(k)) for k in self._required]

    def _changed_items(self):
        return [(k, self.__dict__.get(k)) for k in self._changed]

    @property
    def _changed(self):

        def changed_key(k, v):
            if k in self._required:
                return True
            elif k in self._optional.keys():
                if k in self._types.keys():
                    try:
                        trial = (v == self._instantiate(self._types[k], k, self._optional[k]))
                    except:
                        trial = True
                    return not trial
                else:
                    return not (v == self._optional[k])
            else:
                return not (k in self._reserved)

        return [k for k, v in self.__dict__.items() if changed_key(k, v)]

    @property
    def _listed(self):
        # a list of unique fields which are a union
        # of required, optional, and typed fields
        listed = list(self._required)
        addfields = set(self._optional.keys() + self._types.keys())
        addfields -= set(self._required)
        listed += list(addfields)
        return listed

    # The following methods are for use with JSON
    _json_kw = {
        'indent': 4,          # The default for JSONEncoder is indent=None, the default for json.tool is indent=4
        'separators': (',',   # The comma is usually at the end of a line
                       ': '), # The colon is usually in the middle of a line
    }

    def to_json(self, dict_class=dict):
        return object_to_json(self, dict_class=dict_class)

    def dumps(self):
        import json
        return json.dumps(self.to_json(), default=object_to_json, **self._json_kw)

    def dump(self, f):
        import json
        json.dump(self.to_json(), f, default=object_to_json, **self._json_kw)
        return

    @classmethod
    def loads(cls, s):
        import json
        return cls(json.loads(s))

    @classmethod
    def load(cls, f):
        import json
        return cls(json.load(f))
