
#########################################
#                                       #
#             SITE CONFIG               #
#                                       #
#########################################


SITE={
	'skin' : { 'default' : 'default',
               'dir' :'skins',
             },
}


#########################################
#                                       #
#   NO NEED TO EDIT BEYOND THIS POINT   #
#                                       #
#########################################

SKINS_LIST = ["default", 'skfou']

# HTTP codes
HTTP_NOT_ACCEPTABLE = 406
HTTP_NOT_FOUND = 404

RSS_MEMCACHED_KEY = "rss"


BANNED_IPS = {
    "59.181.121.8" : 1,
    "62.162.98.194" : 1,
    #"127.0.0.1" : 1,
}



# cookie code based on http://code.google.com/p/appengine-utitlies/source/browse/trunk/utilities/session.py
FOFOU_COOKIE = "fofou-uid"
COOKIE_EXPIRE_TIME = 60*60*24*120 # valid for 60*60*24*120 seconds => 120 days
