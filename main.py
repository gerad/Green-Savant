from google.appengine.ext import webapp
from google.appengine.ext import db
from google.appengine.ext.webapp import util

import pdb, sys
debugger = pdb.Pdb(stdin=sys.__stdin__, stdout=sys.__stdout__)

import rest

class ApiHandler(rest.RestHandler):
  def handle_path(self):
    return ApiPath(self.request)

class ApiPath(rest.RestPath):
  def __init__(self, request):
    self.__super().__init__(request.path)
    self.api_key = request.get('api_key')

  def entity(self):
    entity = self.__super().entity()
    if entity and entity.api_key != self.api_key:
      raise ApiSecurityError
    return entity

  def entities(self, model):
    return self.model().filter('api_key =', self.api_key)

  def __super(self): # python is retarded
    return super(ApiPath, self)

class ApiSecurityError(Exception):
  pass

class Log(db.Expando, rest.RestModel):
  api_key = db.StringProperty()
  url = db.StringProperty()
  referrer = db.StringProperty()
  seconds = db.IntegerProperty()
  cache_hit = db.BooleanProperty()
  access_at = db.DateTimeProperty()
  created_at = db.DateTimeProperty(auto_now_add=True)
  updated_at = db.DateTimeProperty(auto_now=True)

  def before_save(self):
    self.update_daily()
    # self.update_monthly()
    # self.update_domains()
    # self.update_referrers()

  def update_daily(self):
    access_day = datetime.date(
      self.access_at.year,
      self.access_at.month,
      self.access_at.day)
    d = Daily.find_or_new({
      'api_key': self.api_key,
      'day' : access_day })
    d.requests += 1
    d.seconds += self.seconds
    d.cache_hits += (1 if self.cache_hit else 0)

class Daily(db.Model, rest.RestModel):
  api_key = db.StringProperty()
  day = db.DateTimeProperty()
  requests = db.IntegerProperty(default=0)
  cache_hits = db.IntegerProperty(default=0)
  seconds = db.IntegerProperty(default=0)
  created_at = db.DateTimeProperty(auto_now_add=True)
  updated_at = db.DateTimeProperty(auto_now=True)

class Referrers(db.Model, rest.RestModel):
  api_key = db.StringProperty()
  referrer = db.StringProperty()
  requests_day = db.IntegerProperty()
  requests_7day = db.IntegerProperty()
  requests_30day = db.IntegerProperty()
  created_at = db.DateTimeProperty(auto_now_add=True)
  updated_at = db.DateTimeProperty(auto_now=True)
"""
class Domains(db.Model, rest.RestModel):
  api_key = db.StringProperty()
  domain = db.StringProperty()
  days = db.ListProperty(db.DateTimeProperty)
  requests = db.ListProperty(db.IntegerProperty)
  requests_day = db.IntegerProperty()
  requests_7day = db.IntegerProperty()
  requests_30day = db.IntegerProperty()
  created_at = db.DateTimeProperty(auto_now_add=True)
  updated_at = db.DateTimeProperty(auto_now=True)
"""
def main():
  application = webapp.WSGIApplication([(r'/.*', ApiHandler)],
                                       debug=True)
  util.run_wsgi_app(application)


if __name__ == '__main__':
  main()