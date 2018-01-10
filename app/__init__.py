from flask import Flask
from conf import conf


import os
import sys


sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'engine'))


def url_for_other_page(page):
    args = request.view_args.copy()
    args['page'] = page
    return url_for(request.endpoint, **args)


app = Flask(__name__, template_folder='templates')

app.config.from_object(conf.DevConf)
app.secret_key = 'Apparently appreciated apps & applets apply 4 appointments 2 appear in Appsterdam'
app.url_map.strict_slashes = False
app.jinja_env.globals['url_for_other_page'] = url_for_other_page


from .views import *
