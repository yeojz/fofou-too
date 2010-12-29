import os, string, Cookie, sha, time, random, cgi, urllib, datetime, StringIO, pickle

from google.appengine.api import users
from google.appengine.ext import webapp

from google.appengine.ext.webapp import template
from django.template import Context, Template

from django.utils import feedgenerator

from models.database import *

from modules.offsets import *
from modules.config import *
from modules.app_function import *

import logging


class FofouBase(webapp.RequestHandler):

  _cookie = None
  # returns either a FOFOU_COOKIE sent by the browser or a newly created cookie
  def get_cookie(self):
    if self._cookie != None:
      return self._cookie
    cookies = get_inbound_cookie()
    for cookieName in cookies.keys():
      if FOFOU_COOKIE != cookieName:
        del cookies[cookieName]
    if (FOFOU_COOKIE not in cookies) or not valid_user_cookie(cookies[FOFOU_COOKIE].value):
      cookies[FOFOU_COOKIE] = new_user_id()
      cookies[FOFOU_COOKIE]['path'] = '/'
      cookies[FOFOU_COOKIE]['expires'] = COOKIE_EXPIRE_TIME
    self._cookie = cookies[FOFOU_COOKIE]
    return self._cookie

  _cookie_to_set = None
  # remember cookie so that we can send it when we render a template
  def send_cookie(self):
    if None == self._cookie_to_set:
      self._cookie_to_set = self.get_cookie()

  def get_cookie_val(self):
    c = self.get_cookie()
    return c.value

  def get_fofou_user(self):
    # get user either by google user id or cookie
    user_id = users.get_current_user()
    user = None
    if user_id:
      user = FofouUser.gql("WHERE user = :1", user_id).get()
      #if user: logging.info("Found existing user for by user_id '%s'" % str(user_id))
    else:
      cookie = self.get_cookie_val()
      if cookie:
        user = FofouUser.gql("WHERE cookie = :1", cookie).get()
        #if user:
        #  logging.info("Found existing user for cookie '%s'" % cookie)
        #else:
        #  logging.info("Didn't find user for cookie '%s'" % cookie)
    return user

  def template_out(self, template_name, template_values):
    self.response.headers['Content-Type'] = 'text/html'
    if None != self._cookie_to_set:
      # a hack extract the cookie part from the whole "Set-Cookie: val" header
      c = str(self._cookie_to_set)
      c = c.split(": ", 1)[1]
      self.response.headers["Set-Cookie"] = c
    #path = os.path.join(os.path.dirname(__file__), template_name)
    path = template_name
    #logging.info("tmpl: %s" % path)
    res = template.render(path, template_values)
    self.response.out.write(res)
    
    
    

# responds to /<forumurl>/rss, returns an RSS feed of recent topics
# (taking into account only the first post in a topic - that's what
# joelonsoftware forum rss feed does)
class RssFeed(webapp.RequestHandler):

  def get(self):
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.error(HTTP_NOT_FOUND)

    cached_feed = memcache.get(RSS_MEMCACHED_KEY)
    if cached_feed is not None:
      self.response.headers['Content-Type'] = 'text/xml'
      self.response.out.write(cached_feed)
      return
      
    feed = feedgenerator.Atom1Feed(
      title = forum.title or forum.url,
      link = siteroot + "rss",
      description = forum.tagline)
  
    topics = Topic.gql("WHERE forum = :1 AND is_deleted = False ORDER BY created_on DESC", forum).fetch(25)
    for topic in topics:
      title = topic.subject
      link = siteroot + "topic?id=" + str(topic.key().id())
      first_post = Post.gql("WHERE topic = :1 ORDER BY created_on", topic).get()
      msg = first_post.message
      # TODO: a hack: using a full template to format message body.
      # There must be a way to do it using straight django APIs
      name = topic.created_by
      if name:
        t = Template("<strong>{{ name }}</strong>: {{ msg|striptags|escape|urlize|linebreaksbr }}")
      else:
        t = Template("{{ msg|striptags|escape|urlize|linebreaksbr }}")
      c = Context({"msg": msg, "name" : name})
      description = t.render(c)
      pubdate = topic.created_on
      feed.add_item(title=title, link=link, description=description, pubdate=pubdate)
    feedtxt = feed.writeString('utf-8')
    self.response.headers['Content-Type'] = 'text/xml'
    self.response.out.write(feedtxt)
    memcache.add(RSS_MEMCACHED_KEY, feedtxt)

