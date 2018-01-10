import os


class BaseConf(object):
    APP_FOLDER = os.path.dirname(os.path.abspath(__file__))[:-5]
    DATABASE = os.path.join(APP_FOLDER, 'crowdbench.db')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///%s' % DATABASE
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = False


class DevConf(BaseConf):
    DEBUG = True
    SQLALCHEMY_ECHO = True


class ProdConf(BaseConf):
    DEBUG = False
    SQLALCHEMY_ECHO = False
