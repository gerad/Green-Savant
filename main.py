from google.appengine.ext import webapp
from google.appengine.ext.webapp import util
from django.utils import simplejson as JSON
from google.appengine.ext import db
import re

import pdb, sys
debugger = pdb.Pdb(stdin=sys.__stdin__, stdout=sys.__stdout__)


class MainHandler(webapp.RequestHandler):
  def get(self):
    self.rest = RestPath(self.request.path)
    if self.rest.entity(): # show
      self.__send_json(self.rest.entity().dict())
    elif self.rest.model(): # list
      self.__send_json([e.dict() for e in self.rest.model().all()])
    else: # / (root path)
      self.__send_json([self.request.path, self.request.body])

  def put(self):
    self.rest = RestPath(self.request.path)
    attrs = JSON.loads(self.request.body)
    self.__send_json(self.rest.entity().update_attributes(attrs).dict())

  def post(self):
    self.rest = RestPath(self.request.path)
    attrs = JSON.loads(self.request.body)
    self.__send_json(self.rest.model().create(attrs).dict())

  def delete(self):
    self.rest = RestPath(self.request.path)
    self.__send_json(self.rest.entity().delete().dict())

  def __send_json(self, data):
    self.response.content_type = 'application/json'
    JSON.dump(data, self.response.out)

class RestModel:
  @classmethod
  def find_or_create_by_name(cls, name):
    if name in globals():
      return globals()[name]
    else:
      return type(name, (cls, db.Expando), {})

  @classmethod
  def create(cls, attrs):
    return cls().update_attributes(attrs)

  def update_attributes(self, attrs):
    for k, v in attrs.items():
      setattr(self, str(k), v)
    self.put()
    return self

  def dict(self):
    ret = dict()
    for k in self.dynamic_properties():
      ret[k] = getattr(self, k)
    if self.is_saved(): ret['id'] = self.key().id()
    return ret

  def delete(self):
    db.Expando.delete(self) # TODO find a better way
    return self

class RestPath:
  def __init__(self, path):
    self.path = path
    self.name, self.key = self.__name_and_key()

  def model(self):
    if not self.name: return None
    return RestModel.find_or_create_by_name(self.name)

  def entity(self):
    if not (self.model() and self.key): return None
    return self.model().get_by_id(self.key)

  def __name_and_key(self):
    m = re.match(r'^/?(\w+)?/?(\d+)?$', self.path)
    name, key = m.groups()
    if key: key = int(key)
    if m: return name, key
    else: return None, None

def main():
  application = webapp.WSGIApplication([(r'/.*', MainHandler)],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()