import os, string, Cookie, sha, time, random, cgi, urllib, datetime, StringIO, pickle

from google.appengine.api import users
from google.appengine.api import memcache
from google.appengine.ext import db

from models.database import *

from modules.config import *
from modules.offsets import *



def get_user_agent(): return os.environ['HTTP_USER_AGENT']
def get_remote_ip(): return os.environ['REMOTE_ADDR']

def ip2long(ip):
  ip_array = ip.split('.')
  ip_long = int(ip_array[0]) * 16777216 + int(ip_array[1]) * 65536 + int(ip_array[2]) * 256 + int(ip_array[3])
  return ip_long

def long2ip(val):
  slist = []
  for x in range(0,4):
    slist.append(str(int(val >> (24 - (x * 8)) & 0xFF)))
  return ".".join(slist)

def to_unicode(val):
  if isinstance(val, unicode): return val
  try:
    return unicode(val, 'latin-1')
  except:
    pass
  try:
    return unicode(val, 'ascii')
  except:
    pass
  try:
    return unicode(val, 'utf-8')
  except:
    raise

def to_utf8(s):
    s = to_unicode(s)
    return s.encode("utf-8")

def req_get_vals(req, names, strip=True): 
  if strip:
    return [req.get(name).strip() for name in names]
  else:
    return [req.get(name) for name in names]

def get_inbound_cookie():
  c = Cookie.SimpleCookie()
  cstr = os.environ.get('HTTP_COOKIE', '')
  c.load(cstr)
  return c

def new_user_id():
  sid = sha.new(repr(time.time())).hexdigest()
  return sid

def valid_user_cookie(c):
  # cookie should always be a hex-encoded sha1 checksum
  if len(c) != 40:
    return False
  # TODO: check that user with that cookie exists, the way appengine-utilities does
  return True

g_anonUser = None
def anonUser():
  global g_anonUser
  if None == g_anonUser:
    g_anonUser = users.User("dummy@dummy.address.com")
  return g_anonUser

def fake_error(response):
  response.headers['Content-Type'] = 'text/plain'
  response.out.write('There was an error processing your request.')

def valid_forum_url(url):
  if not url:
    return False
  try:
    return url == urllib.quote_plus(url)
  except:
    return False
     
# very simplistic check for <txt> being a valid e-mail address
def valid_email(txt):
  # allow empty strings
  if not txt:
    return True
  if '@' not in txt:
    return False
  if '.' not in txt:
    return False
  return True

def forum_from_url(url):
  assert '/' == url[0]
  path = url[1:]
  if '/' in path:
    (forumurl, rest) = path.split("/", 1)
  else:
    forumurl = path
  return Forum.gql("WHERE url = :1", forumurl).get()
      
def forum_root(forum): return "/" + forum.url + "/"

def forum_siteroot_tmpldir_from_url(url):
  assert '/' == url[0]
  path = url[1:]
  if '/' in path:
    (forumurl, rest) = path.split("/", 1)
  else:
    forumurl = path
  forum = Forum.gql("WHERE url = :1", forumurl).get()
  if not forum:
    return (None, None, None)
  siteroot = forum_root(forum)
  skin_name = forum.skin
  if skin_name not in SKINS_LIST:
    skin_name = SITE['skin']['default']
  tmpldir = os.path.join(SITE['skin']['dir'], skin_name)
  return (forum, siteroot, tmpldir)

def get_log_in_out(url):
  user = users.get_current_user()
  if user:
    if users.is_current_user_admin():
      return "Welcome admin, %s! <a href=\"%s\">Log out</a>" % (user.nickname(), users.create_logout_url(url))
    else:
      return "Welcome, %s! <a href=\"%s\">Log out</a>" % (user.nickname(), users.create_logout_url(url))
  else:
    return "<a href=\"%s\">Log in or register</a>" % users.create_login_url(url)    
    
    
def get_admin_template(url):
    return '%s/%s/admin/%s' % (SITE['skin']['dir'], SITE['skin']['default'], url)