# responds to /<forumurl>/rssall, returns an RSS feed of all recent posts
# This is good for forum admins/moderators who want to monitor all posts
class RssAllFeed(webapp.RequestHandler):

  def get(self):
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.error(HTTP_NOT_FOUND)

    feed = feedgenerator.Atom1Feed(
      title = forum.title or forum.url,
      link = siteroot + "rssall",
      description = forum.tagline)
  
    posts = Post.gql("WHERE forum = :1 AND is_deleted = False ORDER BY created_on DESC", forum).fetch(25)
    for post in posts:
      topic = post.topic
      title = topic.subject
      link = siteroot + "topic?id=" + str(topic.key().id())
      msg = post.message
      # TODO: a hack: using a full template to format message body.
      # There must be a way to do it using straight django APIs
      name = post.user_name
      if name:
        t = Template("<strong>{{ name }}</strong>: {{ msg|striptags|escape|urlize|linebreaksbr }}")
      else:
        t = Template("{{ msg|striptags|escape|urlize|linebreaksbr }}")
      c = Context({"msg": msg, "name" : name})
      description = t.render(c)
      pubdate = post.created_on
      feed.add_item(title=title, link=link, description=description, pubdate=pubdate)
    feedtxt = feed.writeString('utf-8')
    self.response.headers['Content-Type'] = 'text/xml'
    self.response.out.write(feedtxt)
    
    
# responds to GET /postdel?<post_id> and /postundel?<post_id>
class PostDelUndel(webapp.RequestHandler):
  def get(self):
    (forum, siteroot, tmpldir) = forum_siteroot_tmpldir_from_url(self.request.path_info)
    if not forum or forum.is_disabled:
      return self.redirect("/")
    is_moderator = users.is_current_user_admin()
    if not is_moderator or forum.is_disabled:
      return self.redirect(siteroot)
    post_id = self.request.query_string
    #logging.info("PostDelUndel: post_id='%s'" % post_id)
    post = db.get(db.Key.from_path('Post', int(post_id)))
    if not post:
      logging.info("No post with post_id='%s'" % post_id)
      return self.redirect(siteroot)
    if post.forum.key() != forum.key():
      loggin.info("post.forum.key().id() ('%s') != fourm.key().id() ('%s')" % (str(post.forum.key().id()), str(forum.key().id())))
      return self.redirect(siteroot)
    path = self.request.path
    if path.endswith("/postdel"):
      if not post.is_deleted:
        post.is_deleted = True
        post.put()
        memcache.delete(RSS_MEMCACHED_KEY)
      else:
        logging.info("Post '%s' is already deleted" % post_id)
    elif path.endswith("/postundel"):
      if post.is_deleted:
        post.is_deleted = False
        post.put()
        memcache.delete(RSS_MEMCACHED_KEY)
      else:
        logging.info("Trying to undelete post '%s' that is not deleted" % post_id)
    else:
      logging.info("'%s' is not a valid path" % path)

    topic = post.topic
    # deleting/undeleting first post also means deleting/undeleting the whole topic
    first_post = Post.gql("WHERE forum=:1 AND topic = :2 ORDER BY created_on", forum, topic).get()
    if first_post.key() == post.key():
      if path.endswith("/postdel"):
        topic.is_deleted = True
      else:
        topic.is_deleted = False
      topic.put()

    # redirect to topic owning this post
    topic_url = siteroot + "topic?id=" + str(topic.key().id())
    self.redirect(topic_url)
     