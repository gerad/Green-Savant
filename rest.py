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
      self.__send_json([e.dict() for e in self.__limit(self.path.entities())])
    else: # / (root path)
      self.__send_json([self.request.path, self.request.body])

  def put(self):
    self.path = self.handle_path()
    logging.info(self.request.body)
    attrs = JSON.loads(self.request.body)
    self.__send_json(self.path.entity().update_attributes(attrs).dict())

  def post(self):
    self.path = self.handle_path()
    logging.info(self.request.body)
    attrs = simplejson.loads(self.request.body)
    self.__send_json(self.path.model().create(attrs).dict())

  def delete(self):
    self.path = self.handle_path()
    self.__send_json(self.path.entity().destroy().dict())

  def __send_json(self, data):
    self.response.content_type = 'application/json'
    json = simplejson.dumps(data)
    callback = self.request.get('callback')
    if callback:
      json = ''.join([callback, '(', json, ');'])
    self.response.out.write(json)

  def __limit(self, query):
    i = int(self.request.get('limit')) if self.request.get('limit') else 10
    iter = query.__iter__()
    while i > 0:
      yield iter.next()
      i -= 1

  def handle_path(self):
    return RestPath(self.request.path)

class RestModel(db.Expando):
  @classmethod
  def default_order(cls):
    return None

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
    res = query.get()
    if not res:
      res = cls().update_attributes(attrs)
    return res

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
    if t in [datetime.datetime, datetime.date, datetime.time]:
      return self.__httpdate(attr)
    if hasattr(attr, 'dict'):
      return attr.dict()
    return attr

  # http://stackoverflow.com/questions/225086/rfc-1123-date-representation-in-python
  def __httpdate(self, dt):
      if type(dt) == datetime.date:
        dt = datetime.datetime.combine(dt, datetime.time())
      weekday = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][dt.weekday()]
      month = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
               "Oct", "Nov", "Dec"][dt.month - 1]
      return "%s, %02d %s %04d %02d:%02d:%02d GMT" % (weekday, dt.day, month,
          dt.year, dt.hour, dt.minute, dt.second)

class RestPath(object):
  def __init__(self, request):
    self.request = request
    self.path = request.path
    self.name, self.key = self.__name_and_key()

  def model(self):
    if not self.name: return None
    return RestModel.find_or_create_by_name(self.name)

  def entities(self):
    order = self.request.get('order') or self.model().default_order()
    q = self.model().all()
    if order:
      q.order(order)
    return q

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