import logging
from google.appengine.ext import db
from google.appengine.ext import webapp
from django.utils import simplejson
import re
import datetime
from dateutil.parser import parse as parse_date
import urllib2

import pdb, sys
debugger = pdb.Pdb(stdin=sys.__stdin__, stdout=sys.__stdout__)

class RestHandler(webapp.RequestHandler):
  def get(self):
    self.path = self.handle_path()
    if self.path.entity(): # show
      self.__send_json(self.path.entity().dict())
    elif self.path.model(): # list
      self.__send_json([e.dict() for e in self.path.entities()])
    else: # / (root path)
      self.__send_json([self.request.path, self.request.body])

  def put(self):
    self.path = self.handle_path()
    attrs = JSON.loads(self.request.body)
    self.__send_json(self.path.entity().update_attributes(attrs).dict())

  def post(self):
    self.path = self.handle_path()
    attrs = simplejson.loads(self.request.body)
    self.__send_json(self.path.model().create(attrs).dict())

  def delete(self):
    self.path = self.handle_path()
    self.__send_json(self.path.entity().destroy().dict())

  def __send_json(self, data):
    self.response.content_type = 'application/json'
    simplejson.dump(data, self.response.out)

  def handle_path(self):
    return RestPath(self.request.path)

class RestModel(db.Expando):
  @classmethod
  def find_or_create_by_name(cls, name):
    for sub in cls.__subclasses__():
      if sub.__name__ == name:
        return sub
    return type(name, (cls, db.Expando), {})

  @classmethod
  def create(cls, attrs):
    return cls().update_attributes(attrs).save()

  @classmethod
  def find_or_new(cls, attrs):
    query = cls.all()
    for k, v in attrs.items():
      query.filter(k + '=', v)
    res = query.fetch(1)
    if not res:
      return cls().update_attributes(attrs)
    return res.pop()

  def update_attributes(self, attrs):
    for k, v in attrs.items():
      self.__update_attribute(str(k), v)
    return self

  def save(self):
    self.before_save()
    self.put()
    return self

  def before_save(self):
    pass # overwrite in subclasses

  def dict(self, include=None, exclude=None):
    ret = dict()
    for k in self.allowed_attributes():
      if include and k not in include: continue
      if exclude and k in exclude: continue
      ret[k] = self.__jsonify(getattr(self, k))
    if self.is_saved(): ret['id'] = self.key().id()
    return ret

  def allowed_attributes(self):
    return self.properties().keys() + self.dynamic_properties()

  def destroy(self):
    self.delete()
    return self

  def __update_attribute(self, attribute, value):
    if attribute in self.properties():
      property = type(self.properties()[attribute])
      if property in [db.DateTimeProperty, db.DateProperty, db.TimeProperty] and type(value) in [str, unicode]:
        value = parse_date(value)
    setattr(self, attribute, value)

  def __jsonify(self, attr): # TODO find a better way
    t = type(attr)
    if t == datetime.datetime:
      return attr.isoformat()
    if hasattr(attr, 'dict'):
      return attr.dict()
    return attr

class RestPath(object):
  def __init__(self, path):
    self.path = path
    self.name, self.key = self.__name_and_key()

  def model(self):
    if not self.name: return None
    return RestModel.find_or_create_by_name(self.name)

  def entities(self):
    return self.model().all()

  def entity(self):
    if not (self.model() and self.key): return None
    return self.model().get_by_id(self.key)

  def __name_and_key(self):
    m = re.match(r'^/?(\w+)?/?(\d+)?$', self.path)
    if m:
      name, key = m.groups()
      if key: key = int(key)
      return name, key
    else: return None, None