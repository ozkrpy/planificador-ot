import os

BASEDIR = os.path.abspath(os.path.dirname(__file__))

# class Config:
#     SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASEDIR, 'data.db')
#     SQLALCHEMY_TRACK_MODIFICATIONS = False
#     SECRET_KEY = 'dev-key-placeholder' # Required for forms later

class Config:
    """Shared base — never instantiated directly."""
    SECRET_KEY          = os.environ.get('SECRET_KEY', 'dev-key-placeholder')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED    = True

class DevelopmentConfig(Config):
    DEBUG    = True
    ENV      = 'development'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DEV_DATABASE_URL',
        'sqlite:///ot_planning_dev.db'
    )

class StagingConfig(Config):
    DEBUG    = False
    TESTING  = True
    ENV      = 'staging'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'STAGING_DATABASE_URL',
        'sqlite:///ot_planning_staging.db'
    )

class ProductionConfig(Config):
    DEBUG    = False
    ENV      = 'production'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///harmony.db'   # change to real DB
    )
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY = True
    PREFERRED_URL_SCHEME = 'https'

config = {
    'development': DevelopmentConfig,
    'staging':     StagingConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig
}